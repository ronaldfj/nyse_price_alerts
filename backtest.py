"""
Stock Sentinel — Backtesting Engine
====================================
Reutiliza add_indicators() y la logica de scoring de alert.py (v2.2+)
para simular señales barra a barra sobre historico de yfinance.

Salidas:
  - backtest_trades.csv   — mismo schema que alerts_history.csv
  - backtest_report.md    — metricas por simbolo, playbook, score bucket, año
  - analysis_output/      — tablas CSV de expectancy

Uso:
  python backtest.py
  python backtest.py --years 3 --symbols AAPL,MSFT,NVDA
  python backtest.py --years 5 --min-score 5.5 --min-rr 0.8
  python backtest.py --years 3 --export-features  # CSV para ML

Anti look-ahead:
  En cada barra i, solo se usan datos hasta i (inclusive).
  Los indicadores se calculan sobre df[:i+1] — nunca sobre el df completo.
  Para eficiencia, los indicadores se calculan una sola vez sobre el df
  completo y luego se itera sobre filas — esto es seguro para indicadores
  causales (EMA, ATR, ADX, MACD) pero requiere shift() para prior_high/low,
  que ya esta implementado en add_indicators() con .shift(1).
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import logging
import os
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd
import yfinance as yf

# v2.9: importar indicadores desde modulo compartido (UNICA fuente de verdad)
from signals import (
    add_indicators as _signals_add_indicators,
    compute_relative_strength as _signals_compute_rs,
)
# FIX: universo importado desde alert.py — antes backtest.py mantenia su propia copia de
# STOCK_NAMES/STOCK_GROUPS (16 simbolos, ultima vez sincronizada ~v2.2), que incluia TSLA y
# PG (excluidos del universo en vivo desde v2.5 por mal desempeno: avg_R=-0.086/-0.166) y le
# faltaban 24+ simbolos que SI corren en produccion (AMD, CRM, NOW, ORCL, ANET, GS, AXP, LLY,
# ABT, ISRG, NKE, MCD, todo Industrial/Energy, y los 6 ETFs sectoriales). Correr
# `python backtest.py` sin --symbols validaba una lista que no tiene nada que ver con lo que
# el bot realmente escanea dos veces al dia — es decir, ~60% del universo en vivo nunca paso
# por el backtest, y dos simbolos deliberadamente excluidos seguian contaminando las metricas
# agregadas. Importar desde alert.py garantiza que ambos usen el mismo universo por
# construccion (mismo principio de fuente unica que signals.py aplica a los indicadores).
# Se suman INDEX_ETFS/SECTOR_ETFS por la misma razon: son datos de clasificacion del
# universo (no parametros de estrategia), asi que tambien deben tener una unica fuente.
from alert import STOCK_NAMES, STOCK_GROUPS, INDEX_ETFS, SECTOR_ETFS, BREADTH_PROXY_SYMBOLS
# FIX (mejora institucional #1): motor de scoring compartido con alert.py — ver scoring.py
# para el detalle de que reglas nunca habian llegado a este archivo (confluence floors,
# bloqueo Supertrend+RS negativa, ETF RS floor, gate de ALERT_ETFS).
import scoring

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("backtest")

# ---------------------------------------------------------------------------
# Universo — importado desde alert.py (ver FIX arriba, junto al import de signals.py)
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# Parametros (sobreescribibles via env o args)
# ---------------------------------------------------------------------------
MIN_SCORE           = float(os.getenv("MIN_SCORE", "5.8"))
MIN_RR              = float(os.getenv("MIN_RR", "0.8"))
# v2.11: riesgo minimo (en ATR) medido contra la entrada REAL (Open t+1). Un gap a la baja
# dentro del umbral del gap filter puede dejar el Open pegado al stop (riesgo ~0) e inflar
# el R de cualquier trade ganador (caso XLP 2024-08-02: riesgo 0.15 -> +21R).
MIN_ENTRY_RISK_ATR  = float(os.getenv("MIN_ENTRY_RISK_ATR", "0.5"))
SETUP_RSI_MIN       = float(os.getenv("SETUP_RSI_MIN", "45"))
SETUP_RSI_MAX       = float(os.getenv("SETUP_RSI_MAX", "66"))
BREAKOUT_RSI_MAX    = float(os.getenv("BREAKOUT_RSI_MAX", "76"))
RS_LOOKBACK         = int(os.getenv("RS_LOOKBACK", "20"))
SWING_LOOKBACK      = int(os.getenv("SWING_LOOKBACK", "12"))
PULLBACK_MAX_ATR    = float(os.getenv("PULLBACK_MAX_ATR", "1.20"))
BREAKOUT_MAX_ATR    = float(os.getenv("BREAKOUT_MAX_ATR", "3.20"))
WEAK_ADX_BLOCK      = float(os.getenv("WEAK_ADX_BLOCK", "15.0"))
BREAKOUT_RS_MIN     = float(os.getenv("BREAKOUT_RS_MIN", "-0.5"))
BREAKOUT_NEAR_PCT   = float(os.getenv("BREAKOUT_NEAR_PCT", "0.995"))
FINAL_RS_MIN        = float(os.getenv("FINAL_RS_MIN", "0.0"))
TRIGGER_VOL_RATIO   = float(os.getenv("TRIGGER_VOL_RATIO", "1.00"))
BREAKOUT_VOL_HARD_GATE = float(os.getenv("BREAKOUT_VOL_HARD_GATE", "0"))  # v2.11: 0 = desactivado
SUPERTREND_PERIOD   = int(os.getenv("SUPERTREND_PERIOD", "10"))
SUPERTREND_MULT     = float(os.getenv("SUPERTREND_MULTIPLIER", "3.0"))
SUPERTREND_BLOCK    = os.getenv("SUPERTREND_REGIME_BLOCK", "true").lower() == "true"
VIX_BLOCK_LEVEL     = float(os.getenv("VIX_BLOCK_LEVEL", "30.0"))
VIX_CAUTION_LEVEL   = float(os.getenv("VIX_CAUTION_LEVEL", "22.0"))
VIX_LOW_LEVEL       = float(os.getenv("VIX_LOW_LEVEL", "18.0"))
# v2.0
BREAKOUT_ATR_GATE           = float(os.getenv("BREAKOUT_ATR_GATE", "2.0"))
BREAKOUT_EXTENDED_VOL_RATIO = float(os.getenv("BREAKOUT_EXTENDED_VOL_RATIO", "1.8"))
BREAKOUT_EXT_VOL_LOW_VIX    = float(os.getenv("BREAKOUT_EXTENDED_VOL_RATIO_LOW_VIX", "1.5"))
SLOPE_CONSISTENCY_RATIO     = float(os.getenv("SLOPE_CONSISTENCY_RATIO", "0.3"))
SLOPE_WEAK_PENALTY          = float(os.getenv("SLOPE_WEAK_PENALTY", "0.4"))
ADAPTIVE_RR_EXT_THRESHOLD   = float(os.getenv("ADAPTIVE_RR_EXTENSION_THRESHOLD", "20.0"))
ADAPTIVE_RR_MULTIPLIER      = float(os.getenv("ADAPTIVE_RR_MULTIPLIER", "1.25"))
VOLUME_PROFILE_LOOKBACK     = int(os.getenv("VOLUME_PROFILE_LOOKBACK", "3"))
VOLUME_PROFILE_PENALTY      = float(os.getenv("VOLUME_PROFILE_PENALTY", "0.5"))
# v2.1
# FIX: se elimino CONFLUENCE_THRESHOLD — el umbral de bonus ahora es siempre "exactamente
# 4" (hardcodeado en scoring.py, igual que en alert.py) en vez de un umbral configurable;
# ese ">= threshold" generico es exactamente el codigo muerto que se documenta en
# scoring.py (con threshold=4 y los casos 4/5 exactos ya resueltos, nunca se alcanzaba).
CONFLUENCE_BONUS     = float(os.getenv("CONFLUENCE_BONUS", "0.5"))
# v2.2
FINAL_RS_MIN_BY_GROUP_RAW = os.getenv("FINAL_RS_MIN_BY_GROUP", "Finance:-4.0,Health:-4.0,Consumer:-2.0")
FINAL_RS_MIN_BY_GROUP: dict[str, float] = {}
for _e in FINAL_RS_MIN_BY_GROUP_RAW.split(","):
    _p = _e.strip().split(":")
    if len(_p) == 2:
        try:
            FINAL_RS_MIN_BY_GROUP[_p[0].strip()] = float(_p[1].strip())
        except ValueError:
            pass

# FIX (mejora institucional #1): parametros v2.6 que backtest.py nunca leia — el
# scoring compartido (scoring.py) los necesita para aplicar exactamente las mismas
# reglas que alert.py. Mismos nombres/defaults que alert.py.
CONFLUENCE_HARD_FLOOR    = int(os.getenv("CONFLUENCE_HARD_FLOOR", "2"))
CONFLUENCE_SOFT_FLOOR    = int(os.getenv("CONFLUENCE_SOFT_FLOOR", "3"))
CONFLUENCE_LOW_PENALTY   = float(os.getenv("CONFLUENCE_LOW_PENALTY", "0.5"))
SUPERTREND_BLOCK_ADX_MIN = float(os.getenv("SUPERTREND_BLOCK_ADX_MIN", "15.0"))
SUPERTREND_BLOCK_RS_NEG  = os.getenv("SUPERTREND_BLOCK_RS_NEG", "true").lower() == "true"
ETF_RS_FLOOR             = float(os.getenv("ETF_RS_FLOOR", "-3.0"))
ALERT_ETFS               = os.getenv("ALERT_ETFS", "false").lower() == "true"

# Backtest-especifico
# v2.7: Pullback Hardening (Backtest Fase B mostro pullback degradandose)
# v2.10: pullback eliminado del sistema

# v2.12: paridad con el vivo. Antes 5 barras de cooldown y time-stop de 15, mientras
# alert.py usa COOLDOWN_HOURS=48 (~2 sesiones) y TRACKER_MAX_BARS_OPEN=20: el backtest
# validaba un sistema distinto al que corre en produccion.
# Los cooldowns del vivo son horas de reloj entre corridas, no barras: se replican como
# dias calendario entre la fecha de corrida (barra i) de una alerta y la siguiente — asi
# un fin de semana cuenta igual que en produccion.
COOLDOWN_DAYS           = float(os.getenv("COOLDOWN_HOURS", "48")) / 24.0
# Con el scanner corriendo tras el cierre, el tracker detecta el stop la noche misma de
# la barra de salida, y el post-stop cooldown corre desde esa fecha.
POST_STOP_COOLDOWN_DAYS = float(os.getenv("POST_STOP_COOLDOWN_HOURS", "72")) / 24.0
POST_STOP_SCORE_PENALTY = float(os.getenv("POST_STOP_SCORE_PENALTY", "1.0"))
MAX_BARS_HOLD       = int(os.getenv("BT_MAX_BARS_HOLD", os.getenv("TRACKER_MAX_BARS_OPEN", "20")))  # time-stop
REQUIRE_PLAYBOOK    = True

# v2.12: filtros que antes existian solo en alert.py (ver CLAUDE.md, drift vivo vs backtest)
EARNINGS_FILTER_ENABLED   = os.getenv("BT_EARNINGS_FILTER", "true").lower() == "true"
EARNINGS_BUFFER_DAYS      = int(os.getenv("EARNINGS_BUFFER_DAYS", "5"))
BREADTH_ENABLED           = os.getenv("BREADTH_ENABLED", "true").lower() == "true"
BREADTH_MIN_PCT           = float(os.getenv("BREADTH_MIN_PCT", "50.0"))
BREADTH_BLOCK_BELOW       = float(os.getenv("BREADTH_BLOCK_BELOW", "40.0"))
CORRELATION_GUARD_ENABLED = os.getenv("CORRELATION_GUARD_ENABLED", "true").lower() == "true"
GAP_BLOCK_PCT             = float(os.getenv("GAP_BLOCK_PCT", "2.0"))

# Parametros del nucleo de scoring compartido — ver alert.py::_CORE_PARAMS (misma idea).
_CORE_PARAMS = scoring.CoreParams(
    setup_rsi_min=SETUP_RSI_MIN,
    setup_rsi_max=SETUP_RSI_MAX,
    breakout_rsi_max=BREAKOUT_RSI_MAX,
    pullback_max_atr=PULLBACK_MAX_ATR,
    breakout_max_atr=BREAKOUT_MAX_ATR,
    weak_adx_block=WEAK_ADX_BLOCK,
    breakout_rs_min=BREAKOUT_RS_MIN,
    breakout_near_pct=BREAKOUT_NEAR_PCT,
    final_rs_min=FINAL_RS_MIN,
    final_rs_min_by_group=FINAL_RS_MIN_BY_GROUP,
    vix_block_level=VIX_BLOCK_LEVEL,
    vix_caution_level=VIX_CAUTION_LEVEL,
    vix_low_level=VIX_LOW_LEVEL,
    breakout_atr_gate=BREAKOUT_ATR_GATE,
    breakout_extended_vol_ratio=BREAKOUT_EXTENDED_VOL_RATIO,
    breakout_extended_vol_ratio_low_vix=BREAKOUT_EXT_VOL_LOW_VIX,
    slope_consistency_ratio=SLOPE_CONSISTENCY_RATIO,
    slope_weak_penalty=SLOPE_WEAK_PENALTY,
    trigger_vol_ratio=TRIGGER_VOL_RATIO,
    breakout_vol_hard_gate=BREAKOUT_VOL_HARD_GATE,
    volume_profile_lookback=VOLUME_PROFILE_LOOKBACK,
    volume_profile_penalty=VOLUME_PROFILE_PENALTY,
    supertrend_regime_block=SUPERTREND_BLOCK,
    supertrend_block_adx_min=SUPERTREND_BLOCK_ADX_MIN,
    supertrend_block_rs_neg=SUPERTREND_BLOCK_RS_NEG,
    confluence_hard_floor=CONFLUENCE_HARD_FLOOR,
    confluence_soft_floor=CONFLUENCE_SOFT_FLOOR,
    confluence_low_penalty=CONFLUENCE_LOW_PENALTY,
    confluence_bonus=CONFLUENCE_BONUS,
    adaptive_rr_extension_threshold=ADAPTIVE_RR_EXT_THRESHOLD,
    adaptive_rr_multiplier=ADAPTIVE_RR_MULTIPLIER,
    min_rr=MIN_RR,
    etf_rs_floor=ETF_RS_FLOOR,
    index_etfs=frozenset(INDEX_ETFS),
    sector_etfs=frozenset(SECTOR_ETFS),
    breadth_min_pct=BREADTH_MIN_PCT,
    breadth_block_below=BREADTH_BLOCK_BELOW,
)

# ---------------------------------------------------------------------------
# Schema CSV de salida (compatible con alerts_history.csv)
# ---------------------------------------------------------------------------
TRADE_COLUMNS = [
    "timestamp_utc", "trigger_candle_utc", "setup_key", "setup_hash",
    "symbol", "name", "group", "playbook",
    "price", "real_entry", "target", "stop", "rr", "score",
    "regime_score", "setup_score", "trigger_score",
    "atr", "adx", "rsi", "rs20", "extension_pct",
    "reasons", "warnings", "blocked",
    "status", "bars_open", "days_open",
    "current_price", "pnl_pct", "mfe_pct", "mae_pct",
    "exit_date", "exit_price", "exit_reason", "closed_utc",
    # columnas extra para analisis ML
    "year", "month", "vol_ratio", "pullback_atr", "trend_quality",
    "confluence_count", "adx_at_entry", "vix_proxy",
]

def add_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """v2.9: delega al modulo signals.py — unica fuente de verdad."""
    return _signals_add_indicators(
        df,
        swing_lookback=SWING_LOOKBACK,
        supertrend_period=SUPERTREND_PERIOD,
        supertrend_multiplier=SUPERTREND_MULT,
    )


# ---------------------------------------------------------------------------
# Datos
# ---------------------------------------------------------------------------

def fetch_data(symbol: str, years: int = 5) -> Optional[pd.DataFrame]:
    period = f"{years}y"
    for attempt in range(3):
        try:
            df = yf.Ticker(symbol).history(period=period, interval="1d", auto_adjust=True)
            if df is not None and not df.empty and {"High","Low","Close","Volume"}.issubset(df.columns):
                df = df.dropna(subset=["High","Low","Close","Volume"])
                if len(df) >= 220:
                    return df
        except Exception as exc:
            log.warning("%s intento %s: %s", symbol, attempt+1, exc)
            time.sleep(2 ** attempt)
    return None


# ---------------------------------------------------------------------------
# RS vs SPY (barra a barra, sobre slice hasta i)
# ---------------------------------------------------------------------------

def compute_rs(symbol_closes: pd.Series, spy_closes: pd.Series, i: int) -> float:
    if i < RS_LOOKBACK + 2:
        return 0.0
    asset_base = float(symbol_closes.iloc[i - 1 - RS_LOOKBACK])
    spy_base   = float(spy_closes.iloc[i - 1 - RS_LOOKBACK])
    # Guard: precio cero o negativo indica datos corruptos
    if asset_base <= 0.0 or spy_base <= 0.0:
        return 0.0
    asset_val = float(symbol_closes.iloc[i - 1])
    spy_val   = float(spy_closes.iloc[i - 1])
    if np.isnan(asset_val) or np.isnan(spy_val):
        return 0.0
    asset_ret = (asset_val / asset_base - 1.0) * 100
    spy_ret   = (spy_val   / spy_base   - 1.0) * 100
    return round(asset_ret - spy_ret, 2)


# ---------------------------------------------------------------------------
# Evaluacion de una barra — misma logica que evaluate_stock() de alert.py
# ---------------------------------------------------------------------------

def _fmt(v: float, d: int = 4) -> str:
    return f"{v:.{d}f}"


def evaluate_bar(
    symbol: str,
    df: pd.DataFrame,
    i: int,
    spy_closes: pd.Series,
    vix_proxy: float,
    breadth_pct: Optional[float] = None,
) -> Optional[dict]:
    """
    Evalua la barra i usando datos hasta i inclusive.
    Retorna un dict con la señal o None si no hay señal.
    i >= 3 siempre (necesitamos last=i-1, prev=i-2 para ser consistentes
    con alert.py que usa iloc[-2] y iloc[-3] sobre el df completo).

    FIX (mejora institucional #1): delega el scoring tecnico a scoring.py, el mismo
    nucleo que usa alert.py en vivo. Antes esta funcion reimplementaba ~250 lineas de
    logica que habia divergido: sin confluence hard/soft floor (v2.6), sin el bloqueo
    Supertrend+RS negativa (v2.6 Fix #3), aplicando descuento de RS a ETFs sectoriales
    que alert.py exime, y con ADX>=20 hardcodeado para el bloqueo Supertrend en vez del
    SUPERTREND_BLOCK_ADX_MIN configurable. Ver scoring.py para el detalle completo.
    """
    if i < 220:
        return None

    last = df.iloc[i - 1]   # barra "cerrada" mas reciente (igual que alert.py iloc[-2])
    prev = df.iloc[i - 2]   # barra anterior                (igual que alert.py iloc[-3])

    group  = STOCK_GROUPS.get(symbol, "Other")
    name   = STOCK_NAMES.get(symbol, symbol)
    rs20   = compute_rs(df["Close"], spy_closes, i)

    # FIX: el slice original era iloc[i-LOOKBACK-1 : i-1], que EXCLUYE la barra de señal
    # (last = df.iloc[i-1]) del chequeo de "volumen decreciente" — mira solo las 3 barras
    # ESTRICTAMENTE anteriores a la señal. alert.py en cambio usa
    # df["Volume"].iloc[-(LOOKBACK+1):-1] sobre el df con la barra de hoy (en formacion)
    # al final, lo que equivale a incluir la barra de señal como la MAS RECIENTE de las 3
    # revisadas. Detectado recien al unificar ambos motores en scoring.py: con el slice
    # viejo, un mismo bar podia dar confluence/trigger_score distinto en vivo vs backtest
    # (hasta 0.5 puntos de score) sin que nada lo senalara. Alineado a la semantica de
    # alert.py (fuente de verdad en produccion): incluye la barra de señal.
    recent_vols = (
        df["Volume"].iloc[i - VOLUME_PROFILE_LOOKBACK: i].values
        if i >= VOLUME_PROFILE_LOOKBACK else np.array([])
    )

    core = scoring.evaluate_core(
        symbol, group, last, prev, rs20, vix_proxy, recent_vols, _CORE_PARAMS,
        breadth_pct=breadth_pct,
    )

    # ── Filtros finales (mismo gate que alert.py::StockSignal.should_alert) ────────
    if core.blocked:
        return None
    passes = scoring.passes_final_filters(
        symbol=symbol, group=group, signal_type=core.signal_type,
        score=core.total_score, rr=core.rr, blocked=core.blocked, rs20=rs20,
        require_playbook=REQUIRE_PLAYBOOK, min_score=MIN_SCORE, min_rr=MIN_RR,
        alert_etfs=ALERT_ETFS, final_rs_min=FINAL_RS_MIN,
        final_rs_min_by_group=FINAL_RS_MIN_BY_GROUP, etf_rs_floor=ETF_RS_FLOOR,
        index_etfs=frozenset(INDEX_ETFS), sector_etfs=frozenset(SECTOR_ETFS),
    )
    if not passes:
        return None

    # ── Construir registro ─────────────────────────────────────────────────
    trigger_dt = pd.Timestamp(df.index[i-1])
    if trigger_dt.tzinfo is None:
        trigger_dt = trigger_dt.tz_localize("UTC")
    trigger_str = trigger_dt.isoformat()

    setup_key  = f"{symbol}|{core.signal_type}|{trigger_str}|{core.entry:.2f}|{core.tp:.2f}|{core.stop:.2f}"
    setup_hash = hashlib.sha256(setup_key.encode()).hexdigest()

    return {
        "bar_index":       i,
        "trigger_dt":      trigger_dt,
        "symbol":          symbol,
        "name":            name,
        "group":           group,
        "playbook":        core.signal_type,
        "entry":           core.entry,
        "target":          round(core.tp, 2),
        "stop":             round(core.stop, 2),
        "rr":              round(core.rr, 2),
        "score":           core.total_score,
        "regime_score":    core.regime_score,
        "setup_score":     core.setup_score,
        "trigger_score":   core.trigger_score,
        "atr":             round(core.atr, 2),
        "adx":             round(core.adx, 2),
        "rsi":             round(core.rsi, 2),
        "rs20":            rs20,
        "extension_pct":   round(core.extension_pct, 2),
        "vol_ratio":       round(float(last["vol_ratio"]), 2),
        "pullback_atr":    round(core.pullback_atr, 2),
        "trend_quality":   core.trend_quality,
        "confluence_count": core.confluence_count,
        "vix_proxy":       vix_proxy,
        "setup_key":       setup_key,
        "setup_hash":      setup_hash,
        "reasons":         " | ".join(core.reasons[:8]),
        "warnings":        " | ".join(core.warnings[:4]),
    }


# ---------------------------------------------------------------------------
# Simulacion de outcome barra a barra tras la señal
# ---------------------------------------------------------------------------

def simulate_trade(df: pd.DataFrame, signal_bar: int, entry: float, target: float, stop: float, playbook: str = "") -> dict:
    """
    Itera sobre barras posteriores a signal_bar para detectar hit_target / hit_stop / expired.
    Usa High/Low de cada barra — conservador: si ambos se tocan en la misma barra, stop gana.
    v2.10: time-stop unico (solo breakout en sistema).
    v2.9: entrada en signal_bar+1 con Open (sin look-ahead).
    """
    n = len(df)
    max_bars = MAX_BARS_HOLD

    # v2.9 Fix #1: ENTRY EFECTIVO en signal_bar+1 (Open de la barra siguiente)
    # Antes: iteraba desde signal_bar — look-ahead, sobrestima win rate
    # Ahora: la senal se detecta al cierre de signal_bar, la orden se ejecuta
    # al Open de signal_bar+1 (siguiente dia de trading). Esto es lo que pasa
    # en la realidad y elimina el sesgo optimista.
    entry_bar = signal_bar + 1
    if entry_bar >= n:
        # No hay barra siguiente — descartar (raro, solo en el ultimo dia del df)
        return {
            "status": "no_entry", "bars_open": 0, "days_open": 0,
            "exit_price": entry, "exit_date": "", "exit_reason": "no_next_bar",
            "pnl_pct": 0.0, "mfe_pct": 0.0, "mae_pct": 0.0,
            "real_entry": entry,
        }

    # Precio de entrada REAL (Open del dia siguiente, no Close del dia de senal)
    real_entry = float(df["Open"].iloc[entry_bar])
    # FIX: se elimino "real_risk_per_share = real_entry - stop", que se calculaba aqui y
    # nunca se usaba (variable muerta). El riesgo real se recalcula donde corresponde —
    # build_report() y main(), a partir de las columnas price/stop/exit_price ya escritas
    # en el CSV — en vez de duplicar el calculo sin conectarlo al resto del pipeline.

    bars_open = 0
    mfe = 0.0   # max favorable excursion %
    mae = 0.0   # max adverse excursion %
    last_bar    = min(entry_bar + max_bars - 1, n - 1)
    # v2.12: si el historico termina antes del time-stop, el trade sigue ABIERTO (igual
    # que el tracker en vivo) — antes se marcaba "expired" al ultimo Close disponible y
    # entraba en la expectancy con un resultado parcial.
    exit_status = "expired" if entry_bar + max_bars <= n else "open"
    exit_price  = float(df["Close"].iloc[last_bar])
    exit_date   = pd.Timestamp(df.index[last_bar]).date().isoformat() if exit_status == "expired" else ""
    exit_reason = f"time_stop_{max_bars}_bars" if exit_status == "expired" else ""
    exit_bar    = last_bar

    # Iterar desde entry_bar (no desde signal_bar) — sin look-ahead
    for j in range(entry_bar, min(entry_bar + max_bars, n)):
        bar_open = float(df["Open"].iloc[j])
        bar_high = float(df["High"].iloc[j])
        bar_low  = float(df["Low"].iloc[j])
        bars_open += 1
        # v2.11: si la barra abre por debajo del stop (gap-through), la orden stop se
        # ejecuta al Open, no al nivel del stop. El target se deja en su nivel (conservador).
        stop_fill = min(stop, bar_open)

        # MFE/MAE calculados sobre real_entry (no entry teorico)
        mfe = max(mfe, (bar_high - real_entry) / max(real_entry, 1e-9) * 100)
        mae = min(mae, (bar_low  - real_entry) / max(real_entry, 1e-9) * 100)

        hit_stop   = bar_low  <= stop
        hit_target = bar_high >= target

        bar_date = pd.Timestamp(df.index[j])
        if bar_date.tzinfo is None:
            bar_date = bar_date.tz_localize("UTC")

        if hit_stop and hit_target:
            exit_status = "hit_stop"
            exit_price  = stop_fill
            exit_date   = bar_date.date().isoformat()
            exit_reason = "same_bar_both_stop_first"
            exit_bar    = j
            break
        if hit_stop:
            exit_status = "hit_stop"
            exit_price  = stop_fill
            exit_date   = bar_date.date().isoformat()
            exit_reason = "stop_hit"
            exit_bar    = j
            break
        if hit_target:
            exit_status = "hit_target"
            exit_price  = target
            exit_date   = bar_date.date().isoformat()
            exit_reason = "target_hit"
            exit_bar    = j
            break

    days_open = bars_open  # aprox 1 barra = 1 dia calendario de trading
    pnl_pct   = (exit_price - real_entry) / max(real_entry, 1e-9) * 100

    return {
        "status":      exit_status,
        "bars_open":   bars_open,
        "days_open":   days_open,
        "exit_price":  round(exit_price, 2),
        "exit_date":   exit_date,
        "exit_reason": exit_reason,
        "pnl_pct":     round(pnl_pct, 4),
        "mfe_pct":     round(mfe, 4),
        "mae_pct":     round(mae, 4),
        "real_entry":  round(real_entry, 4),  # entry efectivo (puede diferir del teorico por gap)
        "exit_bar":    exit_bar,
    }


# ---------------------------------------------------------------------------
# Backtesting de un simbolo completo
# ---------------------------------------------------------------------------

def backtest_symbol(
    symbol: str,
    df: pd.DataFrame,
    spy_closes: pd.Series,
    vix_df: Optional[pd.DataFrame],
    start_date: Optional[pd.Timestamp],
    breadth_map: Optional[dict[str, float]] = None,
    earnings_dates: Optional[list] = None,
) -> list[dict]:
    df = add_indicators(df)
    trades: list[dict] = []
    last_run_date = None             # fecha de corrida (barra i) de la ultima alerta — cooldown
    stop_exit_bars: list[int] = []   # barras donde cerro por stop un trade previo (post-stop cooldown)

    # Alinear VIX
    vix_map: dict[str, float] = {}
    if vix_df is not None and not vix_df.empty:
        for ts, row in vix_df.iterrows():
            d = pd.Timestamp(ts)
            if d.tzinfo is None:
                d = d.tz_localize("UTC")
            vix_map[d.date().isoformat()] = float(row["Close"])

    # Convencion de indices — v2.12 esquema "señal al cierre, entrada al Open siguiente":
    #   i-1 = barra de señal; alert.py corre despues del cierre de esa sesion (su
    #         ultima barra cerrada) y emite la alerta esa noche
    #   i   = sesion de entrada; la orden se ejecuta a su Open
    for i in range(220, len(df)):
        bar_dt = pd.Timestamp(df.index[i-1])
        if bar_dt.tzinfo is None:
            bar_dt = bar_dt.tz_localize("UTC")

        # Solo barras dentro del rango solicitado
        if start_date is not None and bar_dt < start_date:
            continue

        # La alerta se emite la noche de la barra de señal: cooldowns y earnings se miden
        # desde esa fecha, igual que el reloj del vivo.
        run_date = pd.Timestamp(df.index[i - 1]).date()

        # Cooldown entre alertas del mismo simbolo (alert.py: COOLDOWN_HOURS)
        if last_run_date is not None and (run_date - last_run_date).days < COOLDOWN_DAYS:
            continue

        # v2.12: post-stop cooldown (alert.py: POST_STOP_COOLDOWN_HOURS). Solo cuentan
        # stops ya ocurridos antes de la barra de señal — sin look-ahead sobre trades
        # que todavia estan abiertos en esta fecha.
        past_stops = [b for b in stop_exit_bars if b <= i - 1]
        if past_stops:
            last_stop_date = pd.Timestamp(df.index[max(past_stops)]).date()
            if (run_date - last_stop_date).days < POST_STOP_COOLDOWN_DAYS:
                continue

        # v2.12: earnings (alert.py: get_earnings_info). Bloquea si el proximo reporte
        # cae dentro de EARNINGS_BUFFER_DAYS dias calendario desde la noche de la señal.
        if earnings_dates and any(0 <= (e - run_date).days <= EARNINGS_BUFFER_DAYS for e in earnings_dates):
            continue

        # VIX proxy del dia
        vix_proxy = vix_map.get(bar_dt.date().isoformat(), 18.0)
        breadth_pct = breadth_map.get(bar_dt.date().isoformat()) if breadth_map else None

        sig = evaluate_bar(symbol, df, i, spy_closes, vix_proxy, breadth_pct=breadth_pct)
        if sig is None:
            continue

        # alert.py: tras un stop previo exige MIN_SCORE + POST_STOP_SCORE_PENALTY
        if past_stops and sig["score"] < MIN_SCORE + POST_STOP_SCORE_PENALTY:
            continue

        # alert.py no emite la alerta si no existe ningun Open valido (rango vacio)
        lo, hi = scoring.entry_open_range(
            sig["entry"], sig["stop"], sig["target"], sig["atr"],
            MIN_RR, MIN_ENTRY_RISK_ATR, GAP_BLOCK_PCT,
        )
        if lo > hi:
            continue

        # v2.12 FIX: la barra de señal es i-1 (evaluate_bar usa last = df.iloc[i-1]).
        # Antes se pasaba i, y simulate_trade entraba en i+1: un dia TARDE respecto del
        # vivo (que compra el Open del dia siguiente a la señal), salteando la primera
        # sesion del trade y midiendo el gap contra la apertura equivocada.
        outcome = simulate_trade(df, i - 1, sig["entry"], sig["target"], sig["stop"], sig.get("playbook", ""))

        # v2.9: descartar trades sin entrada efectiva
        if outcome["status"] == "no_entry":
            continue

        # En vivo la alerta ya se emitio (y seteo cooldown) aunque el Open luego la cancele.
        last_run_date = run_date

        # Gap + riesgo + R:R contra el Open real — mismo helper que el tracker de alert.py,
        # que marca la alerta como "cancelled" si el Open cae fuera de rango.
        real_entry = outcome.get("real_entry", sig["entry"])
        if scoring.check_entry_at_open(
            real_entry, sig["entry"], sig["stop"], sig["target"], sig["atr"],
            MIN_RR, MIN_ENTRY_RISK_ATR, GAP_BLOCK_PCT,
        ):
            continue

        # Ensamblar fila compatible con alerts_history.csv
        # v2.12 FIX: closed_utc era datetime.now() de la corrida del backtest — todos los
        # trades quedaban con la misma fecha (en el orden de generacion, por simbolo) y
        # advanced_analytics ordenaba por ella: equity curve, drawdown, rolling Sharpe y
        # "edge degradation" se calculaban en orden ALFABETICO, no cronologico. Ahora es
        # la fecha real de salida (vacio si el trade sigue abierto), como en el vivo.
        closed_str = f"{outcome['exit_date']}T20:00:00+00:00" if outcome["exit_date"] else ""
        row = {
            "timestamp_utc":     sig["trigger_dt"].isoformat(),
            "trigger_candle_utc":sig["trigger_dt"].isoformat(),
            "setup_key":         sig["setup_key"],
            "setup_hash":        sig["setup_hash"],
            "symbol":            symbol,
            "name":              sig["name"],
            "group":             sig["group"],
            "playbook":          sig["playbook"],
            "price":             _fmt(outcome.get("real_entry", sig["entry"])),  # v2.9: precio real de entrada
            # FIX (mejora institucional #2): columna espejo de alerts_history.csv, que
            # ahora tambien registra real_entry (Open real de la barra siguiente a la
            # señal) por separado de "price". Aca coinciden por construccion porque
            # "price" YA es el real_entry desde el Fix #1 de v2.9 — se duplica solo para
            # que ambos CSV compartan schema, tal como exige CLAUDE.md.
            "real_entry":        _fmt(outcome.get("real_entry", sig["entry"])),
            "target":            _fmt(sig["target"]),
            "stop":              _fmt(sig["stop"]),
            "rr":                _fmt(sig["rr"]),
            "score":             _fmt(sig["score"]),
            "regime_score":      _fmt(sig["regime_score"]),
            "setup_score":       _fmt(sig["setup_score"]),
            "trigger_score":     _fmt(sig["trigger_score"]),
            "atr":               _fmt(sig["atr"]),
            "adx":               _fmt(sig["adx"]),
            "rsi":               _fmt(sig["rsi"]),
            "rs20":              _fmt(sig["rs20"]),
            "extension_pct":     _fmt(sig["extension_pct"]),
            "reasons":           sig["reasons"],
            "warnings":          sig["warnings"],
            "blocked":           "",
            "status":            outcome["status"],
            "bars_open":         str(outcome["bars_open"]),
            "days_open":         str(outcome["days_open"]),
            "current_price":     _fmt(outcome["exit_price"]),
            "pnl_pct":           _fmt(outcome["pnl_pct"]),
            "mfe_pct":           _fmt(outcome["mfe_pct"]),
            "mae_pct":           _fmt(outcome["mae_pct"]),
            "exit_date":         outcome["exit_date"],
            "exit_price":        _fmt(outcome["exit_price"]),
            "exit_reason":       outcome["exit_reason"],
            "closed_utc":        closed_str,
            # extras ML
            "year":              str(bar_dt.year),
            "month":             str(bar_dt.month),
            "vol_ratio":         _fmt(sig["vol_ratio"]),
            "pullback_atr":      _fmt(sig["pullback_atr"]),
            "trend_quality":     _fmt(sig["trend_quality"]),
            "confluence_count":  str(sig["confluence_count"]),
            "adx_at_entry":      _fmt(sig["adx"]),
            "vix_proxy":         _fmt(vix_proxy),
        }

        trades.append(row)
        if outcome["status"] == "hit_stop":
            stop_exit_bars.append(outcome["exit_bar"])

    return trades


# ---------------------------------------------------------------------------
# Reporte de resultados
# ---------------------------------------------------------------------------

def _safe_mean(s: pd.Series) -> float:
    s = pd.to_numeric(s, errors="coerce").dropna()
    return float(s.mean()) if not s.empty else float("nan")


def expectancy_table(df: pd.DataFrame, by: str) -> pd.DataFrame:
    if df.empty or by not in df.columns:
        return pd.DataFrame()
    rows = []
    for key, g in df.groupby(by, dropna=False, observed=True):
        n = len(g)
        wins    = int(g["status"].eq("hit_target").sum())
        stops   = int(g["status"].eq("hit_stop").sum())
        expired = int(g["status"].eq("expired").sum())
        win_rate = wins / n if n else float("nan")
        avg_r    = _safe_mean(g["realized_r"])
        avg_rr   = _safe_mean(pd.to_numeric(g["rr"], errors="coerce"))
        avg_score= _safe_mean(pd.to_numeric(g["score"], errors="coerce"))
        avg_mfe  = _safe_mean(pd.to_numeric(g["mfe_pct"], errors="coerce"))
        avg_mae  = _safe_mean(pd.to_numeric(g["mae_pct"], errors="coerce"))
        rows.append({
            by: str(key), "n": n,
            "win_rate_%": round(win_rate * 100, 1),
            "stops_%": round(stops / n * 100, 1),
            "expired_%": round(expired / n * 100, 1),
            "avg_realized_R": round(avg_r, 3) if not np.isnan(avg_r) else "nan",
            "avg_rr": round(avg_rr, 2) if not np.isnan(avg_rr) else "nan",
            "avg_score": round(avg_score, 2) if not np.isnan(avg_score) else "nan",
            "avg_mfe_%": round(avg_mfe, 2) if not np.isnan(avg_mfe) else "nan",
            "avg_mae_%": round(avg_mae, 2) if not np.isnan(avg_mae) else "nan",
        })
    result = pd.DataFrame(rows)
    if not result.empty:
        result = result.sort_values("avg_realized_R", ascending=False)
    return result


def build_report(df: pd.DataFrame, outdir: Path, input_years: int) -> str:
    # Calcular realized_r
    df = df.copy()
    df["risk_dollars"]  = pd.to_numeric(df["price"], errors="coerce") - pd.to_numeric(df["stop"], errors="coerce")
    # FIX: la version anterior usaba "rr" (RR estructural, calculado sobre el cierre TEORICO
    # de la barra de senal) para trades hit_target. Pero "price" en este CSV es el real_entry
    # (Open real de la barra siguiente — ver Fix #1 de simulate_trade), asi que "rr" y "price"
    # tenian bases distintas: un gap de hasta 2% (el umbral del gap filter) entre el cierre
    # teorico y la apertura real se colaba sin corregir en el lado ganador de la distribucion,
    # inflando/desinflando arbitrariamente expectancy, Monte Carlo y equity curve. exit_price
    # ya contiene el precio de salida real para cualquier status, asi que una sola formula
    # basta: para hit_stop, exit_price es el stop (-1.0R) o el Open si hubo gap-through (< -1R).
    df["realized_r"] = (
        (pd.to_numeric(df["exit_price"], errors="coerce") - pd.to_numeric(df["price"], errors="coerce"))
        / (df["risk_dollars"] + 1e-9)
    )

    n         = len(df)
    wins      = int(df["status"].eq("hit_target").sum())
    stops     = int(df["status"].eq("hit_stop").sum())
    expired   = int(df["status"].eq("expired").sum())
    win_rate  = wins / n if n else 0
    avg_r     = _safe_mean(df["realized_r"])
    avg_rr    = _safe_mean(pd.to_numeric(df["rr"], errors="coerce"))
    expectancy= avg_r  # E[R] por trade

    lines = [
        "# Backtest Report — Stock Sentinel",
        "",
        f"- Años de histórico: **{input_years}**",
        f"- Universo: **{df['symbol'].nunique()} símbolos**",
        f"- Trades simulados: **{n}**",
        f"- Win rate: **{win_rate*100:.1f}%** ({wins}W / {stops}S / {expired}E)",
        f"- Avg Realized R: **{avg_r:.3f}R**",
        f"- Avg R:R estructural: **{avg_rr:.2f}x**",
        f"- Expectancy por trade: **{expectancy:.3f}R**",
        "",
    ]

    tables = {
        "Por playbook":       expectancy_table(df, "playbook"),
        "Por símbolo":        expectancy_table(df, "symbol"),
        "Por grupo":          expectancy_table(df, "group"),
        "Por año":            expectancy_table(df, "year"),
        "Por score bucket":   expectancy_table(
            df.assign(score_bucket=pd.cut(
                pd.to_numeric(df["score"], errors="coerce"),
                bins=[-np.inf, 5.79, 6.49, 7.49, 8.49, np.inf],
                labels=["<5.8","5.8-6.49","6.5-7.49","7.5-8.49","8.5+"]
            )), "score_bucket"),
        "Por RS bucket":      expectancy_table(
            df.assign(rs_bucket=pd.cut(
                pd.to_numeric(df["rs20"], errors="coerce"),
                bins=[-np.inf, 0, 2, 5, np.inf],
                labels=["<0","0-2","2-5","5+"]
            )), "rs_bucket"),
        "Por confluence":     expectancy_table(df, "confluence_count"),
    }

    for title, tbl in tables.items():
        lines.append(f"## {title}")
        lines.append("")
        if not tbl.empty:
            lines.append(tbl.to_markdown(index=False))
        else:
            lines.append("_sin datos_")
        lines.append("")
        # Guardar CSV
        safe = title.lower().replace(" ","_").replace("á","a").replace("ó","o").replace("ú","u").replace("é","e").replace("ñ","n")
        tbl.to_csv(outdir / f"bt_{safe}.csv", index=False)

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# v2.12: filtros del vivo replicados historicamente
# ---------------------------------------------------------------------------

def build_breadth_map(years: int) -> dict[str, float]:
    """% de ETFs sectoriales sobre su EMA200 por fecha — misma definicion que
    alert.py::compute_market_breadth(), pero para cada barra historica."""
    above_cols = []
    for sym in BREADTH_PROXY_SYMBOLS:
        df = fetch_data(sym, years=years)
        if df is None or len(df) < 200:
            continue
        close = df["Close"]
        ema200 = close.ewm(span=200, adjust=False).mean()
        idx = [pd.Timestamp(t).date().isoformat() for t in df.index]
        above_cols.append(pd.Series((close > ema200).values, index=idx, name=sym))
    if not above_cols:
        return {}
    above = pd.concat(above_cols, axis=1)
    pct = above.mean(axis=1, skipna=True) * 100.0
    return {d: round(float(v), 1) for d, v in pct.items()}


def fetch_earnings_dates(symbol: str) -> list:
    """Fechas historicas de earnings (yfinance, requiere lxml). ETFs no reportan.
    Si falla, se opera sin filtro para ese simbolo — mismo criterio que el vivo."""
    if symbol in INDEX_ETFS or symbol in SECTOR_ETFS:
        return []
    try:
        ed = yf.Ticker(symbol).get_earnings_dates(limit=28)
        if ed is None or ed.empty:
            return []
        return sorted({pd.Timestamp(t).date() for t in ed.index})
    except Exception as exc:
        log.warning("%s: earnings historicos no disponibles (%s) — sin filtro de earnings", symbol, exc)
        return []


def apply_correlation_guard(trades_df: pd.DataFrame) -> pd.DataFrame:
    """alert.py::CORRELATION_GUARD — una sola alerta por grupo por corrida, la de mayor
    rank_score. Aproximacion: se aplica por barra de señal (no re-libera el cooldown del
    simbolo descartado, que en vivo podria volver a alertar en la siguiente sesion)."""
    if trades_df.empty:
        return trades_df
    score = pd.to_numeric(trades_df["score"], errors="coerce")
    conf  = pd.to_numeric(trades_df["confluence_count"], errors="coerce").fillna(0)
    rs    = pd.to_numeric(trades_df["rs20"], errors="coerce").fillna(0)
    rank  = score * (1 + conf * 0.15) * (1 + rs.clip(lower=0) / 20)  # mismo rank_score que alert.py
    sig_day = trades_df["trigger_candle_utc"].astype(str).str[:10]
    keep = (
        trades_df.assign(_rank=rank, _day=sig_day)
        .sort_values("_rank", ascending=False)
        .drop_duplicates(subset=["_day", "group"], keep="first")
        .index
    )
    return trades_df.loc[sorted(keep)]


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Stock Sentinel Backtester")
    p.add_argument("--years",   type=int,   default=3,    help="Años de histórico (default: 3)")
    p.add_argument("--symbols", type=str,   default="",   help="Símbolos separados por coma (default: universo completo)")
    p.add_argument("--min-score", type=float, default=None)
    p.add_argument("--min-rr",    type=float, default=None)
    p.add_argument("--outdir",  type=str,   default="backtest_output")
    p.add_argument("--export-features", action="store_true", help="Exportar CSV con features para ML")
    return p.parse_args()


def main() -> None:
    args = parse_args()

    global MIN_SCORE, MIN_RR
    if args.min_score is not None:
        MIN_SCORE = args.min_score
    if args.min_rr is not None:
        MIN_RR = args.min_rr

    symbols = (
        [s.strip().upper() for s in args.symbols.split(",") if s.strip()]
        if args.symbols else list(STOCK_NAMES.keys())
    )

    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)

    start_date = pd.Timestamp.now(tz="UTC") - pd.DateOffset(years=args.years)
    log.info("Backtest | %s símbolos | %s años | MIN_SCORE=%.1f | MIN_RR=%.1f",
             len(symbols), args.years, MIN_SCORE, MIN_RR)

    # Descargar SPY y VIX una sola vez
    log.info("Descargando SPY...")
    spy_df = yf.Ticker("SPY").history(period=f"{args.years + 1}y", interval="1d", auto_adjust=True)
    spy_df = add_indicators(spy_df)
    spy_closes = spy_df["Close"]

    log.info("Descargando VIX...")
    try:
        vix_df = yf.Ticker("^VIX").history(period=f"{args.years + 1}y", interval="1d", auto_adjust=True)
    except Exception:
        vix_df = None
        log.warning("VIX no disponible — se usara proxy 18.0")

    breadth_map: dict[str, float] = {}
    if BREADTH_ENABLED:
        log.info("Calculando breadth historica (%s ETFs sectoriales)...", len(BREADTH_PROXY_SYMBOLS))
        breadth_map = build_breadth_map(args.years + 1)

    all_trades: list[dict] = []

    for symbol in symbols:
        log.info("Procesando %s...", symbol)
        df = fetch_data(symbol, years=args.years + 1)
        if df is None:
            log.warning("%s: sin datos suficientes, omitido", symbol)
            continue

        earnings = fetch_earnings_dates(symbol) if EARNINGS_FILTER_ENABLED else []
        trades = backtest_symbol(symbol, df, spy_closes, vix_df, start_date,
                                 breadth_map=breadth_map, earnings_dates=earnings)
        log.info("  %s: %s señales generadas", symbol, len(trades))
        all_trades.extend(trades)
        time.sleep(0.5)

    if not all_trades:
        log.warning("Sin trades generados. Revisa MIN_SCORE / MIN_RR / universo.")
        sys.exit(0)

    # Guardar CSV de trades
    trades_df = pd.DataFrame(all_trades)
    if CORRELATION_GUARD_ENABLED:
        n_before = len(trades_df)
        trades_df = apply_correlation_guard(trades_df).reset_index(drop=True)
        log.info("Correlation guard: %s -> %s trades", n_before, len(trades_df))
    trades_path = outdir / "backtest_trades.csv"
    trades_df.to_csv(trades_path, index=False)
    log.info("Trades guardados: %s (%s filas)", trades_path, len(trades_df))

    # v2.12: los trades aun abiertos al final del historico quedan en el CSV (igual que el
    # tracker en vivo) pero no entran en metricas — su resultado todavia no existe.
    n_open = int(trades_df["status"].eq("open").sum())
    if n_open:
        log.info("%s trades siguen abiertos al cierre del historico — excluidos de metricas", n_open)
    trades_df = trades_df[trades_df["status"] != "open"].reset_index(drop=True)

    # Reporte
    report_md = build_report(trades_df, outdir, args.years)
    report_path = outdir / "backtest_report.md"
    report_path.write_text(report_md, encoding="utf-8")
    log.info("Reporte: %s", report_path)

    # Feature export para ML
    if args.export_features:
        ml_cols = [
            "symbol","group","playbook","year","score","regime_score","setup_score",
            "trigger_score","rr","rsi","adx","rs20","extension_pct","vol_ratio",
            "pullback_atr","trend_quality","confluence_count","vix_proxy",
            "mfe_pct","mae_pct","status",
        ]
        available = [c for c in ml_cols if c in trades_df.columns]
        ml_df = trades_df[available].copy()
        ml_df["target_binary"] = (ml_df["status"] == "hit_target").astype(int)
        ml_path = outdir / "features_for_ml.csv"
        ml_df.to_csv(ml_path, index=False)
        log.info("Features ML exportadas: %s (%s columnas)", ml_path, len(available))

    # Resumen consola
    n = len(trades_df)
    wins   = int(trades_df["status"].eq("hit_target").sum())
    stops  = int(trades_df["status"].eq("hit_stop").sum())
    expired= int(trades_df["status"].eq("expired").sum())
    print(f"\n{'='*50}")
    print(f"BACKTEST COMPLETO")
    print(f"{'='*50}")
    print(f"Símbolos procesados : {trades_df['symbol'].nunique()}")
    print(f"Trades totales      : {n}")
    print(f"Win rate            : {wins/n*100:.1f}% ({wins}W / {stops}S / {expired}E)")
    # FIX: este resumen de consola usaba una TERCERA formula distinta a la de build_report()
    # (aqui trataba "expired" como 0.0R fijo, ignorando el pnl real de esas posiciones) y a
    # la de advanced_analytics.compute_realized_r. Unificadas las tres para que reporten el
    # mismo numero sobre el mismo dataset: (exit_price - price) / (price - stop).
    risk_dollars_summary = (
        pd.to_numeric(trades_df["price"], errors="coerce") - pd.to_numeric(trades_df["stop"], errors="coerce")
    )
    realized_r = (
        (pd.to_numeric(trades_df["exit_price"], errors="coerce") - pd.to_numeric(trades_df["price"], errors="coerce"))
        / (risk_dollars_summary + 1e-9)
    ).to_numpy()
    print(f"Avg Realized R      : {np.nanmean(realized_r):.3f}R")
    print(f"Expectancy          : {np.nanmean(realized_r):.3f}R/trade")
    print(f"\nSalidas en: {outdir}/")
    print(f"  - backtest_trades.csv")
    print(f"  - backtest_report.md")
    if args.export_features:
        print(f"  - features_for_ml.csv")


if __name__ == "__main__":
    main()
