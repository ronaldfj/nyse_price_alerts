
"""
Stock Sentinel Bot — Alertas técnicas para NYSE/Nasdaq
Iteración 2.1:
  === Iteración 2.0 — Entry Quality Filter ===
  - Breakout ATR Gate: vol_ratio >= BREAKOUT_EXTENDED_VOL_RATIO si pullback_atr > BREAKOUT_ATR_GATE
  - Score deflation cuadratica para extensiones sobre EMA200 (reemplaza penalizacion lineal)
  - Regime score cap: EMA200 slope inconsistente (slope5 vs slope3) reduce peso del regimen
  - Re-entry cooldown dinamico: tras hit_stop -> 72h + MIN_SCORE+1.0 por simbolo
  - should_suppress_by_history_v2: lee exit_reason del CSV para aplicar cooldown diferenciado

  === Iteracion 2.1 — Multi-Signal Confluence + Adaptive Scoring ===

  === Iteracion 2.2 — Group-Aware RS Thresholds + Dynamic Vol Gate ===

  === Iteracion 2.3 — Backtest-Driven Calibration ===

  === Iteracion 2.4 — Expanded Universe (46 simbolos) ===
  - Tech: +AMD, CRM, NOW, ORCL, ANET
  - Finance: +GS, AXP
  - Health: +LLY, ABT, ISRG
  - Consumer: +NKE, MCD
  - Industrial: CAT, HON, DE, LMT (nuevo grupo)
  - Energy: XOM, CVX (nuevo grupo)
  - ETFs sectoriales: XLK, XLF, XLV, XLI, XLE, XLP

  === Iteracion 2.10 — Sistema Breakout Puro ===
  Decision basada en backtest post-v2.9:
  - breakout: 0.269R con costos, 249 trades, edge robusto
  - pullback: 0.009R con costos, 21 trades, expectancy practicamente nula
  - El edge esta enteramente en breakout. Pullback solo agrega complejidad sin valor.
  Cambios:
  - Eliminada toda logica de detectar/scorear pullback
  - Eliminadas env vars PULLBACK_* (5 vars + sizing factor)
  - signal_type ahora siempre es "breakout" o "none" (no mas "pullback")
  - Tracker simplificado: TRACKER_MAX_BARS_OPEN unico para todos
  - Sizing simplificado: 1x para todos los breakouts (sin factor reducido)

  === Iteracion 2.9 — Refactor + Fix Look-Ahead (Auditoria Externa) ===
  Hallazgos criticos resueltos de revision externa:
  - Fix #1: simulate_trade entra en signal_bar+1 con Open (no signal_bar) — antes
            habia look-ahead que sobrestimaba win rate y subestimaba stops
  - Fix #2: signals.py modulo compartido — add_indicators y compute_relative_strength
            ahora son UNICA fuente de verdad para alert.py y backtest.py
  - Fix #8: backtest aplica gap filter (>2%) sobre el real_entry para descartar
            trades donde el precio teorico no representa la entrada real

  === Iteracion 2.8 — Clasificacion Fija + Sizing Diferenciado ===
  Decision arquitectonica post-v2.7: pullback como playbook secundario, no contaminante.
  - Cascada de clasificacion fija: pullback PRIMERO (estricto) -> breakout -> descartado
  - Pullback que califica = pullback (no se reclasifica como breakout)
  - Breakout solo entra si cumple sus reglas originales (sin contaminacion)
  - Hybrid eliminado completamente (no hay caso else que lo genere)
  - PULLBACK_SIZING_FACTOR = 0.5 fijo (mitad de riesgo de breakout)
  - Filtros pullback relajados de v2.7: confluence>=2, RS>=0%, ADX>=18, score+0.3

  === Iteracion 2.7 — Pullback Hardening (Backtest-Driven) ===
  Decision basada en compare_playbooks Fase B:
  - breakout: 0.319R (edge mejorando +0.105)
  - pullback: 0.121R (edge degradandose -0.138)
  - hybrid:   -0.261R (eliminado en v2.3)
  Mantenemos ambos para diversificacion temporal pero endurecemos pullback:
  - PULLBACK_MIN_CONFLUENCE: 3 (vs 2 global) — solo pullbacks con catalizadores
  - PULLBACK_MIN_RS: 1.0% (vs 0% global) — solo activos con liderazgo
  - PULLBACK_MIN_ADX: 20 (vs 15 global) — solo tendencias fuertes
  - PULLBACK_MIN_SCORE: MIN_SCORE + 0.5 — barra mas alta para pullback
  - PULLBACK_MAX_BARS: 12 (vs 20 global) — corta trades estancados rapido

  === Iteracion 2.6 — Quality Hardening (post-XLP false positive) ===
  Fixes basados en alerta XLP que paso siendo de baja calidad:
  - Fix #1: confluence_count <2 = hard block, <3 = penalty -0.5 (antes sin penalty)
  - Fix #2: Supertrend bajista ahora bloquea con ADX>=15 (antes >=20)
  - Fix #3: Supertrend bajista + RS<0 = hard block automatico (cualquier ADX)
  - Fix #4: Sector ETFs requieren RS minimo absoluto (ETF_RS_FLOOR=-3%)

  === Iteracion 2.5 — Bug Fixes + Quality Filters + Risk Sizing ===
  BUGS:
  - Fix #1: post-stop cooldown solo cuenta trades cerrados (no abiertos)
  - Fix #2: alineacion temporal asset vs SPY en compute_relative_strength
  - Fix #3: get_earnings_info con fallback robusto + advertencia visible si falla
  - Fix #4: descarga batch de yfinance (40 simbolos en 1 request, no 40)
  - Fix #5: cooldown lee max(state, history) — robusto a perdida de state.json
  MEJORAS:
  - #6:  filtro breadth de mercado — % SP500 sobre EMA200 (skip si <50%)
  - #7:  position sizing — sugiere # acciones para riesgo de 1% sobre cuenta configurable
  - #8:  gap filter — bloquea si gap intraday >2% vs cierre anterior (entry invalida)
  - #9:  ranking de alertas — score * confluence_count * (1 + rs20/10)
  - #10: correlation guard — solo 1 alerta por sector por dia (top-ranked gana)
  - #11: trailing stop sugerido — entry + max(0.5*ATR, EMA20) como guia post-trade
  - #12: RSI Wilder canonico documentado (alpha=1/14 vs com=13 — equivalentes)
  - Confluence threshold subido a 4 (backtest: confluence=4 -> 68.4% WR, 0.997R)
  - Hybrid playbook deshabilitado (backtest: avg_R=-0.208, stop rate 73.3%)
  - TSLA y PG excluidos del universo (TSLA avg_R=-0.086 stop=60%, PG avg_R=-0.166 stop=59%)
    NOTA v2.10: TSLA re-agregada al universo (decision consciente del usuario, no
    un descuido de este aviso) — el scoring/parametros cambiaron sustancialmente
    desde v2.5. PG sigue excluida. No hay backtest nuevo que confirme el edge de
    TSLA bajo v2.10; si empieza a generar alertas en vivo, vigilar de cerca via
    /analyze antes de confiar en el tamaño de posicion sugerido.
  - TRACKER_MAX_BARS_OPEN=20 para capturar mas pullbacks (expired=43% en pullback)
  - Confluence=5 penaliza en vez de bonificar (backtest: 0% WR, avg_R=-0.543)
  - CONFLUENCE_BONUS: score +0.5 cuando >=3 confluencias de entrada activas
  - TREND_QUALITY_SCORE: ratio DI+/(DI++DI-) pondera regime_score de forma continua
  - Adaptive MIN_RR: sube a MIN_RR * 1.25 si extension_pct > 20
  - VOLUME_PROFILE_FILTER: penaliza volumen decreciente en ultimas 3 velas (distribucion)
  - Score por capas: regime / setup / trigger (heredado de 1.5)
  - Hard blocks solo para riesgo real
  - Dos playbooks: pullback continuation / breakout expansion
  - R:R estructural usando swing low + rango reciente
  - Relative strength simple vs SPY (20 sesiones)
  - Soporte a market_context_stocks.json por defecto
  - DRY_RUN para pruebas sin Telegram
  - Tracker automatico de outcomes: open / hit_target / hit_stop / expired
  - Idempotencia por setup_hash + fallback de cooldown desde CSV
"""

from __future__ import annotations

import csv
import hashlib
import json
import logging
import os
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import pandas as pd
import requests
import yfinance as yf

# v2.9: importar indicadores desde modulo compartido (UNICA fuente de verdad)
from signals import (
    add_indicators as _signals_add_indicators,
    compute_relative_strength as _signals_compute_rs,
)
# FIX (mejora institucional #1): motor de scoring/filtros compartido con backtest.py.
# Antes, evaluate_stock() (aca) y evaluate_bar() (backtest.py) duplicaban ~250 lineas de
# logica identica que fue divergiendo silenciosamente iteracion a iteracion — ver
# scoring.py para el detalle completo de que se desincronizo y por que importa.
import scoring

# ── Logging ───────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("stock-sentinel-v2")

# ── Universo de acciones ──────────────────────────────────────────────────────
STOCK_NAMES = {
    # ── Tech ──────────────────────────────────────────────────────────────
    "AAPL": "Apple Inc.",
    "MSFT": "Microsoft Corp.",
    "NVDA": "NVIDIA Corp.",
    "AMZN": "Amazon.com Inc.",
    "GOOGL": "Alphabet Inc.",
    "META": "Meta Platforms",
    "AVGO": "Broadcom Inc.",
    "AMD":  "Advanced Micro Devices",
    "CRM":  "Salesforce Inc.",
    "NOW":  "ServiceNow Inc.",
    "ORCL": "Oracle Corp.",
    "ANET": "Arista Networks",
    # ── Tech / Cybersecurity ──────────────────────────────────────────────
    "PANW": "Palo Alto Networks",
    "CRWD": "CrowdStrike Holdings",
    "FTNT": "Fortinet Inc.",
    "ZS":   "Zscaler Inc.",
    "OKTA": "Okta Inc.",
    # CYBR (CyberArk) excluida: adquirida por PANW en 2025, deslistada — yfinance
    # devuelve 404/"possibly delisted" (verificado 2026-07-09).
    # ── Finance ───────────────────────────────────────────────────────────
    "JPM":  "JPMorgan Chase",
    "V":    "Visa Inc.",
    "MA":   "Mastercard Inc.",
    "BRK-B":"Berkshire Hathaway",
    "GS":   "Goldman Sachs",
    "AXP":  "American Express",
    # ── Health ────────────────────────────────────────────────────────────
    "UNH":  "UnitedHealth Group",
    "LLY":  "Eli Lilly & Co.",
    "ABT":  "Abbott Laboratories",
    "ISRG": "Intuitive Surgical",
    # ── Consumer / Retail ─────────────────────────────────────────────────
    "HD":   "Home Depot Inc.",
    "COST": "Costco Wholesale",
    "NKE":  "Nike Inc.",
    "MCD":  "McDonald's Corp.",
    "TSLA": "Tesla Inc.",
    # ── Industrial ────────────────────────────────────────────────────────
    "CAT":  "Caterpillar Inc.",
    "HON":  "Honeywell Intl.",
    "DE":   "Deere & Company",
    "LMT":  "Lockheed Martin",
    # ── Energy ────────────────────────────────────────────────────────────
    "XOM":  "Exxon Mobil Corp.",
    "CVX":  "Chevron Corp.",
    # ── ETFs — índices ────────────────────────────────────────────────────
    "SPY":  "S&P 500 ETF",
    "QQQ":  "Nasdaq 100 ETF",
    # ── ETFs — sectoriales ────────────────────────────────────────────────
    "XLK":  "Tech Sector ETF",
    "XLF":  "Finance Sector ETF",
    "XLV":  "Health Sector ETF",
    "XLI":  "Industrial Sector ETF",
    "XLE":  "Energy Sector ETF",
    "XLP":  "Consumer Staples ETF",
}

STOCK_GROUPS = {
    # Tech
    "AAPL": "Tech", "MSFT": "Tech", "NVDA": "Tech", "AMZN": "Tech",
    "GOOGL": "Tech", "META": "Tech", "AVGO": "Tech", "AMD": "Tech",
    "CRM": "Tech", "NOW": "Tech", "ORCL": "Tech", "ANET": "Tech",
    "PANW": "Tech", "CRWD": "Tech", "FTNT": "Tech", "ZS": "Tech",
    "OKTA": "Tech",
    # Finance
    "JPM": "Finance", "V": "Finance", "MA": "Finance",
    "BRK-B": "Finance", "GS": "Finance", "AXP": "Finance",
    # Health
    "UNH": "Health", "LLY": "Health", "ABT": "Health", "ISRG": "Health",
    # Consumer
    "HD": "Consumer", "COST": "Consumer", "NKE": "Consumer", "MCD": "Consumer",
    "TSLA": "Consumer",
    # Industrial
    "CAT": "Industrial", "HON": "Industrial", "DE": "Industrial", "LMT": "Industrial",
    # Energy
    "XOM": "Energy", "CVX": "Energy",
    # ETF
    "SPY": "ETF", "QQQ": "ETF",
    "XLK": "ETF", "XLF": "ETF", "XLV": "ETF",
    "XLI": "ETF", "XLE": "ETF", "XLP": "ETF",
}
STOCKS = list(STOCK_NAMES.keys())

# ── Configuración ─────────────────────────────────────────────────────────────
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")
STATE_FILE = os.getenv("STOCK_STATE_FILE", "stock_state.json")
ALERTS_HISTORY_FILE = os.getenv("ALERTS_HISTORY_FILE", "alerts_history.csv")
DRY_RUN = os.getenv("DRY_RUN", "false").lower() == "true"

MIN_SCORE = float(os.getenv("MIN_SCORE", "5.8"))
MIN_RR = float(os.getenv("MIN_RR", "1.6"))
COOLDOWN = int(os.getenv("COOLDOWN_HOURS", "48")) * 3600
EARNINGS_BUFFER_DAYS = int(os.getenv("EARNINGS_BUFFER_DAYS", "5"))
VIX_BLOCK_LEVEL = float(os.getenv("VIX_BLOCK_LEVEL", "30.0"))
VIX_CAUTION_LEVEL = float(os.getenv("VIX_CAUTION_LEVEL", "22.0"))
TRIGGER_VOL_RATIO = float(os.getenv("TRIGGER_VOL_RATIO", "1.00"))
BREAKOUT_VOL_HARD_GATE = float(os.getenv("BREAKOUT_VOL_HARD_GATE", "0"))  # v2.11: 0 = desactivado
SETUP_RSI_MIN = float(os.getenv("SETUP_RSI_MIN", "45"))
SETUP_RSI_MAX = float(os.getenv("SETUP_RSI_MAX", "66"))
BREAKOUT_RSI_MAX = float(os.getenv("BREAKOUT_RSI_MAX", "76"))
RS_LOOKBACK = int(os.getenv("RS_LOOKBACK", "20"))
SWING_LOOKBACK = int(os.getenv("SWING_LOOKBACK", "12"))
PULLBACK_MAX_ATR = float(os.getenv("PULLBACK_MAX_ATR", "1.20"))
BREAKOUT_MAX_ATR = float(os.getenv("BREAKOUT_MAX_ATR", "3.20"))
WEAK_ADX_BLOCK = float(os.getenv("WEAK_ADX_BLOCK", "15.0"))
BREAKOUT_RS_MIN = float(os.getenv("BREAKOUT_RS_MIN", "-0.5"))
BREAKOUT_NEAR_PCT = float(os.getenv("BREAKOUT_NEAR_PCT", "0.995"))
FINAL_RS_MIN = float(os.getenv("FINAL_RS_MIN", "0.0"))

# v2.2: RS minima por grupo — Finance/Health suelen rezagarse estructuralmente vs SPY
# Formato: "GROUP:valor,GROUP:valor" — grupos sin entry usan FINAL_RS_MIN global
FINAL_RS_MIN_BY_GROUP_RAW = os.getenv("FINAL_RS_MIN_BY_GROUP", "Finance:-4.0,Health:-4.0,Consumer:-2.0,Industrial:-2.0,Energy:-3.0")
FINAL_RS_MIN_BY_GROUP: dict[str, float] = {}
for _entry in FINAL_RS_MIN_BY_GROUP_RAW.split(","):
    _parts = _entry.strip().split(":")
    if len(_parts) == 2:
        try:
            FINAL_RS_MIN_BY_GROUP[_parts[0].strip()] = float(_parts[1].strip())
        except ValueError:
            pass

# v2.2: Vol gate dinamico segun VIX — relaja BREAKOUT_EXTENDED_VOL_RATIO en mercados tranquilos
VIX_LOW_LEVEL = float(os.getenv("VIX_LOW_LEVEL", "18.0"))
BREAKOUT_EXTENDED_VOL_RATIO_LOW_VIX = float(os.getenv("BREAKOUT_EXTENDED_VOL_RATIO_LOW_VIX", "1.5"))
ALERT_ETFS = os.getenv("ALERT_ETFS", "false").lower() == "true"
# v2.4: ETFs sectoriales alertan siempre — solo SPY/QQQ como benchmark puro se excluyen
SECTOR_ETFS = {"XLK", "XLF", "XLV", "XLI", "XLE", "XLP"}
INDEX_ETFS   = {"SPY", "QQQ"}
REQUIRE_PLAYBOOK = os.getenv("REQUIRE_PLAYBOOK", "true").lower() == "true"
TRACKER_MAX_BARS_OPEN = int(os.getenv("TRACKER_MAX_BARS_OPEN", "20"))  # v2.3: pullback expired=43% con 15
TRACKER_ENABLED = os.getenv("TRACKER_ENABLED", "true").lower() == "true"
HISTORY_COOLDOWN_FALLBACK = os.getenv("HISTORY_COOLDOWN_FALLBACK", "true").lower() == "true"
SUPERTREND_PERIOD = int(os.getenv("SUPERTREND_PERIOD", "10"))
SUPERTREND_MULTIPLIER = float(os.getenv("SUPERTREND_MULTIPLIER", "3.0"))
SUPERTREND_REGIME_BLOCK = os.getenv("SUPERTREND_REGIME_BLOCK", "true").lower() == "true"

# -- Iteracion 2.0 -- Entry Quality Filter -----------------------------------
BREAKOUT_ATR_GATE = float(os.getenv('BREAKOUT_ATR_GATE', '2.0'))
BREAKOUT_EXTENDED_VOL_RATIO = float(os.getenv('BREAKOUT_EXTENDED_VOL_RATIO', '1.8'))
POST_STOP_COOLDOWN = int(os.getenv('POST_STOP_COOLDOWN_HOURS', '72')) * 3600
POST_STOP_SCORE_PENALTY = float(os.getenv('POST_STOP_SCORE_PENALTY', '1.0'))
SLOPE_CONSISTENCY_RATIO = float(os.getenv('SLOPE_CONSISTENCY_RATIO', '0.3'))
SLOPE_WEAK_PENALTY = float(os.getenv('SLOPE_WEAK_PENALTY', '0.4'))

# -- Iteracion 2.1 -- Multi-Signal Confluence + Adaptive Scoring -------------
CONFLUENCE_THRESHOLD = int(os.getenv('CONFLUENCE_THRESHOLD', '4'))  # v2.3: backtest confluence=4 -> 68.4% WR
CONFLUENCE_BONUS = float(os.getenv('CONFLUENCE_BONUS', '0.8'))  # v2.3: subido de 0.5
ADAPTIVE_RR_EXTENSION_THRESHOLD = float(os.getenv('ADAPTIVE_RR_EXTENSION_THRESHOLD', '20.0'))
ADAPTIVE_RR_MULTIPLIER = float(os.getenv('ADAPTIVE_RR_MULTIPLIER', '1.25'))
VOLUME_PROFILE_LOOKBACK = int(os.getenv('VOLUME_PROFILE_LOOKBACK', '3'))
VOLUME_PROFILE_PENALTY = float(os.getenv('VOLUME_PROFILE_PENALTY', '0.5'))

# ── Iteracion 2.5 — Quality Filters + Risk Sizing ────────────────────────────
# #6: Breadth filter
BREADTH_ENABLED      = os.getenv("BREADTH_ENABLED", "true").lower() == "true"
BREADTH_MIN_PCT      = float(os.getenv("BREADTH_MIN_PCT", "50.0"))   # % SP500 sobre EMA200
BREADTH_BLOCK_BELOW  = float(os.getenv("BREADTH_BLOCK_BELOW", "40.0"))  # hard block bajo este nivel
# Universo proxy para breadth (usamos los 11 ETFs sectoriales + indices ya descargados)
# es mas eficiente que descargar los 500 simbolos del SP500.
BREADTH_PROXY_SYMBOLS = ["XLK","XLF","XLV","XLI","XLE","XLP","XLY","XLU","XLB","XLRE","XLC"]

# #7: Position sizing
ACCOUNT_SIZE_USD     = float(os.getenv("ACCOUNT_SIZE_USD", "10000"))
RISK_PER_TRADE_PCT   = float(os.getenv("RISK_PER_TRADE_PCT", "1.0"))  # % de cuenta por trade

# #8: Gap filter
GAP_BLOCK_PCT        = float(os.getenv("GAP_BLOCK_PCT", "2.0"))  # bloquea si |gap| > 2%
GAP_FILTER_ENABLED   = os.getenv("GAP_FILTER_ENABLED", "true").lower() == "true"

# #10: Correlation guard — solo top-ranked alerta por sector por dia
CORRELATION_GUARD_ENABLED = os.getenv("CORRELATION_GUARD_ENABLED", "true").lower() == "true"

# #4: Batch download
BATCH_DOWNLOAD_ENABLED = os.getenv("BATCH_DOWNLOAD_ENABLED", "true").lower() == "true"

# ── Iteracion 2.6 — Quality Hardening ────────────────────────────────────────
# #1: Confluence floor — bloquear setups con muy poca confluencia
CONFLUENCE_HARD_FLOOR    = int(os.getenv("CONFLUENCE_HARD_FLOOR", "2"))   # < hard block
CONFLUENCE_SOFT_FLOOR    = int(os.getenv("CONFLUENCE_SOFT_FLOOR", "3"))   # < penalty
CONFLUENCE_LOW_PENALTY   = float(os.getenv("CONFLUENCE_LOW_PENALTY", "0.5"))

# #2/3: Supertrend bajista mas restrictivo
SUPERTREND_BLOCK_ADX_MIN = float(os.getenv("SUPERTREND_BLOCK_ADX_MIN", "15.0"))   # antes 20
SUPERTREND_BLOCK_RS_NEG  = os.getenv("SUPERTREND_BLOCK_RS_NEG", "true").lower() == "true"

# #4: Sector ETFs RS floor absoluto — XLP con RS=-6.79% nunca deberia pasar
ETF_RS_FLOOR             = float(os.getenv("ETF_RS_FLOOR", "-3.0"))

# v2.10: Eliminadas env vars PULLBACK_* — sistema es breakout puro

# Parametros del nucleo de scoring compartido (scoring.py) — construidos una sola vez
# a partir de las mismas constantes de arriba, para que evaluate_stock() y (via
# backtest.py) evaluate_bar() lean exactamente los mismos umbrales.
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
    breakout_extended_vol_ratio_low_vix=BREAKOUT_EXTENDED_VOL_RATIO_LOW_VIX,
    slope_consistency_ratio=SLOPE_CONSISTENCY_RATIO,
    slope_weak_penalty=SLOPE_WEAK_PENALTY,
    trigger_vol_ratio=TRIGGER_VOL_RATIO,
    breakout_vol_hard_gate=BREAKOUT_VOL_HARD_GATE,
    volume_profile_lookback=VOLUME_PROFILE_LOOKBACK,
    volume_profile_penalty=VOLUME_PROFILE_PENALTY,
    supertrend_regime_block=SUPERTREND_REGIME_BLOCK,
    supertrend_block_adx_min=SUPERTREND_BLOCK_ADX_MIN,
    supertrend_block_rs_neg=SUPERTREND_BLOCK_RS_NEG,
    confluence_hard_floor=CONFLUENCE_HARD_FLOOR,
    confluence_soft_floor=CONFLUENCE_SOFT_FLOOR,
    confluence_low_penalty=CONFLUENCE_LOW_PENALTY,
    confluence_bonus=CONFLUENCE_BONUS,
    adaptive_rr_extension_threshold=ADAPTIVE_RR_EXTENSION_THRESHOLD,
    adaptive_rr_multiplier=ADAPTIVE_RR_MULTIPLIER,
    min_rr=MIN_RR,
    etf_rs_floor=ETF_RS_FLOOR,
    index_etfs=frozenset(INDEX_ETFS),
    sector_etfs=frozenset(SECTOR_ETFS),
)

# v2.5 Fix #3: tracking de simbolos donde fallo earnings — para reportarlo al final
EARNINGS_FAILURES: set[str] = set()

# Cache de earnings: poblado por prefetch_earnings_parallel antes del scan principal
_EARNINGS_CACHE: dict[str, tuple[Optional[str], bool]] = {}

DEFAULT_CONTEXT_CANDIDATES = (
    os.getenv("MARKET_CONTEXT_FILE", ""),
    "market_context_stocks.json",
    "market_context.json",
)

ALERT_HISTORY_COLUMNS = [
    "timestamp_utc",
    "trigger_candle_utc",
    "setup_key",
    "setup_hash",
    "symbol",
    "name",
    "group",
    "playbook",
    "price",
    # FIX (mejora institucional #2): real_entry = Open real de la primera barra
    # posterior a la alerta (analogo al Fix #1 de backtest.py::simulate_trade — "entry
    # efectivo en signal_bar+1, no Close del dia de senal"). Antes el tracker en vivo
    # nunca capturaba esto: pnl_pct/mfe_pct/mae_pct se calculaban siempre contra "price"
    # (el cierre de la barra de señal, ya vencido para cuando la alerta se lee), mientras
    # que el backtest SI se ancla a un fill realista. Se completa recien cuando el
    # tracker ve la primera barra cerrada tras la alerta — vacio ("") hasta entonces;
    # ensure_alert_history_schema() ya migra filas viejas sin esta columna a "".
    "real_entry",
    "target",
    "stop",
    "rr",
    "score",
    "regime_score",
    "setup_score",
    "trigger_score",
    "atr",
    "adx",
    "rsi",
    "rs20",
    "extension_pct",
    "vix",
    "earnings_date",
    "reasons",
    "warnings",
    "blocked",
    "status",
    "last_checked_utc",
    "bars_open",
    "days_open",
    "current_price",
    "pnl_pct",
    "mfe_pct",
    "mae_pct",
    "exit_date",
    "exit_price",
    "exit_reason",
    "closed_utc",
]


# ── Dataclass de señal ────────────────────────────────────────────────────────
@dataclass
class StockSignal:
    symbol: str
    name: str
    price: float
    score: float
    rr: float
    tp: float
    stop: float
    atr: float
    trigger_candle_utc: str
    rsi: float = 0.0
    adx: float = 0.0
    group: str = "Other"
    earnings_date: str = ""
    regime_score: float = 0.0
    setup_score: float = 0.0
    trigger_score: float = 0.0
    extension_pct: float = 0.0
    rs20: float = 0.0
    signal_type: str = "none"
    supertrend_bull: bool = False
    supertrend_val: float = 0.0
    reasons: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    blocked: list[str] = field(default_factory=list)
    # v2.5 nuevos campos
    confluence_count: int = 0
    position_size_shares: int = 0
    position_size_usd: float = 0.0
    risk_usd: float = 0.0
    trailing_stop_initial: float = 0.0
    rank_score: float = 0.0  # para ordenar multiples alertas

    @property
    def should_alert(self) -> bool:
        # FIX (mejora institucional #1): el gate final ahora vive en scoring.py
        # (passes_final_filters), compartido con backtest.py — antes backtest.py
        # reimplementaba una version incompleta inline (sin benchmark_ok/ALERT_ETFS ni
        # el rs_ok especifico de ETFs), lo que le permitia generar "trades" para SPY/QQQ
        # que jamas habrian alertado en vivo. Ver scoring.py para el detalle.
        return scoring.passes_final_filters(
            symbol=self.symbol,
            group=self.group,
            signal_type=self.signal_type,
            score=self.score,
            rr=self.rr,
            blocked=self.blocked,
            rs20=self.rs20,
            require_playbook=REQUIRE_PLAYBOOK,
            min_score=MIN_SCORE,
            min_rr=MIN_RR,
            alert_etfs=ALERT_ETFS,
            final_rs_min=FINAL_RS_MIN,
            final_rs_min_by_group=FINAL_RS_MIN_BY_GROUP,
            etf_rs_floor=ETF_RS_FLOOR,
            index_etfs=frozenset(INDEX_ETFS),
            sector_etfs=frozenset(SECTOR_ETFS),
        )


# FIX: helper de retry con backoff exponencial — antes NINGUNA llamada externa (Telegram,
# yfinance, earnings) reintentaba, violando el requisito basico de un sistema no supervisado
# ("cada llamada externa debe tener retry con backoff"). Un timeout transitorio de red tenia
# el mismo efecto que una falla real: dato perdido, sin segundo intento, hasta la proxima
# corrida (12h despues). Se centraliza aca para no duplicar el patron en cada funcion.
def _retry(desc: str, fn, attempts: int = 3, base_delay: float = 1.5):
    last_exc: Optional[Exception] = None
    for attempt in range(1, attempts + 1):
        try:
            return fn()
        except Exception as exc:
            last_exc = exc
            if attempt == attempts:
                break
            wait = base_delay * (2 ** (attempt - 1))
            log.warning("%s: intento %s/%s fallo (%s) — reintentando en %.1fs", desc, attempt, attempts, exc, wait)
            time.sleep(wait)
    log.error("%s: fallo tras %s intentos — %s", desc, attempts, last_exc)
    return None


# ── Telegram ──────────────────────────────────────────────────────────────────
def send_telegram(msg: str) -> bool:
    if DRY_RUN:
        log.info("[DRY RUN] Mensaje:\n%s", msg)
        return True

    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        log.warning("Telegram no configurado")
        return False

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"

    # FIX: retry con backoff para errores transitorios (timeout, 429, 5xx). No reintenta
    # 4xx != 429 (token invalido, chat_id invalido, markdown malformado) porque ahi
    # reintentar no cambia el resultado — solo demora la deteccion del problema real.
    def _post() -> bool:
        response = requests.post(
            url,
            json={"chat_id": TELEGRAM_CHAT_ID, "text": msg, "parse_mode": "Markdown"},
            timeout=15,
        )
        if response.status_code == 200:
            return True
        if response.status_code == 429 or response.status_code >= 500:
            raise RuntimeError(f"HTTP {response.status_code}: {response.text[:200]}")
        log.warning("Telegram %s (no reintentable): %s", response.status_code, response.text[:200])
        return False

    result = _retry("Telegram sendMessage", _post, attempts=3, base_delay=2.0)
    return bool(result)


# ── Estado ────────────────────────────────────────────────────────────────────
def load_state() -> dict:
    try:
        state_path = Path(STATE_FILE)
        return json.loads(state_path.read_text()) if state_path.exists() else {}
    except Exception as exc:
        log.error("Cargando estado: %s", exc)
        return {}


def save_state(state: dict) -> None:
    try:
        Path(STATE_FILE).write_text(json.dumps(state, indent=2))
    except Exception as exc:
        log.error("Guardando estado: %s", exc)


def _parse_iso_datetime(value: str) -> Optional[datetime]:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except Exception:
        return None


def _safe_float(value: object, default: float = 0.0) -> float:
    try:
        if value in ("", None):
            return default
        return float(value)
    except Exception:
        return default


def _fmt_csv_number(value: object, digits: int = 4) -> str:
    if value in ("", None):
        return ""
    try:
        return f"{float(value):.{digits}f}"
    except Exception:
        return str(value)


def _normalize_dt_text(ts: datetime) -> str:
    # FIX: se elimino ".replace('+00:00', '+00:00')" al final — reemplazaba un string por si
    # mismo (no-op), presumiblemente un resto de una edicion anterior. isoformat() ya deja el
    # sufijo "+00:00" tras astimezone(utc).
    return ts.astimezone(timezone.utc).replace(microsecond=0).isoformat()


def _bar_timestamp_to_utc(idx) -> datetime:
    """Convierte el indice de una barra diaria de yfinance a datetime UTC real.
    # FIX: la version anterior, ante un timestamp naive, hacia
    # `.replace(tzinfo=timezone.utc)` — es decir, ETIQUETABA la fecha/hora tal cual (p.ej.
    # medianoche del calendario de NYSE) como si YA fuera UTC, en vez de CONVERTIRLA. yfinance
    # casi siempre devuelve un indice tz-aware (America/New_York) para datos diarios, por lo
    # que este caso limite rara vez se ejercita en produccion — pero si alguna vez el indice
    # llega naive (cambio de version de pandas/yfinance, feed alternativo, etc.), el bug
    # desplazaria trigger_candle_utc hasta 5 horas, pudiendo cambiar la fecha calendario y
    # romper la deduplicacion por setup_hash (que incluye trigger_candle_utc). Ahora se asume
    # el timezone real de la bolsa (America/New_York) antes de convertir a UTC.
    """
    ts = pd.Timestamp(idx)
    if ts.tzinfo is None:
        ts = ts.tz_localize("America/New_York")
    return ts.to_pydatetime()


def _price_bucket(value: float) -> str:
    return f"{round(float(value), 2):.2f}"


def build_setup_key(sig: StockSignal) -> str:
    return "|".join(
        [
            sig.symbol,
            sig.signal_type,
            sig.trigger_candle_utc,
            _price_bucket(sig.price),
            _price_bucket(sig.tp),
            _price_bucket(sig.stop),
        ]
    )


def build_setup_hash(sig: StockSignal) -> str:
    return hashlib.sha256(build_setup_key(sig).encode("utf-8")).hexdigest()


def load_alert_history_rows() -> list[dict[str, str]]:
    path = Path(ALERTS_HISTORY_FILE)
    if not path.exists() or path.stat().st_size == 0:
        return []

    with path.open("r", newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        rows = []
        for row in reader:
            normalized = {col: row.get(col, "") for col in ALERT_HISTORY_COLUMNS}
            rows.append(normalized)
        return rows


def save_alert_history_rows(rows: list[dict[str, str]]) -> None:
    path = Path(ALERTS_HISTORY_FILE)
    path.parent.mkdir(parents=True, exist_ok=True)

    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=ALERT_HISTORY_COLUMNS)
        writer.writeheader()
        for row in rows:
            normalized = {col: row.get(col, "") for col in ALERT_HISTORY_COLUMNS}
            writer.writerow(normalized)


def _compute_legacy_setup_fields(row: dict[str, str]) -> tuple[str, str]:
    symbol = (row.get("symbol") or "").strip()
    playbook = (row.get("playbook") or "none").strip() or "none"
    trigger_candle_utc = (row.get("trigger_candle_utc") or "").strip()
    price = _price_bucket(_safe_float(row.get("price")))
    target = _price_bucket(_safe_float(row.get("target")))
    stop = _price_bucket(_safe_float(row.get("stop")))

    # Si el CSV viejo no traía trigger_candle_utc, deduplicamos por setup económico
    # para colapsar reenvíos repetidos del mismo trade aunque el timestamp_utc cambie.
    if trigger_candle_utc:
        setup_key = "|".join([symbol, playbook, trigger_candle_utc, price, target, stop])
    else:
        setup_key = "|".join([symbol, playbook, price, target, stop])

    setup_hash = hashlib.sha256(setup_key.encode("utf-8")).hexdigest() if setup_key else ""
    return setup_key, setup_hash


def ensure_alert_history_schema() -> None:
    path = Path(ALERTS_HISTORY_FILE)
    path.parent.mkdir(parents=True, exist_ok=True)

    if not path.exists() or path.stat().st_size == 0:
        return

    with path.open("r", newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        current_columns = reader.fieldnames or []
        rows = list(reader)

    normalized_rows = []
    seen_hashes: set[str] = set()
    duplicates_removed = 0

    for row in rows:
        normalized = {col: row.get(col, "") for col in ALERT_HISTORY_COLUMNS}
        if not normalized.get("trigger_candle_utc"):
            normalized["trigger_candle_utc"] = normalized.get("timestamp_utc", "")
        if not normalized.get("setup_key") or not normalized.get("setup_hash"):
            setup_key, setup_hash = _compute_legacy_setup_fields(normalized)
            normalized["setup_key"] = setup_key
            normalized["setup_hash"] = setup_hash

        setup_hash = normalized.get("setup_hash", "")
        if setup_hash and setup_hash in seen_hashes:
            duplicates_removed += 1
            continue
        if setup_hash:
            seen_hashes.add(setup_hash)
        normalized_rows.append(normalized)

    if current_columns != ALERT_HISTORY_COLUMNS or duplicates_removed:
        save_alert_history_rows(normalized_rows)
        if current_columns != ALERT_HISTORY_COLUMNS:
            log.info("Histórico CSV migrado a esquema tracker+dedupe: %s", ALERTS_HISTORY_FILE)
        if duplicates_removed:
            log.info("Histórico CSV depurado: %s duplicados exactos eliminados", duplicates_removed)


def append_alert_history(sig: StockSignal, vix: Optional[float]) -> None:
    history_path = Path(ALERTS_HISTORY_FILE)
    history_path.parent.mkdir(parents=True, exist_ok=True)

    now_utc = datetime.now(timezone.utc).isoformat()
    setup_key = build_setup_key(sig)
    setup_hash = build_setup_hash(sig)
    row = {
        "timestamp_utc": now_utc,
        "trigger_candle_utc": sig.trigger_candle_utc,
        "setup_key": setup_key,
        "setup_hash": setup_hash,
        "symbol": sig.symbol,
        "name": sig.name,
        "group": sig.group,
        "playbook": sig.signal_type,
        "price": _fmt_csv_number(sig.price),
        # Se completa en update_alert_history_tracker() con el Open real de la primera
        # barra posterior a la alerta — todavia no existe en el momento de alertar.
        "real_entry": "",
        "target": _fmt_csv_number(sig.tp),
        "stop": _fmt_csv_number(sig.stop),
        "rr": _fmt_csv_number(sig.rr),
        "score": _fmt_csv_number(sig.score),
        "regime_score": _fmt_csv_number(sig.regime_score),
        "setup_score": _fmt_csv_number(sig.setup_score),
        "trigger_score": _fmt_csv_number(sig.trigger_score),
        "atr": _fmt_csv_number(sig.atr),
        "adx": _fmt_csv_number(sig.adx),
        "rsi": _fmt_csv_number(sig.rsi),
        "rs20": _fmt_csv_number(sig.rs20),
        "extension_pct": _fmt_csv_number(sig.extension_pct),
        "vix": _fmt_csv_number(vix) if vix is not None else "",
        "earnings_date": sig.earnings_date,
        "reasons": " | ".join(sig.reasons),
        "warnings": " | ".join(sig.warnings),
        "blocked": " | ".join(sig.blocked),
        "status": "open",
        "last_checked_utc": now_utc,
        "bars_open": "0",
        "days_open": "0",
        "current_price": _fmt_csv_number(sig.price),
        "pnl_pct": "0.0000",
        "mfe_pct": "0.0000",
        "mae_pct": "0.0000",
        "exit_date": "",
        "exit_price": "",
        "exit_reason": "",
        "closed_utc": "",
    }

    rows = load_alert_history_rows()
    if any((r.get("setup_hash") or "") == setup_hash for r in rows):
        log.info("🛡️ Histórico: setup ya existe, no se vuelve a guardar (%s %s)", sig.symbol, sig.signal_type)
        return

    rows.append(row)
    save_alert_history_rows(rows)


def has_exact_duplicate(sig: StockSignal, rows: list[dict[str, str]]) -> bool:
    setup_hash = build_setup_hash(sig)
    return any((row.get("setup_hash") or "") == setup_hash for row in rows)


def recent_history_timestamp(symbol: str, rows: list[dict[str, str]]) -> float:
    """Timestamp del trade mas reciente para el simbolo (incluye abiertos).
    Usado para cooldown estandar."""
    latest = 0.0
    for row in rows:
        if (row.get("symbol") or "").strip() != symbol:
            continue
        dt = _parse_iso_datetime(row.get("timestamp_utc", ""))
        if dt is None:
            continue
        latest = max(latest, dt.timestamp())
    return latest


def recent_closed_stop_timestamp(symbol: str, rows: list[dict[str, str]]) -> float:
    """v2.5 Fix #1: Timestamp del ultimo trade CERRADO POR STOP.
    Usado solo para post-stop cooldown — evita confundir trades abiertos."""
    latest = 0.0
    for row in rows:
        if (row.get("symbol") or "").strip() != symbol:
            continue
        status = (row.get("status") or "").strip().lower()
        if status != "hit_stop":
            continue
        # usar closed_utc si existe, fallback a timestamp_utc
        dt = _parse_iso_datetime(row.get("closed_utc", "") or row.get("timestamp_utc", ""))
        if dt is None:
            continue
        latest = max(latest, dt.timestamp())
    return latest


def _last_exit_reason_for_symbol(symbol: str, rows: list[dict[str, str]]) -> str:
    """Retorna el exit_reason del trade mas reciente cerrado para el simbolo."""
    latest_ts = 0.0
    latest_reason = ""
    for row in rows:
        if (row.get("symbol") or "").strip() != symbol:
            continue
        status = (row.get("status") or "").strip().lower()
        if status not in {"hit_stop", "hit_target", "expired"}:
            continue
        dt = _parse_iso_datetime(row.get("closed_utc", "") or row.get("timestamp_utc", ""))
        if dt is None:
            continue
        ts = dt.timestamp()
        if ts > latest_ts:
            latest_ts = ts
            latest_reason = (row.get("exit_reason") or "").strip().lower()
    return latest_reason


def should_suppress_by_history(sig: StockSignal, rows: list[dict[str, str]], now_ts: float, min_score_override: float = 0.0) -> tuple[bool, str]:
    """
    v2.0: cooldown dinamico post-stop.
    - hit_stop reciente -> 72h + score minimo elevado
    - Normal -> COOLDOWN estandar
    """
    if has_exact_duplicate(sig, rows):
        return True, "setup_hash ya existe en historico"
    if not HISTORY_COOLDOWN_FALLBACK:
        return False, ""

    # v2.5 Fix #1: post-stop cooldown usa SOLO trades cerrados por stop
    last_stop_ts = recent_closed_stop_timestamp(sig.symbol, rows)
    if last_stop_ts:
        elapsed_stop = now_ts - last_stop_ts
        if elapsed_stop < POST_STOP_COOLDOWN:
            hours_left = (POST_STOP_COOLDOWN - elapsed_stop) / 3600.0
            return True, f"post-stop cooldown {hours_left:.1f}h restantes (72h)"
        # cooldown vencido pero aun aplicar score elevado
        required_score = MIN_SCORE + POST_STOP_SCORE_PENALTY
        if sig.score < required_score:
            return True, f"post-stop score insuficiente ({sig.score:.1f} < {required_score:.1f})"

    # Cooldown estandar — usa cualquier trade reciente (abierto o cerrado)
    last_ts = recent_history_timestamp(sig.symbol, rows)
    if last_ts:
        elapsed = now_ts - last_ts
        if elapsed < COOLDOWN:
            hours_left = (COOLDOWN - elapsed) / 3600.0
            return True, f"cooldown CSV {hours_left:.1f}h restantes"

    return False, ""



def _prepare_closed_tracker_bars(df: Optional[pd.DataFrame], opened_dt: datetime) -> pd.DataFrame:
    if df is None or df.empty:
        return pd.DataFrame()

    closed_df = df.copy()
    if len(closed_df) >= 2:
        closed_df = closed_df.iloc[:-1]

    if closed_df.empty:
        return pd.DataFrame()

    opened_date = opened_dt.date()
    mask = pd.Index([ts.date() >= opened_date for ts in closed_df.index])
    return closed_df.loc[mask].copy()


def update_alert_history_tracker() -> dict[str, int]:
    stats = {
        "open_checked": 0,
        "hit_target": 0,
        "hit_stop": 0,
        "expired": 0,
        "still_open": 0,
        "invalid": 0,
    }

    if not TRACKER_ENABLED:
        return stats

    rows = load_alert_history_rows()
    if not rows:
        return stats

    now_utc = datetime.now(timezone.utc).isoformat()
    data_cache: dict[str, Optional[pd.DataFrame]] = {}
    changed = False

    for row in rows:
        status = (row.get("status") or "open").strip().lower()
        if status in {"hit_target", "hit_stop", "expired"}:
            continue

        stats["open_checked"] += 1

        symbol = (row.get("symbol") or "").strip()
        entry = _safe_float(row.get("price"))
        target = _safe_float(row.get("target"))
        stop = _safe_float(row.get("stop"))
        opened_dt = _parse_iso_datetime(row.get("timestamp_utc", ""))

        if not symbol or entry <= 0 or target <= 0 or stop <= 0 or opened_dt is None:
            row["status"] = "invalid"
            row["last_checked_utc"] = now_utc
            stats["invalid"] += 1
            changed = True
            continue

        if symbol not in data_cache:
            data_cache[symbol] = fetch_data(symbol)

        trade_df = _prepare_closed_tracker_bars(data_cache[symbol], opened_dt)
        if trade_df.empty:
            row["status"] = "open"
            row["last_checked_utc"] = now_utc
            row["bars_open"] = "0"
            row["days_open"] = "0"
            row["current_price"] = _fmt_csv_number(entry)
            row["pnl_pct"] = "0.0000"
            row["mfe_pct"] = "0.0000"
            row["mae_pct"] = "0.0000"
            changed = True
            stats["still_open"] += 1
            continue

        # FIX (mejora institucional #2): capturar el fill REAL (Open de la primera barra
        # cerrada tras la alerta), analogo a simulate_trade()'s Fix #1 en backtest.py.
        # Se calcula UNA sola vez (trade_df.iloc[0] es siempre la misma barra calendario
        # en corridas sucesivas, porque el filtro es por opened_date fijo) y se persiste
        # en el CSV para que corridas futuras no lo recalculen ni lo desplacen.
        real_entry = _safe_float(row.get("real_entry"))
        if real_entry <= 0:
            real_entry = float(trade_df["Open"].iloc[0])
            row["real_entry"] = _fmt_csv_number(real_entry)

        highs = trade_df["High"].astype(float)
        lows = trade_df["Low"].astype(float)
        closes = trade_df["Close"].astype(float)

        bars_open = int(len(trade_df))
        days_open = int((trade_df.index[-1].date() - opened_dt.date()).days)
        current_price = float(closes.iloc[-1])
        mfe_pct = ((float(highs.max()) - real_entry) / max(real_entry, 1e-9)) * 100.0
        mae_pct = ((float(lows.min()) - real_entry) / max(real_entry, 1e-9)) * 100.0

        exit_status = "open"
        exit_price = None
        exit_date = ""
        exit_reason = ""

        for idx, bar in trade_df.iterrows():
            bar_low = float(bar["Low"])
            bar_high = float(bar["High"])

            hit_stop = bar_low <= stop
            hit_target = bar_high >= target

            if hit_stop and hit_target:
                exit_status = "hit_stop"
                exit_price = stop
                exit_date = idx.date().isoformat()
                exit_reason = "same_bar_both_hit_stop_first"
                break
            if hit_stop:
                exit_status = "hit_stop"
                exit_price = stop
                exit_date = idx.date().isoformat()
                exit_reason = "stop_hit"
                break
            if hit_target:
                exit_status = "hit_target"
                exit_price = target
                exit_date = idx.date().isoformat()
                exit_reason = "target_hit"
                break

        # v2.10: time-stop unico (solo breakout en sistema)
        if exit_status == "open" and bars_open >= TRACKER_MAX_BARS_OPEN:
            exit_status = "expired"
            exit_price = current_price
            exit_date = trade_df.index[-1].date().isoformat()
            exit_reason = f"time_stop_{TRACKER_MAX_BARS_OPEN}_bars"

        row["status"] = exit_status
        row["last_checked_utc"] = now_utc
        row["bars_open"] = str(bars_open)
        row["days_open"] = str(days_open)
        row["current_price"] = _fmt_csv_number(current_price)
        row["mfe_pct"] = _fmt_csv_number(mfe_pct)
        row["mae_pct"] = _fmt_csv_number(mae_pct)

        if exit_status == "open":
            row["pnl_pct"] = _fmt_csv_number(((current_price - real_entry) / max(real_entry, 1e-9)) * 100.0)
            row["exit_date"] = ""
            row["exit_price"] = ""
            row["exit_reason"] = ""
            row["closed_utc"] = ""
            stats["still_open"] += 1
        else:
            realized_pnl_pct = ((float(exit_price) - real_entry) / max(real_entry, 1e-9)) * 100.0
            row["pnl_pct"] = _fmt_csv_number(realized_pnl_pct)
            row["exit_date"] = exit_date
            row["exit_price"] = _fmt_csv_number(exit_price)
            row["exit_reason"] = exit_reason
            row["closed_utc"] = now_utc

            if exit_status == "hit_target":
                stats["hit_target"] += 1
            elif exit_status == "hit_stop":
                stats["hit_stop"] += 1
            elif exit_status == "expired":
                stats["expired"] += 1

        changed = True

    if changed:
        save_alert_history_rows(rows)

    return stats


# ── Contexto macro manual ─────────────────────────────────────────────────────
def resolve_context_path() -> Optional[Path]:
    for candidate in DEFAULT_CONTEXT_CANDIDATES:
        if not candidate:
            continue
        path = Path(candidate)
        if path.exists():
            return path
    return None


def load_market_context() -> dict:
    path = resolve_context_path()
    if path is None:
        log.info("Sin market_context local — se usará contexto vacío")
        return {}

    try:
        raw = json.loads(path.read_text())
        if isinstance(raw, dict):
            log.info("Contexto cargado desde %s", path)
            return raw
        return {}
    except Exception as exc:
        log.warning("No se pudo leer %s: %s", path, exc)
        return {}


def get_symbol_context(context: dict, symbol: str) -> dict:
    merged: dict = {}
    merged.update(context.get("GLOBAL", {}))
    merged.update(context.get(symbol, {}))
    return merged


def normalize_caution_adjustment(sym_context: dict) -> tuple[float, str]:
    score_adjustment = float(sym_context.get("score_adjustment", 0.0))
    caution_level = str(sym_context.get("caution_level", "")).upper().strip()
    note = str(sym_context.get("note", "")).strip()

    caution_map = {
        "HIGH": -0.75,
        "ELEVATED": -0.50,
        "REDUCED": -0.25,
        "NORMAL": 0.0,
        "FAVORABLE": 0.25,
    }

    if caution_level in caution_map:
        score_adjustment += caution_map[caution_level]

    return score_adjustment, note


# ── Macro ─────────────────────────────────────────────────────────────────────
def fetch_vix() -> Optional[float]:
    # FIX: retry con backoff. El VIX es el circuit breaker de panico de mercado
    # (VIX_BLOCK_LEVEL=30 = bloqueo total); antes un timeout transitorio de yfinance
    # desactivaba ese hard block para TODA la corrida sin que nadie se enterara mas que
    # por un log de GitHub Actions que nadie revisa reactivamente. Ver tambien el resumen
    # de Telegram en main(), que ahora reporta explicitamente si el VIX no estuvo disponible.
    def _fetch() -> float:
        df = yf.Ticker("^VIX").history(period="5d", interval="1d", auto_adjust=True)
        if df is None or df.empty:
            raise RuntimeError("respuesta vacia de yfinance")
        return round(float(df["Close"].iloc[-1]), 2)

    return _retry("VIX", _fetch, attempts=3, base_delay=1.5)


def get_earnings_info(symbol: str) -> tuple[Optional[str], bool]:
    if STOCK_GROUPS.get(symbol) == "ETF":
        return None, False
    if symbol in _EARNINGS_CACHE:
        return _EARNINGS_CACHE[symbol]

    # FIX: retry con backoff en la parte de red (antes un timeout/429 transitorio de
    # yfinance dejaba el simbolo sin filtro de earnings por toda la corrida — riesgo real:
    # alertar sobre una accion que reporta resultados esa misma semana). Se reintenta solo
    # la obtencion de datos; distingue "API fallo" (reintentable, cuenta como failure) de
    # "no hay earnings programados" (respuesta valida, no es una falla).
    last_exc: Optional[Exception] = None
    earnings_date = None
    for attempt in range(1, 4):
        try:
            ticker = yf.Ticker(symbol)
            earnings_date = None

            try:
                earnings_df = ticker.get_earnings_dates(limit=1)
                if earnings_df is not None and not earnings_df.empty:
                    earnings_date = earnings_df.index[0]
            except Exception:
                earnings_df = None

            if earnings_date is None:
                cal = ticker.calendar
                if isinstance(cal, dict):
                    candidate = cal.get("Earnings Date")
                    if isinstance(candidate, list) and candidate:
                        earnings_date = candidate[0]
                    elif candidate is not None:
                        earnings_date = candidate
                elif isinstance(cal, pd.DataFrame) and not cal.empty and "Earnings Date" in cal.index:
                    earnings_date = cal.loc["Earnings Date"].iloc[0]

            last_exc = None
            break
        except Exception as exc:
            last_exc = exc
            if attempt < 3:
                wait = 1.5 * (2 ** (attempt - 1))
                log.warning("%s: earnings intento %s/3 fallo (%s) — reintentando en %.1fs", symbol, attempt, exc, wait)
                time.sleep(wait)

    if last_exc is not None:
        # v2.5 Fix #3: warning visible — operar sin filtro de earnings es riesgoso
        log.warning("%s: get_earnings_info FALLO tras reintentos — operando SIN filtro de earnings: %s", symbol, last_exc)
        EARNINGS_FAILURES.add(symbol)
        return None, False

    if earnings_date is None:
        return None, False

    if hasattr(earnings_date, "to_pydatetime"):
        earnings_dt = earnings_date.to_pydatetime()
    elif isinstance(earnings_date, datetime):
        earnings_dt = earnings_date
    else:
        return str(earnings_date), False

    now = datetime.now(timezone.utc)
    if earnings_dt.tzinfo is None:
        earnings_dt = earnings_dt.replace(tzinfo=timezone.utc)

    # Usar total_seconds para evitar truncamiento de .days
    # Ejemplo: 5 días y 23 horas → .days = 5 (pasa el filtro), total = 5.96 (bloqueado)
    diff_seconds = abs((earnings_dt - now).total_seconds())
    days_diff = diff_seconds / 86400.0
    date_str = earnings_dt.strftime("%Y-%m-%d")
    return date_str, days_diff <= EARNINGS_BUFFER_DAYS


def prefetch_earnings_parallel(symbols: list[str], max_workers: int = 10) -> None:
    """Precarga earnings info para todos los simbolos no-ETF en paralelo.
    Popula _EARNINGS_CACHE para que evaluate_stock() no haga requests individuales."""
    global _EARNINGS_CACHE
    non_etf = [s for s in symbols if STOCK_GROUPS.get(s) != "ETF"]
    if not non_etf:
        return
    log.info("Prefetch earnings paralelo: %s simbolos (max_workers=%s)...", len(non_etf), max_workers)
    t0 = time.time()
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(get_earnings_info, s): s for s in non_etf}
        for future in as_completed(futures):
            sym = futures[future]
            try:
                _EARNINGS_CACHE[sym] = future.result()
            except Exception as exc:
                log.debug("Earnings prefetch %s: %s", sym, exc)
                _EARNINGS_CACHE[sym] = (None, False)
    log.info("Prefetch earnings completado en %.1fs (%s/%s OK)",
             time.time() - t0, len(_EARNINGS_CACHE), len(non_etf))


# ── Indicadores técnicos ──────────────────────────────────────────────────────
def add_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """v2.9: delega al modulo signals.py — unica fuente de verdad."""
    return _signals_add_indicators(
        df,
        swing_lookback=SWING_LOOKBACK,
        supertrend_period=SUPERTREND_PERIOD,
        supertrend_multiplier=SUPERTREND_MULTIPLIER,
    )


# ── Descarga ──────────────────────────────────────────────────────────────────
# v2.5 Fix #4: cache global de descargas batch
_DATA_CACHE: dict[str, pd.DataFrame] = {}


def batch_download(symbols: list[str], period: str = "2y") -> dict[str, pd.DataFrame]:
    """Descarga multiples simbolos en una sola request.
    yf.download() acepta lista de tickers y devuelve DataFrame multi-index."""
    if not symbols:
        return {}

    # FIX: retry con backoff — antes un unico fallo (timeout, rate limit) tiraba todo el
    # batch a descarga individual (40 requests en vez de 1), mucho mas lento y con mayor
    # probabilidad de rate-limit en cascada. Reintentar el batch primero es mas barato.
    def _download() -> object:
        # group_by='ticker' para tener df.xs(symbol) accesible
        bulk = yf.download(
            tickers=" ".join(symbols),
            period=period,
            interval="1d",
            auto_adjust=True,
            group_by="ticker",
            progress=False,
            threads=True,
        )
        if bulk is None or bulk.empty:
            raise RuntimeError("respuesta vacia de yfinance")
        return bulk

    bulk = _retry("Batch download", _download, attempts=3, base_delay=2.0)
    if bulk is None:
        log.warning("Batch download fallo tras reintentos — fallback a descarga individual")
        return {}

    result: dict[str, pd.DataFrame] = {}
    if bulk is None or bulk.empty:
        return result

    for sym in symbols:
        try:
            if len(symbols) == 1:
                df = bulk
            else:
                df = bulk[sym] if sym in bulk.columns.get_level_values(0) else None
            if df is None or df.empty:
                continue
            df = df.dropna(subset=["High","Low","Close","Volume"])
            if len(df) >= 220:
                result[sym] = df
        except Exception as exc:
            log.debug("Batch parse %s: %s", sym, exc)

    return result


def prefetch_all_data(symbols: list[str]) -> None:
    """Descarga todos los simbolos al inicio del scan en un batch."""
    global _DATA_CACHE
    if not BATCH_DOWNLOAD_ENABLED:
        return
    log.info("Batch download de %s simbolos...", len(symbols))
    t0 = time.time()
    _DATA_CACHE = batch_download(symbols)
    elapsed = time.time() - t0
    log.info("Batch download completado en %.1fs (%s/%s simbolos OK)",
             elapsed, len(_DATA_CACHE), len(symbols))


def fetch_data(symbol: str) -> Optional[pd.DataFrame]:
    """Devuelve datos del cache o hace descarga individual como fallback."""
    if symbol in _DATA_CACHE:
        return _DATA_CACHE[symbol]

    # FIX: retry con backoff — este es el fallback individual que corre cuando el batch
    # download no trajo el simbolo; antes tampoco reintentaba, asi que un timeout aqui
    # eliminaba el simbolo del scan completo para esa corrida sin segunda oportunidad.
    def _fetch() -> pd.DataFrame:
        result = yf.Ticker(symbol).history(period="2y", interval="1d", auto_adjust=True)
        if result is None or result.empty:
            raise RuntimeError("respuesta vacia de yfinance")
        return result

    df = _retry(f"{symbol} fetch_data", _fetch, attempts=3, base_delay=1.5)
    if df is None:
        return None

    required = {"High", "Low", "Close", "Volume"}
    if df is None or df.empty or not required.issubset(df.columns):
        log.warning("%s: datos invalidos", symbol)
        return None

    df = df.dropna(subset=list(required))
    if len(df) < 220:
        log.warning("%s: pocas velas (%s < 220)", symbol, len(df))
        return None

    _DATA_CACHE[symbol] = df
    return df


# ── Helpers cuantitativos ─────────────────────────────────────────────────────
def compute_relative_strength(df: pd.DataFrame, spy_df: Optional[pd.DataFrame], symbol: str = "") -> float:
    """v2.9: delega al modulo signals.py — unica fuente de verdad."""
    return _signals_compute_rs(df, spy_df, lookback=RS_LOOKBACK, symbol=symbol)


# ── v2.5 #6: Breadth filter ──────────────────────────────────────────────────
def compute_market_breadth() -> Optional[float]:
    """% de simbolos del proxy SP500 (ETFs sectoriales) sobre su EMA200.
    Returns None si no hay datos suficientes."""
    if not BREADTH_ENABLED:
        return None

    above = 0
    total = 0
    for sym in BREADTH_PROXY_SYMBOLS:
        df = fetch_data(sym)
        if df is None or len(df) < 200:
            continue
        ema200 = df["Close"].ewm(span=200, adjust=False).mean()
        last_close = float(df["Close"].iloc[-2])
        last_ema   = float(ema200.iloc[-2])
        if last_close > last_ema:
            above += 1
        total += 1

    if total == 0:
        return None
    pct = (above / total) * 100.0
    log.info("Breadth proxy: %s/%s ETFs sectoriales sobre EMA200 (%.1f%%)", above, total, pct)
    return round(pct, 1)


# ── v2.5 #7 + v2.10: Position sizing simplificado (solo breakout) ───────────
def compute_position_size(entry: float, stop: float, playbook: str = "breakout") -> tuple[int, float, float]:
    """Calcula # acciones, $ posicion, $ riesgo basado en RISK_PER_TRADE_PCT.
    v2.10: sizing 1x para todos (eliminado pullback factor).
    Returns (shares, position_usd, risk_usd)."""
    risk_per_share = max(entry - stop, 0.01)
    risk_budget    = ACCOUNT_SIZE_USD * (RISK_PER_TRADE_PCT / 100.0)
    shares = int(risk_budget / risk_per_share)
    position_usd = shares * entry
    risk_usd     = shares * risk_per_share
    return shares, round(position_usd, 2), round(risk_usd, 2)


# ── v2.5 #8: Gap filter ──────────────────────────────────────────────────────
def detect_overnight_gap(df: pd.DataFrame) -> tuple[float, bool]:
    """Detecta gap entre cierre de N-1 y apertura de N (ultima barra).
    Returns (gap_pct, blocked)."""
    if not GAP_FILTER_ENABLED or len(df) < 2:
        return 0.0, False
    prev_close = float(df["Close"].iloc[-2])
    today_open = float(df["Open"].iloc[-1])
    gap_pct = abs((today_open - prev_close) / max(prev_close, 1e-9)) * 100.0
    blocked = gap_pct > GAP_BLOCK_PCT
    return round(gap_pct, 2), blocked


# ── v2.5 #11: Trailing stop sugerido ─────────────────────────────────────────
def compute_trailing_stop_initial(entry: float, atr: float, ema20: float) -> float:
    """Stop de trailing inicial sugerido para post-trade.
    Mas ajustado que el stop estructural — para mover una vez la posicion este ITM."""
    return round(max(ema20, entry - 1.5 * atr), 2)


# ── Evaluación ────────────────────────────────────────────────────────────────
def evaluate_stock(symbol: str, sym_context: dict, vix: Optional[float], spy_df: Optional[pd.DataFrame], breadth_pct: Optional[float] = None) -> Optional[StockSignal]:
    df = fetch_data(symbol)
    if df is None:
        return None

    earnings_date_str, earnings_near = get_earnings_info(symbol)
    df = add_indicators(df)

    if len(df) < max(220, RS_LOOKBACK + 25):
        return None

    last = df.iloc[-2]
    prev = df.iloc[-3]
    trigger_candle_utc = _normalize_dt_text(_bar_timestamp_to_utc(df.index[-2]))

    name = STOCK_NAMES.get(symbol, symbol)
    group = STOCK_GROUPS.get(symbol, "Other")

    entry = float(last["Close"])
    rs20 = 0.0 if symbol == "SPY" else compute_relative_strength(df, spy_df, symbol=symbol)
    recent_vols = df["Volume"].iloc[-(VOLUME_PROFILE_LOOKBACK + 1):-1].values

    # FIX (mejora institucional #1): todo el bloque de scoring tecnico (regime/setup/
    # trigger/confluencia/playbook/stop-tp-rr) vivia duplicado aca y en
    # backtest.py::evaluate_bar, y habia divergido silenciosamente con el tiempo (ver
    # scoring.py). Ahora ambos llaman al mismo nucleo — este archivo solo aporta lo que
    # es genuinamente exclusivo de la operacion en vivo: earnings, gap intraday,
    # contexto manual y sizing/telegram.
    base_score_adjustment, context_note = normalize_caution_adjustment(sym_context)
    core = scoring.evaluate_core(
        symbol, group, last, prev, rs20, vix, recent_vols, _CORE_PARAMS,
        base_score_adjustment=base_score_adjustment,
        breadth_pct=breadth_pct,
    )

    blocked: list[str] = []
    warnings: list[str] = list(core.warnings)
    reasons: list[str] = list(core.reasons)

    # ── Filtros exclusivamente en vivo (sin equivalente historico limpio) ──
    if earnings_near and earnings_date_str:
        blocked.append(f"Earnings en {earnings_date_str} (±{EARNINGS_BUFFER_DAYS} días)")

    # v2.5 #8: gap filter — si gap intraday >GAP_BLOCK_PCT, el setup tecnico es invalido
    gap_pct, gap_blocked = detect_overnight_gap(df)
    if gap_blocked:
        blocked.append(f"Gap overnight {gap_pct:.1f}% > {GAP_BLOCK_PCT}% — entry invalida")

    if sym_context.get("hard_block_long"):
        blocked.append(f"Bloqueo manual: {sym_context.get('note', 'sin nota')}")

    blocked.extend(core.blocked)

    if core.score_adjustment != 0:
        reasons.append(f"Ajuste macro/manual: {core.score_adjustment:+.2f}")
    if context_note:
        reasons.append(f"Contexto: {context_note}")

    # v2.5: position sizing + trailing stop sugerido + ranking score
    shares, pos_usd, risk_usd = compute_position_size(entry, core.stop, core.signal_type)
    trailing_initial = compute_trailing_stop_initial(entry, core.atr, float(last["ema20"]))
    # ranking: score ponderado por confluence + RS positiva (boost)
    rank = core.total_score * (1 + core.confluence_count * 0.15) * (1 + max(rs20, 0) / 20)

    return StockSignal(
        symbol=symbol,
        name=name,
        price=entry,
        score=core.total_score,
        rr=round(core.rr, 2),
        tp=round(core.tp, 2),
        stop=round(core.stop, 2),
        atr=round(core.atr, 2),
        trigger_candle_utc=trigger_candle_utc,
        rsi=round(core.rsi, 2),
        adx=round(core.adx, 2),
        group=group,
        earnings_date=earnings_date_str or "",
        regime_score=core.regime_score,
        setup_score=core.setup_score,
        trigger_score=core.trigger_score,
        extension_pct=round(core.extension_pct, 2),
        rs20=round(rs20, 2),
        signal_type=core.signal_type,
        supertrend_bull=core.supertrend_bull,
        supertrend_val=round(core.supertrend_val, 2),
        reasons=reasons,
        warnings=warnings,
        blocked=blocked,
        # v2.5 nuevos campos
        confluence_count=core.confluence_count,
        position_size_shares=shares,
        position_size_usd=pos_usd,
        risk_usd=risk_usd,
        trailing_stop_initial=trailing_initial,
        rank_score=round(rank, 2),
    )


# ── Formato de alerta ─────────────────────────────────────────────────────────
def format_alert(sig: StockSignal, vix: Optional[float]) -> str:
    score_emoji = "🔥" if sig.score >= 7.0 else "📈"
    vix_line = f"📉 *VIX:* {vix:.1f}\n" if vix is not None else ""
    earnings_line = f"📅 *Próximos earnings:* {sig.earnings_date}\n" if sig.earnings_date else ""
    rs_line = f"⚔️ *RS vs SPY (20d):* {sig.rs20:+.2f}%\n" if sig.symbol != "SPY" else ""
    # v2.10: solo breakout
    signal_type_line = f"🚀 *Playbook:* breakout\n" if sig.signal_type == "breakout" else ""
    trigger_line = f"🕯️ *Trigger candle:* {sig.trigger_candle_utc}\n"
    st_emoji = "🟢" if sig.supertrend_bull else "🔴"
    st_dir = "ALCISTA" if sig.supertrend_bull else "BAJISTA"
    supertrend_line = f"{st_emoji} *Supertrend({SUPERTREND_PERIOD},{SUPERTREND_MULTIPLIER}):* {st_dir} @ ${sig.supertrend_val:.2f}\n"

    signal_breakdown = (
        f"🧩 *Regime/Setup/Trigger:* "
        f"{sig.regime_score:.1f}/{sig.setup_score:.1f}/{sig.trigger_score:.1f}\n"
    )

    warnings_block = ""
    if sig.warnings:
        warnings_block = "\n⚠️ *Warnings:*\n" + "\n".join(f"  • {warn}" for warn in sig.warnings[:4])

    confluences = "\n".join(f"  • {reason}" for reason in sig.reasons[:8])

    # v2.5: bloque de sizing + trailing stop
    sizing_block = ""
    if sig.position_size_shares > 0:
        sizing_block = (
            f"\n💼 *Sizing sugerido* (cuenta=${ACCOUNT_SIZE_USD:,.0f}, riesgo={RISK_PER_TRADE_PCT}%)\n"
            f"  • Acciones: {sig.position_size_shares}\n"
            f"  • Posicion: ${sig.position_size_usd:,.2f}\n"
            f"  • Riesgo: ${sig.risk_usd:.2f}\n"
            f"  • Trailing stop sugerido: ${sig.trailing_stop_initial:.2f}\n"
        )

    confluence_line = f"🔗 *Confluence count:* {sig.confluence_count}/5\n" if sig.confluence_count > 0 else ""

    return (
        f"{score_emoji} *ALERTA BOLSA v2.6: {sig.name} ({sig.symbol})*\n\n"
        f"💰 *Precio:* ${sig.price:.2f}\n"
        f"📊 *Score:* {sig.score:.1f} | *Rank:* {sig.rank_score:.2f}\n"
        f"⚖️ *R:R estructural:* {sig.rr:.2f}x\n"
        f"📏 *ATR:* ${sig.atr:.2f} | *ADX:* {sig.adx:.1f} | *RSI:* {sig.rsi:.1f}\n"
        f"{supertrend_line}"
        f"{signal_breakdown}"
        f"{confluence_line}"
        f"{signal_type_line}"
        f"{trigger_line}"
        f"{rs_line}"
        f"{vix_line}"
        f"{earnings_line}"
        f"\n🎯 *TARGET:* ${sig.tp:.2f}\n"
        f"🛑 *STOP:* ${sig.stop:.2f}"
        f"{sizing_block}\n"
        f"📝 *Confluencias:*\n{confluences}"
        f"{warnings_block}"
    )


def format_reject_log(sig: StockSignal) -> str:
    if sig.blocked:
        return "; ".join(sig.blocked[:4])
    if sig.warnings:
        return "; ".join(sig.warnings[:4])
    return "Sin score suficiente"


# ── Main ──────────────────────────────────────────────────────────────────────
def main() -> None:
    state = load_state()
    context = load_market_context()
    now = time.time()

    ensure_alert_history_schema()
    history_rows = load_alert_history_rows()

    mode = "DRY RUN" if DRY_RUN else "PRODUCCIÓN"
    log.info("Iniciando escaneo v2.6 [%s] — %s simbolos", mode, len(STOCKS))
    log.info("Historico CSV: %s", ALERTS_HISTORY_FILE)

    tracker_stats = update_alert_history_tracker() if not DRY_RUN else {"open_checked": 0, "hit_target": 0, "hit_stop": 0, "expired": 0, "still_open": 0, "invalid": 0}
    if tracker_stats["open_checked"] > 0:
        log.info(
            "Tracker historico | Revisadas:%s | Target:%s | Stop:%s | Expiradas:%s | Abiertas:%s | Invalidas:%s",
            tracker_stats["open_checked"], tracker_stats["hit_target"], tracker_stats["hit_stop"],
            tracker_stats["expired"], tracker_stats["still_open"], tracker_stats["invalid"],
        )
        history_rows = load_alert_history_rows()

    # v2.5 Fix #4: batch download al inicio — todos los simbolos + breadth proxies + SPY/VIX
    all_symbols_to_fetch = list(set(STOCKS + BREADTH_PROXY_SYMBOLS + ["SPY"]))
    prefetch_all_data(all_symbols_to_fetch)

    # Prefetch earnings en paralelo mientras el batch download ya completó
    prefetch_earnings_parallel(STOCKS)

    vix = fetch_vix()
    if vix is not None:
        vix_status = "PANICO" if vix >= VIX_BLOCK_LEVEL else ("NERVIOSO" if vix >= VIX_CAUTION_LEVEL else "NORMAL")
        log.info("VIX=%.1f — condicion de mercado: %s", vix, vix_status)
    else:
        log.warning("VIX no disponible — se omite filtro macro")

    spy_df = fetch_data("SPY")
    if spy_df is None:
        log.warning("SPY no disponible — se omite relative strength benchmark")

    # v2.5 #6: breadth filter — calcular una sola vez para todo el scan
    breadth_pct = compute_market_breadth()

    stats = {k: 0 for k in ("scanned", "cooldown", "no_data", "blocked", "duplicate", "no_signal", "alerts", "corr_guard", "ranked_skip")}

    # ========================================================================
    # FASE 1: Recolectar candidatos validos (sin alertar todavia)
    # ========================================================================
    candidates: list[StockSignal] = []

    for symbol in STOCKS:
        last_alert_state = float(state.get(symbol, 0) or 0)
        fallback_last_ts = recent_history_timestamp(symbol, history_rows)
        last_alert = max(last_alert_state, fallback_last_ts)
        remaining = COOLDOWN - (now - last_alert)
        if remaining > 0:
            log.info("COOLDOWN %s: %.1fh restantes", symbol, remaining / 3600)
            stats["cooldown"] += 1
            continue

        stats["scanned"] += 1
        try:
            sym_context = get_symbol_context(context, symbol)
            sig = evaluate_stock(symbol, sym_context, vix, spy_df, breadth_pct)

            if sig is None:
                stats["no_data"] += 1
                log.warning("%s: sin datos suficientes", symbol)
                continue

            if sig.blocked:
                stats["blocked"] += 1
                log.info(
                    "%s: score=%.1f | RR=%.2f | r/s/t=%.1f/%.1f/%.1f | BLOQUEADO | %s",
                    sig.symbol, sig.score, sig.rr, sig.regime_score, sig.setup_score,
                    sig.trigger_score, format_reject_log(sig),
                )
                continue

            if sig.should_alert:
                # Verificar cooldown / duplicado antes de añadir a candidatos
                suppress, reason = should_suppress_by_history(sig, history_rows, now)
                if suppress:
                    stats["duplicate"] += 1
                    log.info("🛡️ DUPLICADA %s | %s", sig.symbol, reason)
                    continue
                candidates.append(sig)
            else:
                stats["no_signal"] += 1
                log.info(
                    "%s: score=%.1f | RR=%.2f | r/s/t=%.1f/%.1f/%.1f | sin senal | %s",
                    sig.symbol, sig.score, sig.rr, sig.regime_score, sig.setup_score,
                    sig.trigger_score, format_reject_log(sig),
                )

        except Exception as exc:
            log.error("%s: excepcion — %s", symbol, exc, exc_info=True)

    # ========================================================================
    # FASE 2: Rankear candidatos + correlation guard + emitir alertas
    # ========================================================================
    telegram_failures: list[str] = []
    if candidates:
        # v2.5 #9: rankear por rank_score descendente
        candidates.sort(key=lambda s: s.rank_score, reverse=True)
        log.info("Candidatos pre-ranking: %s", [(c.symbol, c.rank_score) for c in candidates])

        # v2.5 #10: correlation guard — solo top 1 por sector
        sectors_used: set[str] = set()
        approved: list[StockSignal] = []
        for sig in candidates:
            if CORRELATION_GUARD_ENABLED and sig.group in sectors_used:
                stats["corr_guard"] += 1
                log.info(
                    "🔗 CORR GUARD %s (grupo=%s ya tiene alerta de mayor rank)",
                    sig.symbol, sig.group,
                )
                continue
            approved.append(sig)
            sectors_used.add(sig.group)

        # Emitir alertas finales
        # FIX: antes, append_alert_history() y el cooldown (state[symbol]=now) SOLO se
        # ejecutaban si send_telegram() devolvia True. Eso acopla el audit trail y el
        # anti-duplicado a la disponibilidad de una API externa sin retry propio a este
        # nivel: si Telegram fallaba (rate limit, markdown roto por un "note" manual en
        # market_context_stocks.json, etc.), la señal se perdia para siempre sin quedar
        # registrada, Y ademas podia volver a evaluarse y re-intentar alertar en la
        # siguiente corrida porque nunca se persistio ni se seteo el cooldown. Ahora la
        # persistencia (historico + cooldown) es incondicional; el envio a Telegram es
        # best-effort (ya con retry, ver send_telegram) y su fallo solo se refleja en
        # logs/stats/resumen, sin comprometer el registro de auditoria del trade.
        for sig in approved:
            delivered = send_telegram(format_alert(sig, vix))
            if not delivered:
                telegram_failures.append(sig.symbol)
                log.error(
                    "Telegram NO entrego la alerta de %s tras reintentos — se persiste "
                    "igual en el historico para no perder el registro ni el cooldown",
                    sig.symbol,
                )

            if not DRY_RUN:
                append_alert_history(sig, vix)
                history_rows = load_alert_history_rows()
                state[sig.symbol] = now
                save_state(state)

            stats["alerts"] += 1
            log.info(
                "%s ALERTA %s | score=%.1f | rank=%.2f | confluence=%s/5 | RR=%.2f | playbook=%s | RS20=%+.2f%%",
                "✅" if delivered else "⚠️ (no entregada a Telegram)",
                sig.symbol, sig.score, sig.rank_score, sig.confluence_count,
                sig.rr, sig.signal_type, sig.rs20,
            )

    # v2.5 Fix #3: reportar simbolos donde fallo earnings
    if EARNINGS_FAILURES:
        log.warning(
            "EARNINGS NO DISPONIBLES para %s simbolos (operando sin filtro): %s",
            len(EARNINGS_FAILURES), sorted(EARNINGS_FAILURES),
        )

    log.info(
        "Escaneo v2.6 completado | Escaneados:%s | Cooldown:%s | Sin datos:%s | Bloqueados:%s | "
        "Duplicadas:%s | Sin senal:%s | CorrGuard:%s | Alertas:%s",
        stats["scanned"], stats["cooldown"], stats["no_data"], stats["blocked"],
        stats["duplicate"], stats["no_signal"], stats["corr_guard"], stats["alerts"],
    )

    if not DRY_RUN:
        # FIX: antes, VIX no disponible / fallas de earnings / entregas fallidas de
        # Telegram solo quedaban en el log de GitHub Actions (que nadie revisa
        # reactivamente). Un fallo de VIX en particular desactiva silenciosamente el
        # circuit breaker de panico de mercado para toda la corrida — ahora se hace
        # visible en el mismo resumen que el operador SI lee (Telegram).
        vix_summary = f"📉 VIX: {vix:.1f}\n" if vix is not None else "⚠️ VIX NO DISPONIBLE — hard block de panico desactivado esta corrida\n"
        breadth_summary = f"🌐 Breadth: {breadth_pct:.1f}%\n" if breadth_pct is not None else ""
        earnings_summary = (
            f"⚠️ Earnings no disponibles ({len(EARNINGS_FAILURES)}): {', '.join(sorted(EARNINGS_FAILURES))}\n"
            if EARNINGS_FAILURES else ""
        )
        telegram_fail_summary = (
            f"⚠️ Alertas NO entregadas a Telegram ({len(telegram_failures)}): {', '.join(telegram_failures)}\n"
            if telegram_failures else ""
        )
        send_telegram(
            f"📋 *Resumen escaneo bolsa v2.6*\n\n"
            f"{vix_summary}"
            f"{breadth_summary}"
            f"✅ Alertas enviadas: {stats['alerts']}\n"
            f"🔗 Bloqueadas por correlacion: {stats['corr_guard']}\n"
            f"🛡️ Duplicadas bloqueadas: {stats['duplicate']}\n"
            f"○ Sin senal: {stats['no_signal']}\n"
            f"⚠️ Bloqueadas: {stats['blocked']}\n"
            f"💤 En cooldown: {stats['cooldown']}\n"
            f"❌ Sin datos: {stats['no_data']}\n"
            f"{earnings_summary}"
            f"{telegram_fail_summary}"
        )


if __name__ == "__main__":
    main()
