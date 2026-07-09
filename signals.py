"""
Stock Sentinel — signals.py
============================
Modulo compartido para indicadores y calculos comunes entre alert.py y backtest.py.

v2.9 motivacion:
La duplicacion de logica entre alert.py y backtest.py fue identificada como riesgo
critico: cualquier cambio de scoring requiere actualizar dos lugares y arriesga
divergencia silenciosa (ya nos paso con los reportes identicos en v2.7).

Esta primera version extrae las funciones DETERMINISTICAS que son identicas en
ambos lados y no dependen del scoring del playbook:

  - compute_supertrend_vectorized: Supertrend O(n) sin loops Python
  - add_indicators: EMA, RSI, ATR, ADX, MACD, vol_ratio, prior highs/lows, slopes
  - compute_relative_strength: RS vs SPY con alineacion temporal correcta

NO incluye evaluate_stock ni evaluate_bar — esos tienen scoring acoplado al modo
(live vs backtest). Su unificacion completa es trabajo de iteraciones futuras.
"""

from __future__ import annotations

import logging
from typing import Optional

import numpy as np
import pandas as pd

log = logging.getLogger("stock-sentinel-v2")


# ── Defaults publicos (sobrescribibles desde el modulo importador via env) ──
SUPERTREND_PERIOD_DEFAULT = 10
SUPERTREND_MULTIPLIER_DEFAULT = 3.0
SWING_LOOKBACK_DEFAULT = 12
RS_LOOKBACK_DEFAULT = 20


# ── Supertrend (vectorizado, O(n)) ──────────────────────────────────────────
def compute_supertrend_vectorized(
    df: pd.DataFrame,
    period: int = SUPERTREND_PERIOD_DEFAULT,
    multiplier: float = SUPERTREND_MULTIPLIER_DEFAULT,
) -> pd.DataFrame:
    """
    Calcula Supertrend completamente vectorizado usando numpy.
    Anade columnas: st_atr, st_upper_raw, st_lower_raw, st_upper, st_lower,
    st_trend (1=alcista, -1=bajista), st_value (valor activo).
    """
    n = len(df)
    high = df["High"].to_numpy(dtype=float)
    low = df["Low"].to_numpy(dtype=float)
    close = df["Close"].to_numpy(dtype=float)

    # RMA (Wilder) del TR — vectorizado via pandas EWM (misma inicializacion que add_indicators)
    prev_close = np.empty(n, dtype=float)
    prev_close[0] = close[0]
    prev_close[1:] = close[:-1]
    tr = np.maximum(
        high - low,
        np.maximum(
            np.abs(high - prev_close),
            np.abs(low - prev_close),
        ),
    )
    tr[0] = high[0] - low[0]

    alpha = 1.0 / period
    rma = pd.Series(tr).ewm(alpha=alpha, adjust=False).mean().to_numpy()

    hl2 = (high + low) / 2.0
    upper_raw = hl2 + multiplier * rma
    lower_raw = hl2 - multiplier * rma

    upper = upper_raw.copy()
    lower = lower_raw.copy()
    trend = np.ones(n, dtype=float)
    st_value = np.empty(n, dtype=float)
    st_value[0] = upper_raw[0]

    for i in range(1, n):
        upper[i] = upper_raw[i] if (upper_raw[i] < upper[i - 1] or close[i - 1] > upper[i - 1]) else upper[i - 1]
        lower[i] = lower_raw[i] if (lower_raw[i] > lower[i - 1] or close[i - 1] < lower[i - 1]) else lower[i - 1]
        if trend[i - 1] == -1.0:
            trend[i] = 1.0 if close[i] > upper[i - 1] else -1.0
        else:
            trend[i] = -1.0 if close[i] < lower[i - 1] else 1.0
        st_value[i] = lower[i] if trend[i] == 1.0 else upper[i]

    out = df.copy()
    out["st_atr"] = rma
    out["st_upper_raw"] = upper_raw
    out["st_lower_raw"] = lower_raw
    out["st_upper"] = upper
    out["st_lower"] = lower
    out["st_trend"] = trend
    out["st_value"] = st_value
    return out


# ── Indicadores tecnicos canonicos ──────────────────────────────────────────
def add_indicators(
    df: pd.DataFrame,
    swing_lookback: int = SWING_LOOKBACK_DEFAULT,
    supertrend_period: int = SUPERTREND_PERIOD_DEFAULT,
    supertrend_multiplier: float = SUPERTREND_MULTIPLIER_DEFAULT,
) -> pd.DataFrame:
    """
    Agrega EMA20/50/200, RSI Wilder, ATR Wilder, ADX/DI+/DI-, MACD,
    vol_ratio, slopes, prior highs/lows y Supertrend.

    Esta funcion es la UNICA fuente de verdad para indicadores en todo el sistema.
    """
    df = df.copy()

    # EMAs
    df["ema20"] = df["Close"].ewm(span=20, adjust=False).mean()
    df["ema50"] = df["Close"].ewm(span=50, adjust=False).mean()
    df["ema200"] = df["Close"].ewm(span=200, adjust=False).mean()

    # RSI Wilder (com=13 equivale a alpha=1/14 = Wilder)
    delta = df["Close"].diff()
    gain = delta.where(delta > 0, 0.0).ewm(com=13, adjust=False).mean()
    loss = (-delta.where(delta < 0, 0.0)).ewm(com=13, adjust=False).mean()
    df["rsi"] = 100 - (100 / (1 + gain / (loss + 1e-9)))

    # ATR Wilder
    prev_close = df["Close"].shift(1)
    tr = pd.concat(
        [
            df["High"] - df["Low"],
            (df["High"] - prev_close).abs(),
            (df["Low"] - prev_close).abs(),
        ],
        axis=1,
    ).max(axis=1)
    df["atr"] = tr.ewm(com=13, adjust=False).mean()

    # ADX, DI+, DI-
    up_move = df["High"].diff()
    dn_move = -df["Low"].diff()
    plus_dm = up_move.where((up_move > dn_move) & (up_move > 0), 0.0)
    minus_dm = dn_move.where((dn_move > up_move) & (dn_move > 0), 0.0)
    plus_di = 100 * plus_dm.ewm(com=13, adjust=False).mean() / (df["atr"] + 1e-9)
    minus_di = 100 * minus_dm.ewm(com=13, adjust=False).mean() / (df["atr"] + 1e-9)
    dx = 100 * (plus_di - minus_di).abs() / (plus_di + minus_di + 1e-9)
    df["adx"] = dx.ewm(com=13, adjust=False).mean()
    df["plus_di"] = plus_di
    df["minus_di"] = minus_di

    # MACD
    ema12 = df["Close"].ewm(span=12, adjust=False).mean()
    ema26 = df["Close"].ewm(span=26, adjust=False).mean()
    df["macd"] = ema12 - ema26
    df["macd_sig"] = df["macd"].ewm(span=9, adjust=False).mean()
    df["macd_hist"] = df["macd"] - df["macd_sig"]

    # Volumen relativo
    df["vol_sma20"] = df["Volume"].rolling(20).mean()
    df["vol_ratio"] = df["Volume"] / (df["vol_sma20"] + 1e-9)

    # Slopes
    df["ema200_slope_5"] = df["ema200"] - df["ema200"].shift(5)
    df["ema200_slope_3"] = df["ema200"] - df["ema200"].shift(3)
    df["ema20_slope_3"] = df["ema20"] - df["ema20"].shift(3)

    # Prior highs / lows (todos shifteados — anti look-ahead)
    df["prior_high_5"] = df["High"].shift(1).rolling(5).max()
    df["prior_high_20"] = df["High"].shift(1).rolling(20).max()
    df["prior_low_5"] = df["Low"].shift(1).rolling(5).min()
    df["prior_low_12"] = df["Low"].shift(1).rolling(swing_lookback).min()
    df["prior_low_20"] = df["Low"].shift(1).rolling(20).min()

    # Supertrend
    df = compute_supertrend_vectorized(df, period=supertrend_period, multiplier=supertrend_multiplier)

    return df


# ── Relative Strength vs SPY (alineado temporalmente) ──────────────────────
def compute_relative_strength(
    df: pd.DataFrame,
    spy_df: Optional[pd.DataFrame],
    lookback: int = RS_LOOKBACK_DEFAULT,
    symbol: str = "",
) -> float:
    """
    Calcula la diferencia de retornos entre el activo y SPY en `lookback` sesiones.
    Devuelve 0.0 si no hay datos suficientes o no se pueden alinear.

    v2.5 Fix #2: alineacion temporal por interseccion de indices — evita errores
    cuando asset y SPY tienen fechas distintas (holidays, IPOs recientes, etc).

    v2.10 Fix: yfinance devuelve indices con tz distinta segun el path de descarga
    (yf.Ticker().history() → tz-aware "America/New_York"; yf.download(group_by=
    "ticker") en batch → tz-naive). Si df y spy_df vienen de paths distintos, la
    interseccion de indices da vacio SIN error — esto devolvia 0.0 en silencio
    para simbolos con historia de sobra, indistinguible del caso legitimo de
    "no hay suficiente overlap". Se normaliza a tz-naive antes de intersectar
    para que el resultado no dependa de que fetch_data() haya usado descarga
    individual o batch para cada uno.
    """
    if spy_df is None or len(df) < lookback + 2 or len(spy_df) < lookback + 2:
        return 0.0

    asset_close = df["Close"]
    spy_close = spy_df["Close"]
    if isinstance(asset_close.index, pd.DatetimeIndex) and asset_close.index.tz is not None:
        asset_close = asset_close.tz_localize(None)
    if isinstance(spy_close.index, pd.DatetimeIndex) and spy_close.index.tz is not None:
        spy_close = spy_close.tz_localize(None)

    common_idx = asset_close.index.intersection(spy_close.index)
    if len(common_idx) < lookback + 2:
        log.warning(
            "%s: RS sin overlap suficiente vs SPY pese a tener historia de sobra "
            "(asset=%s barras, spy=%s barras, comunes=%s) — posible mismatch de "
            "formato de indice entre fuentes de descarga",
            symbol or "<simbolo>", len(df), len(spy_df), len(common_idx),
        )
        return 0.0

    asset_aligned = asset_close.reindex(common_idx).dropna()
    spy_aligned = spy_close.reindex(common_idx).dropna()

    # Re-intersectar tras dropna: un NaN en posiciones distintas reduce el universo comun
    valid_idx = asset_aligned.index.intersection(spy_aligned.index)
    if len(valid_idx) < lookback + 2:
        return 0.0

    asset_aligned = asset_aligned.loc[valid_idx]
    spy_aligned = spy_aligned.loc[valid_idx]

    asset_base = float(asset_aligned.iloc[-2 - lookback])
    spy_base = float(spy_aligned.iloc[-2 - lookback])

    # Guard contra precios cero o negativos (datos corruptos)
    if asset_base <= 0.0 or spy_base <= 0.0:
        return 0.0

    asset_ret = (float(asset_aligned.iloc[-2]) / asset_base - 1.0) * 100
    spy_ret = (float(spy_aligned.iloc[-2]) / spy_base - 1.0) * 100
    return round(asset_ret - spy_ret, 2)


# ── Validacion de datos ────────────────────────────────────────────────────
def validate_ohlcv(df: pd.DataFrame, min_bars: int = 220) -> bool:
    """True si el DataFrame es valido para evaluacion."""
    if df is None or df.empty:
        return False
    required = {"High", "Low", "Close", "Volume"}
    if not required.issubset(df.columns):
        return False
    df_clean = df.dropna(subset=list(required))
    return len(df_clean) >= min_bars
