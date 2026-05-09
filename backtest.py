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
    compute_supertrend_vectorized as _signals_supertrend,
)

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
# Universo (sincronizado con alert.py)
# ---------------------------------------------------------------------------
STOCK_NAMES: dict[str, str] = {
    "AAPL": "Apple Inc.",
    "MSFT": "Microsoft Corp.",
    "NVDA": "NVIDIA Corp.",
    "AMZN": "Amazon.com Inc.",
    "GOOGL": "Alphabet Inc.",
    "META": "Meta Platforms",
    "TSLA": "Tesla, Inc.",
    "BRK-B": "Berkshire Hathaway",
    "V": "Visa Inc.",
    "JPM": "JPMorgan Chase",
    "UNH": "UnitedHealth Group",
    "MA": "Mastercard Inc.",
    "AVGO": "Broadcom Inc.",
    "HD": "Home Depot Inc.",
    "PG": "Procter & Gamble",
    "COST": "Costco Wholesale",
}

STOCK_GROUPS: dict[str, str] = {
    "AAPL": "Tech", "MSFT": "Tech", "NVDA": "Tech", "AMZN": "Tech",
    "GOOGL": "Tech", "META": "Tech", "AVGO": "Tech",
    "TSLA": "Consumer", "HD": "Consumer", "PG": "Consumer", "COST": "Consumer",
    "JPM": "Finance", "V": "Finance", "MA": "Finance", "BRK-B": "Finance",
    "UNH": "Health",
}

# ---------------------------------------------------------------------------
# Parametros (sobreescribibles via env o args)
# ---------------------------------------------------------------------------
MIN_SCORE           = float(os.getenv("MIN_SCORE", "5.8"))
MIN_RR              = float(os.getenv("MIN_RR", "0.8"))
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
CONFLUENCE_THRESHOLD = int(os.getenv("CONFLUENCE_THRESHOLD", "3"))
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

# Backtest-especifico
# v2.7: Pullback Hardening (Backtest Fase B mostro pullback degradandose)
# v2.10: pullback eliminado del sistema

COOLDOWN_BARS       = int(os.getenv("BT_COOLDOWN_BARS", "5"))   # barras entre señales del mismo simbolo
MAX_BARS_HOLD       = int(os.getenv("BT_MAX_BARS_HOLD", "15"))  # time-stop
REQUIRE_PLAYBOOK    = True

# ---------------------------------------------------------------------------
# Schema CSV de salida (compatible con alerts_history.csv)
# ---------------------------------------------------------------------------
TRADE_COLUMNS = [
    "timestamp_utc", "trigger_candle_utc", "setup_key", "setup_hash",
    "symbol", "name", "group", "playbook",
    "price", "target", "stop", "rr", "score",
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

# ---------------------------------------------------------------------------
# Indicadores (copiado de alert.py — sin modificar para garantizar paridad)
# ---------------------------------------------------------------------------

def compute_supertrend_vectorized(df: pd.DataFrame, period: int = 10, multiplier: float = 3.0) -> pd.DataFrame:
    n = len(df)
    high  = df["High"].to_numpy(dtype=float)
    low   = df["Low"].to_numpy(dtype=float)
    close = df["Close"].to_numpy(dtype=float)

    tr = np.maximum(
        high - low,
        np.maximum(np.abs(high - np.roll(close, 1)), np.abs(low - np.roll(close, 1))),
    )
    tr[0] = high[0] - low[0]

    alpha = 1.0 / period
    rma = np.empty(n, dtype=float)
    rma[0] = tr[0]
    for i in range(1, n):
        rma[i] = alpha * tr[i] + (1.0 - alpha) * rma[i - 1]

    hl2 = (high + low) / 2.0
    upper_raw = hl2 + multiplier * rma
    lower_raw = hl2 - multiplier * rma

    upper = upper_raw.copy()
    lower = lower_raw.copy()
    trend = np.ones(n, dtype=float)
    st_value = np.empty(n, dtype=float)
    st_value[0] = upper_raw[0]

    for i in range(1, n):
        upper[i] = upper_raw[i] if (upper_raw[i] < upper[i-1] or close[i-1] > upper[i-1]) else upper[i-1]
        lower[i] = lower_raw[i] if (lower_raw[i] > lower[i-1] or close[i-1] < lower[i-1]) else lower[i-1]
        if trend[i-1] == -1.0:
            trend[i] = 1.0 if close[i] > upper[i-1] else -1.0
        else:
            trend[i] = -1.0 if close[i] < lower[i-1] else 1.0
        st_value[i] = lower[i] if trend[i] == 1.0 else upper[i]

    out = df.copy()
    out["st_atr"]      = rma
    out["st_upper"]    = upper
    out["st_lower"]    = lower
    out["st_trend"]    = trend
    out["st_value"]    = st_value
    return out


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
    # usamos i-1 como "last confirmed close" (anti look-ahead)
    asset_ret = (symbol_closes.iloc[i-1] / symbol_closes.iloc[i-1-RS_LOOKBACK] - 1.0) * 100
    spy_ret   = (spy_closes.iloc[i-1]   / spy_closes.iloc[i-1-RS_LOOKBACK]   - 1.0) * 100
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
) -> Optional[dict]:
    """
    Evalua la barra i usando datos hasta i inclusive.
    Retorna un dict con la señal o None si no hay señal.
    i >= 3 siempre (necesitamos last=i-1, prev=i-2 para ser consistentes
    con alert.py que usa iloc[-2] y iloc[-3] sobre el df completo).
    """
    if i < 220:
        return None

    last = df.iloc[i - 1]   # barra "cerrada" mas reciente (igual que alert.py iloc[-2])
    prev = df.iloc[i - 2]   # barra anterior                (igual que alert.py iloc[-3])

    group  = STOCK_GROUPS.get(symbol, "Other")
    name   = STOCK_NAMES.get(symbol, symbol)
    rs20   = compute_rs(df["Close"], spy_closes, i)

    entry      = float(last["Close"])
    atr        = max(float(last["atr"]), entry * 0.008)
    rsi        = float(last["rsi"])
    prev_rsi   = float(prev["rsi"])
    adx        = float(last["adx"])
    plus_di    = float(last["plus_di"])
    minus_di   = float(last["minus_di"])
    vol_ratio  = float(last["vol_ratio"])
    ema20      = float(last["ema20"])
    ema50      = float(last["ema50"])
    ema200     = float(last["ema200"])
    extension_pct = ((entry - ema200) / max(ema200, 1e-9)) * 100
    pullback_atr  = abs(entry - ema20) / max(atr, 1e-9)

    prior_high_5   = float(last["prior_high_5"])  if pd.notna(last["prior_high_5"])  else entry
    prior_high_20  = float(last["prior_high_20"]) if pd.notna(last["prior_high_20"]) else entry + 2*atr
    prior_low_5    = float(last["prior_low_5"])   if pd.notna(last["prior_low_5"])   else entry - 1.2*atr
    prior_swing_low= float(last["prior_low_12"])  if pd.notna(last["prior_low_12"])  else entry - 1.8*atr
    prior_low_20   = float(last["prior_low_20"])  if pd.notna(last["prior_low_20"])  else prior_swing_low

    st_trend_last  = int(last["st_trend"])  if pd.notna(last.get("st_trend"))  else 0
    st_trend_prev  = int(prev["st_trend"])  if pd.notna(prev.get("st_trend"))  else 0
    st_value_last  = float(last["st_value"]) if pd.notna(last.get("st_value")) else 0.0
    supertrend_bull     = st_trend_last == 1
    supertrend_cross_up = (st_trend_prev == -1) and (st_trend_last == 1)

    reasons:  list[str] = []
    warnings: list[str] = []
    blocked:  list[str] = []

    # ── Hard blocks ────────────────────────────────────────────────────────
    if vix_proxy >= VIX_BLOCK_LEVEL:
        blocked.append(f"VIX={vix_proxy:.1f} — mercado en panico")

    if SUPERTREND_BLOCK and not supertrend_bull and adx >= 20:
        blocked.append(f"Supertrend bajista (ST={st_value_last:.2f}, ADX={adx:.1f})")

    if extension_pct > 30:
        blocked.append(f"Precio sobreextendido: {extension_pct:.1f}% sobre EMA200")

    if rsi > 80:
        blocked.append(f"RSI extremo ({rsi:.1f})")

    if adx < WEAK_ADX_BLOCK:
        blocked.append(f"ADX={adx:.1f} < {WEAK_ADX_BLOCK:.0f}")
    elif plus_di <= minus_di and adx >= 18:
        blocked.append(f"Direccion bajista DI+={plus_di:.1f} <= DI-={minus_di:.1f}")

    # ── Regime score ───────────────────────────────────────────────────────
    regime_score = 0.0

    if entry > ema200:
        regime_score += 1.0
        reasons.append("Precio > EMA200")
    if ema50 > ema200:
        regime_score += 0.75
        reasons.append("EMA50 > EMA200")

    slope5 = float(last["ema200_slope_5"])
    slope3 = float(last["ema200_slope_3"]) if "ema200_slope_3" in last.index else slope5
    if slope5 > 0:
        if slope3 > 0 and slope5 >= slope3 * SLOPE_CONSISTENCY_RATIO:
            regime_score += 0.75
            reasons.append("EMA200 slope consistente")
        else:
            regime_score += 0.75 - SLOPE_WEAK_PENALTY
            warnings.append(f"EMA200 slope inconsistente ({slope5:.2f} vs {slope3:.2f})")
    else:
        regime_score -= 0.2
        warnings.append("EMA200 sin pendiente positiva")

    if supertrend_cross_up:
        regime_score += 1.2
        reasons.append("Supertrend cruce alcista")
    elif supertrend_bull:
        regime_score += 0.6
        reasons.append("Supertrend alcista")
    else:
        regime_score -= 0.5
        warnings.append("Supertrend bajista")

    di_total = plus_di + minus_di + 1e-9
    trend_quality = plus_di / di_total
    if plus_di > minus_di and adx >= 18:
        regime_score += round(1.0 * trend_quality * 2, 2)
        reasons.append(f"Direccionalidad ADX={adx:.1f} quality={trend_quality:.2f}")
    elif plus_di > minus_di and adx >= WEAK_ADX_BLOCK:
        regime_score += 0.4 * trend_quality * 2
        warnings.append(f"Direccionalidad debil ADX={adx:.1f}")
    elif adx >= 18:
        regime_score -= 0.4
        warnings.append(f"DI sin liderazgo DI+={plus_di:.1f} DI-={minus_di:.1f}")

    # ── Setup score ────────────────────────────────────────────────────────
    setup_score = 0.0

    # v2.0: deflacion cuadratica
    if extension_pct > 20:
        ext_penalty = 0.45 * ((extension_pct - 20) / 10.0) ** 2 + 0.45
        setup_score -= round(ext_penalty, 2)
        warnings.append(f"Extension {extension_pct:.1f}% (penalty={ext_penalty:.2f})")

    if rsi > BREAKOUT_RSI_MAX:
        setup_score -= 0.5
        warnings.append(f"RSI caliente ({rsi:.1f})")

    if 0.15 <= pullback_atr <= PULLBACK_MAX_ATR:
        setup_score += 0.8
    elif pullback_atr < 0.15:
        setup_score += 0.2
    elif pullback_atr <= BREAKOUT_MAX_ATR:
        setup_score -= 0.15
        warnings.append(f"Lejos de EMA20 ({pullback_atr:.2f} ATR)")
    else:
        setup_score -= 0.45
        warnings.append(f"Muy extendido EMA20 ({pullback_atr:.2f} ATR)")

    if SETUP_RSI_MIN <= rsi <= SETUP_RSI_MAX and rsi >= prev_rsi:
        setup_score += 1.0
        reasons.append(f"RSI zona ideal ({rsi:.1f})")
    elif SETUP_RSI_MAX < rsi <= BREAKOUT_RSI_MAX and adx >= 20:
        setup_score += 0.45
    elif 40 <= rsi < SETUP_RSI_MIN and rsi > prev_rsi:
        setup_score += 0.35
    else:
        setup_score -= 0.5
        warnings.append(f"RSI fuera de zona ({rsi:.1f})")

    if ema20 > ema50 and float(last["ema20_slope_3"]) > 0:
        setup_score += 0.8
        reasons.append("EMA20 > EMA50 con pendiente")
    elif entry > ema50:
        setup_score += 0.4
    else:
        setup_score -= 0.2
        warnings.append("Precio bajo EMA50")

    # v2.2: RS con group discount
    rs_group_discount = 0.5 if group in FINAL_RS_MIN_BY_GROUP else 1.0
    if symbol != "SPY":
        if rs20 > 1.0:
            setup_score += 0.9
            reasons.append(f"RS positiva {rs20:+.2f}%")
        elif rs20 > 0:
            setup_score += 0.4
        elif rs20 > -1.0:
            setup_score -= 0.2 * rs_group_discount
            warnings.append(f"RS plana {rs20:+.2f}% (grupo={group})")
        else:
            setup_score -= 0.7 * rs_group_discount
            warnings.append(f"RS negativa {rs20:+.2f}% (grupo={group})")

    # ── Trigger score ──────────────────────────────────────────────────────
    trigger_score = 0.0

    broke_prior_high_5  = entry > prior_high_5
    broke_prior_high_20 = entry > prior_high_20
    near_breakout       = entry >= prior_high_20 * BREAKOUT_NEAR_PCT
    bullish_reclaim     = entry > ema20 and float(prev["Close"]) <= float(prev["ema20"])
    positive_momentum   = float(last["macd_hist"]) > float(prev["macd_hist"])

    if broke_prior_high_5:
        trigger_score += 0.8
        reasons.append("Ruptura high reciente")
    elif bullish_reclaim:
        trigger_score += 0.5
        reasons.append("Reclaim EMA20")
    elif near_breakout:
        trigger_score += 0.35

    if supertrend_cross_up:
        trigger_score += 0.6
        reasons.append("Supertrend flip alcista")

    if positive_momentum and float(last["macd_hist"]) > 0:
        trigger_score += 0.8
        reasons.append("MACD hist acelerando >0")
    elif positive_momentum:
        trigger_score += 0.4

    if vol_ratio >= TRIGGER_VOL_RATIO:
        trigger_score += 0.8
        reasons.append(f"Vol confirmacion {vol_ratio:.2f}x")
    elif vol_ratio >= 0.95:
        trigger_score += 0.15
    else:
        trigger_score -= 0.4
        warnings.append(f"Vol flojo {vol_ratio:.2f}x")

    # v2.0: breakout ATR gate con vol dinamico
    effective_vol_gate = (
        BREAKOUT_EXT_VOL_LOW_VIX if vix_proxy < VIX_LOW_LEVEL else BREAKOUT_EXTENDED_VOL_RATIO
    )
    if pullback_atr > BREAKOUT_ATR_GATE and vol_ratio < effective_vol_gate:
        trigger_score -= 0.7
        warnings.append(f"Breakout extendido sin vol ({pullback_atr:.2f} ATR, {vol_ratio:.2f}x)")

    # v2.1: volume profile — 3 velas decrecientes
    if i >= VOLUME_PROFILE_LOOKBACK + 2:
        recent_vols = df["Volume"].iloc[i - VOLUME_PROFILE_LOOKBACK - 1: i - 1].values
        vol_decreasing = all(recent_vols[j] > recent_vols[j+1] for j in range(len(recent_vols)-1))
        if vol_decreasing:
            trigger_score -= VOLUME_PROFILE_PENALTY
            warnings.append("Vol decreciente 3 velas")

    # ── Playbook detection ─────────────────────────────────────────────────
    signal_type = "none"
    pullback_trend_strong = entry > ema200 and ema50 > ema200 and ema20 > ema50 and adx >= 18
    breakout_structure = (
        broke_prior_high_20
        or near_breakout
        or (broke_prior_high_5 and positive_momentum and trigger_score >= 1.6
            and entry >= prior_high_20 * 0.985)
    )
    # v2.10: solo breakout (pullback eliminado por backtest 0.009R)
    is_breakout = (
        breakout_structure and vol_ratio >= 0.95 and rs20 >= BREAKOUT_RS_MIN
        and adx >= 18 and rsi <= BREAKOUT_RSI_MAX
        and pullback_atr <= BREAKOUT_MAX_ATR and entry > ema50
    )
    if is_breakout:
        signal_type = "breakout"
        trigger_score += 1.2
        reasons.append("Playbook: Breakout Expansion")

    if signal_type == "none":
        setup_score -= 0.7
        warnings.append("Sin breakout valido")

    # ── VIX caution ────────────────────────────────────────────────────────
    score_adjustment = 0.0
    if VIX_CAUTION_LEVEL <= vix_proxy < VIX_BLOCK_LEVEL:
        score_adjustment -= 0.5

    # v2.1: confluence bonus
    confluence_signals = [
        broke_prior_high_5,
        bullish_reclaim,
        supertrend_cross_up,
        positive_momentum and float(last["macd_hist"]) > 0,
        vol_ratio >= TRIGGER_VOL_RATIO,
    ]
    confluence_count = sum(bool(s) for s in confluence_signals)
    if confluence_count >= CONFLUENCE_THRESHOLD:
        score_adjustment += CONFLUENCE_BONUS

    total_score = round(regime_score + setup_score + trigger_score + score_adjustment, 2)

    # ── R:R estructural ────────────────────────────────────────────────────
    range_20     = max(prior_high_20 - prior_low_20, 1.2 * atr)
    measured_move = max(0.75 * range_20, 1.6 * atr)

    if signal_type == "breakout":
        raw_stop = max(prior_high_5 - 0.30 * atr, ema20 - 0.35 * atr)
        stop = min(raw_stop, entry - 1.50 * atr, entry - 0.25 * atr)
        risk = entry - stop
        tp   = max(prior_high_20 + 0.20 * atr, entry + measured_move, entry + 1.25 * risk)
    elif signal_type == "hybrid":
        raw_stop = max(prior_low_5 - 0.20 * atr, ema20 - 0.45 * atr, entry - 1.05 * atr)
        stop = min(raw_stop, entry - 0.15 * atr)
        risk = entry - stop
        tp   = max(prior_high_20 + 0.15 * atr, entry + max(0.60 * range_20, 1.5 * atr), entry + 1.20 * risk)
    elif signal_type == "pullback":
        raw_stop = min(prior_swing_low - 0.12 * atr, ema50 - 0.12 * atr, entry - 0.80 * atr)
        stop = min(raw_stop, entry - 0.15 * atr)
        risk = entry - stop
        tp   = max(prior_high_20 + 0.10 * atr, entry + max(0.55 * range_20, 1.3 * atr), entry + 1.15 * risk)
    else:
        raw_stop = min(prior_swing_low - 0.10 * atr, ema50 - 0.15 * atr, entry - 0.90 * atr)
        stop = min(raw_stop, entry - 0.15 * atr)
        risk = entry - stop
        tp   = max(entry + 1.00 * atr, prior_high_20)

    min_risk = max(0.22 * atr, entry * 0.002)
    if risk < min_risk:
        stop = entry - min_risk
        risk = min_risk

    if stop >= entry:
        blocked.append("Stop invalido")
        stop = entry - max(0.90 * atr, entry * 0.003)
        risk = entry - stop
    if tp <= entry:
        blocked.append("TP invalido")
        tp = entry + max(1.20 * atr, 0.60 * range_20)

    rr = (tp - entry) / max(risk, 1e-9)

    # v2.0: adaptive MIN_RR
    effective_min_rr = MIN_RR
    if extension_pct > ADAPTIVE_RR_EXT_THRESHOLD:
        effective_min_rr = round(MIN_RR * ADAPTIVE_RR_MULTIPLIER, 2)
    if rr < effective_min_rr and extension_pct > ADAPTIVE_RR_EXT_THRESHOLD:
        blocked.append(f"Adaptive RR {rr:.2f} < {effective_min_rr:.2f}")

    # ── Filtros finales ────────────────────────────────────────────────────
    if blocked:
        return None
    if total_score < MIN_SCORE:
        return None
    if rr < MIN_RR:
        return None
    if REQUIRE_PLAYBOOK and signal_type != "breakout":
        return None
    rs_min = FINAL_RS_MIN_BY_GROUP.get(group, FINAL_RS_MIN)
    if rs20 < rs_min:
        return None

    # ── Construir registro ─────────────────────────────────────────────────
    trigger_dt = pd.Timestamp(df.index[i-1])
    if trigger_dt.tzinfo is None:
        trigger_dt = trigger_dt.tz_localize("UTC")
    trigger_str = trigger_dt.isoformat()

    setup_key  = f"{symbol}|{signal_type}|{trigger_str}|{entry:.2f}|{tp:.2f}|{stop:.2f}"
    setup_hash = hashlib.sha256(setup_key.encode()).hexdigest()

    return {
        "bar_index":       i,
        "trigger_dt":      trigger_dt,
        "symbol":          symbol,
        "name":            name,
        "group":           group,
        "playbook":        signal_type,
        "entry":           entry,
        "target":          round(tp, 2),
        "stop":            round(stop, 2),
        "rr":              round(rr, 2),
        "score":           total_score,
        "regime_score":    round(regime_score, 2),
        "setup_score":     round(setup_score, 2),
        "trigger_score":   round(trigger_score, 2),
        "atr":             round(atr, 2),
        "adx":             round(adx, 2),
        "rsi":             round(rsi, 2),
        "rs20":            rs20,
        "extension_pct":   round(extension_pct, 2),
        "vol_ratio":       round(vol_ratio, 2),
        "pullback_atr":    round(pullback_atr, 2),
        "trend_quality":   round(trend_quality, 2),
        "confluence_count": confluence_count,
        "vix_proxy":       vix_proxy,
        "setup_key":       setup_key,
        "setup_hash":      setup_hash,
        "reasons":         " | ".join(reasons[:8]),
        "warnings":        " | ".join(warnings[:4]),
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
    # Recalcular riesgo con el precio real (gap puede cambiarlo)
    real_risk_per_share = real_entry - stop

    bars_open = 0
    mfe = 0.0   # max favorable excursion %
    mae = 0.0   # max adverse excursion %
    exit_status = "expired"
    exit_price  = float(df["Close"].iloc[min(entry_bar + max_bars - 1, n - 1)])
    exit_date   = ""
    exit_reason = f"time_stop_{max_bars}_bars"

    # Iterar desde entry_bar (no desde signal_bar) — sin look-ahead
    for j in range(entry_bar, min(entry_bar + max_bars, n)):
        bar_high = float(df["High"].iloc[j])
        bar_low  = float(df["Low"].iloc[j])
        bars_open += 1

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
            exit_price  = stop
            exit_date   = bar_date.date().isoformat()
            exit_reason = "same_bar_both_stop_first"
            break
        if hit_stop:
            exit_status = "hit_stop"
            exit_price  = stop
            exit_date   = bar_date.date().isoformat()
            exit_reason = "stop_hit"
            break
        if hit_target:
            exit_status = "hit_target"
            exit_price  = target
            exit_date   = bar_date.date().isoformat()
            exit_reason = "target_hit"
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
) -> list[dict]:
    df = add_indicators(df)
    trades: list[dict] = []
    last_signal_bar = -999  # para cooldown entre señales

    # Alinear VIX
    vix_map: dict[str, float] = {}
    if vix_df is not None and not vix_df.empty:
        for ts, row in vix_df.iterrows():
            d = pd.Timestamp(ts)
            if d.tzinfo is None:
                d = d.tz_localize("UTC")
            vix_map[d.date().isoformat()] = float(row["Close"])

    for i in range(220, len(df) - 1):
        bar_dt = pd.Timestamp(df.index[i-1])
        if bar_dt.tzinfo is None:
            bar_dt = bar_dt.tz_localize("UTC")

        # Solo barras dentro del rango solicitado
        if start_date is not None and bar_dt < start_date:
            continue

        # Cooldown entre señales del mismo simbolo
        if (i - last_signal_bar) < COOLDOWN_BARS:
            continue

        # VIX proxy del dia
        vix_proxy = vix_map.get(bar_dt.date().isoformat(), 18.0)

        sig = evaluate_bar(symbol, df, i, spy_closes, vix_proxy)
        if sig is None:
            continue

        # v2.9: Pasamos la barra de senal directamente. simulate_trade entra en signal_bar+1 (Open)
        outcome = simulate_trade(df, i, sig["entry"], sig["target"], sig["stop"], sig.get("playbook", ""))

        # v2.9: descartar trades sin entrada efectiva o con gap excesivo
        if outcome["status"] == "no_entry":
            continue

        # v2.9 Fix #8: filtro de gap aplicado al precio real de entrada
        real_entry = outcome.get("real_entry", sig["entry"])
        gap_pct = abs((real_entry - sig["entry"]) / max(sig["entry"], 1e-9)) * 100.0
        if gap_pct > 2.0:  # mismo umbral que GAP_BLOCK_PCT del live
            continue

        # Ensamblar fila compatible con alerts_history.csv
        now_str = datetime.now(timezone.utc).isoformat()
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
            "closed_utc":        now_str,
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
        last_signal_bar = i

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
    df["realized_r"]    = np.where(
        df["status"] == "hit_target", pd.to_numeric(df["rr"], errors="coerce"),
        np.where(df["status"] == "hit_stop", -1.0,
        (pd.to_numeric(df["exit_price"], errors="coerce") - pd.to_numeric(df["price"], errors="coerce"))
        / (df["risk_dollars"] + 1e-9))
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

    all_trades: list[dict] = []

    for symbol in symbols:
        log.info("Procesando %s...", symbol)
        df = fetch_data(symbol, years=args.years + 1)
        if df is None:
            log.warning("%s: sin datos suficientes, omitido", symbol)
            continue

        trades = backtest_symbol(symbol, df, spy_closes, vix_df, start_date)
        log.info("  %s: %s señales generadas", symbol, len(trades))
        all_trades.extend(trades)
        time.sleep(0.5)

    if not all_trades:
        log.warning("Sin trades generados. Revisa MIN_SCORE / MIN_RR / universo.")
        sys.exit(0)

    # Guardar CSV de trades
    trades_df = pd.DataFrame(all_trades)
    trades_path = outdir / "backtest_trades.csv"
    trades_df.to_csv(trades_path, index=False)
    log.info("Trades guardados: %s (%s filas)", trades_path, len(trades_df))

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
    realized_r = np.where(
        trades_df["status"] == "hit_target", pd.to_numeric(trades_df["rr"], errors="coerce"),
        np.where(trades_df["status"] == "hit_stop", -1.0, 0.0)
    )
    print(f"Avg Realized R      : {np.nanmean(realized_r):.3f}R")
    print(f"Expectancy          : {np.nanmean(realized_r):.3f}R/trade")
    print(f"\nSalidas en: {outdir}/")
    print(f"  - backtest_trades.csv")
    print(f"  - backtest_report.md")
    if args.export_features:
        print(f"  - features_for_ml.csv")


if __name__ == "__main__":
    main()
