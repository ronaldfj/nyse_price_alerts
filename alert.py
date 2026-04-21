"""
Stock Sentinel Bot v2 — Alertas técnicas para NYSE/Nasdaq
Iteración 1 aplicada:
  - Score por capas: regime / setup / trigger
  - R:R estructural real usando swing low + ATR buffer
  - Pendiente de EMA200 para evitar tendencias planas
  - Relative strength simple vs SPY (20 sesiones)
  - Soporte a market_context_stocks.json por defecto
  - Uso real de caution_level desde market_context
  - Logging más claro para debugging y tuning
  - DRY_RUN para pruebas sin Telegram
"""

from __future__ import annotations

import json
import logging
import os
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import pandas as pd
import requests
import yfinance as yf

# ── Logging ───────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("stock-sentinel-v2")

# ── Universo de acciones ──────────────────────────────────────────────────────
STOCK_NAMES = {
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
    "SPY": "S&P 500 ETF",
    "QQQ": "Nasdaq 100 ETF",
}

STOCK_GROUPS = {
    "AAPL": "Tech",
    "MSFT": "Tech",
    "NVDA": "Tech",
    "AMZN": "Tech",
    "GOOGL": "Tech",
    "META": "Tech",
    "AVGO": "Tech",
    "TSLA": "Consumer",
    "HD": "Consumer",
    "PG": "Consumer",
    "COST": "Consumer",
    "JPM": "Finance",
    "V": "Finance",
    "MA": "Finance",
    "BRK-B": "Finance",
    "UNH": "Health",
    "SPY": "ETF",
    "QQQ": "ETF",
}

STOCKS = list(STOCK_NAMES.keys())

# ── Configuración ─────────────────────────────────────────────────────────────
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")
STATE_FILE = os.getenv("STOCK_STATE_FILE", "stock_state.json")
DRY_RUN = os.getenv("DRY_RUN", "false").lower() == "true"

MIN_SCORE = float(os.getenv("MIN_SCORE", "6.0"))
MIN_RR = float(os.getenv("MIN_RR", "1.9"))
COOLDOWN = int(os.getenv("COOLDOWN_HOURS", "48")) * 3600
EARNINGS_BUFFER_DAYS = int(os.getenv("EARNINGS_BUFFER_DAYS", "5"))
VIX_BLOCK_LEVEL = float(os.getenv("VIX_BLOCK_LEVEL", "30.0"))
VIX_CAUTION_LEVEL = float(os.getenv("VIX_CAUTION_LEVEL", "22.0"))
TRIGGER_VOL_RATIO = float(os.getenv("TRIGGER_VOL_RATIO", "1.4"))
SETUP_RSI_MIN = float(os.getenv("SETUP_RSI_MIN", "45"))
SETUP_RSI_MAX = float(os.getenv("SETUP_RSI_MAX", "65"))
RS_LOOKBACK = int(os.getenv("RS_LOOKBACK", "20"))
SWING_LOOKBACK = int(os.getenv("SWING_LOOKBACK", "12"))

DEFAULT_CONTEXT_CANDIDATES = (
    os.getenv("MARKET_CONTEXT_FILE", ""),
    "market_context_stocks.json",
    "market_context.json",
)

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
    rsi: float = 0.0
    adx: float = 0.0
    group: str = "Other"
    earnings_date: str = ""
    regime_score: float = 0.0
    setup_score: float = 0.0
    trigger_score: float = 0.0
    extension_pct: float = 0.0
    rs20: float = 0.0
    reasons: list[str] = field(default_factory=list)
    blocked: list[str] = field(default_factory=list)

    @property
    def should_alert(self) -> bool:
        return self.score >= MIN_SCORE and self.rr >= MIN_RR and not self.blocked


# ── Telegram ──────────────────────────────────────────────────────────────────
def send_telegram(msg: str) -> bool:
    if DRY_RUN:
        log.info("[DRY RUN] Mensaje:\n%s", msg)
        return True
    if not TELEGRAM_BOT_TOKEN:
        log.warning("TELEGRAM_BOT_TOKEN no configurado")
        return False

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    try:
        resp = requests.post(
            url,
            json={"chat_id": TELEGRAM_CHAT_ID, "text": msg, "parse_mode": "Markdown"},
            timeout=15,
        )
        if resp.status_code != 200:
            log.warning("Telegram %s: %s", resp.status_code, resp.text[:120])
            return False
        return True
    except Exception as exc:
        log.error("Telegram error: %s", exc)
        return False


# ── Estado ────────────────────────────────────────────────────────────────────
def load_state() -> dict:
    try:
        path = Path(STATE_FILE)
        return json.loads(path.read_text()) if path.exists() else {}
    except Exception as exc:
        log.error("Cargando estado: %s", exc)
        return {}


def save_state(state: dict) -> None:
    try:
        Path(STATE_FILE).write_text(json.dumps(state, indent=2))
    except Exception as exc:
        log.error("Guardando estado: %s", exc)


# ── Contexto macro manual ─────────────────────────────────────────────────────
def resolve_market_context_file() -> Path | None:
    for candidate in DEFAULT_CONTEXT_CANDIDATES:
        if not candidate:
            continue
        path = Path(candidate)
        if path.exists():
            return path
    return None


def load_market_context() -> dict:
    """
    Carga market_context_stocks.json o market_context.json.
    """
    path = resolve_market_context_file()
    if path is None:
        log.info("Sin archivo de contexto macro manual")
        return {}

    try:
        raw = json.loads(path.read_text())
        if isinstance(raw, dict):
            log.info("Contexto cargado desde %s", path.name)
            return raw
    except Exception as exc:
        log.warning("No se pudo leer contexto %s: %s", path, exc)

    return {}


def get_symbol_context(context: dict, symbol: str) -> dict:
    merged = {}
    merged.update(context.get("GLOBAL", {}))
    merged.update(context.get(symbol, {}))
    return merged


def normalize_caution_adjustment(sym_context: dict) -> tuple[float, str]:
    """
    Traduce caution_level a ajuste de score si el usuario no lo especificó.
    """
    level = str(sym_context.get("caution_level", "")).upper().strip()
    explicit = sym_context.get("score_adjustment")
    note = sym_context.get("note", "")

    if explicit is not None:
        try:
            return float(explicit), note
        except (TypeError, ValueError):
            pass

    mapping = {
        "NORMAL": 0.0,
        "ELEVATED": -0.25,
        "HIGH": -0.5,
        "RISK_OFF": -1.0,
    }
    return mapping.get(level, 0.0), note


# ── VIX — filtro macro global ─────────────────────────────────────────────────
def fetch_vix() -> Optional[float]:
    try:
        df = yf.Ticker("^VIX").history(period="2d", interval="1d", auto_adjust=False)
        if df is not None and not df.empty:
            return round(float(df["Close"].iloc[-1]), 2)
    except Exception as exc:
        log.warning("VIX no disponible: %s", exc)
    return None


# ── Earnings — filtro de riesgo binario ───────────────────────────────────────
def get_earnings_info(symbol: str) -> tuple[Optional[str], bool]:
    """
    Retorna (fecha_earnings_str, earnings_proximos).
    Usa calendar si está disponible y hace fallback simple si no.
    """
    try:
        ticker = yf.Ticker(symbol)
        earnings_date = None

        cal = ticker.calendar
        if isinstance(cal, dict):
            earnings_date = cal.get("Earnings Date")
            if isinstance(earnings_date, list) and earnings_date:
                earnings_date = earnings_date[0]
        elif isinstance(cal, pd.DataFrame) and not cal.empty and "Earnings Date" in cal.index:
            earnings_date = cal.loc["Earnings Date"].iloc[0]

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

        days_diff = abs((earnings_dt - now).days)
        date_str = earnings_dt.strftime("%Y-%m-%d")
        return date_str, days_diff <= EARNINGS_BUFFER_DAYS

    except Exception as exc:
        log.debug("%s: earnings no disponibles — %s", symbol, exc)
        return None, False


# ── Indicadores técnicos ──────────────────────────────────────────────────────
def add_indicators(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()

    # EMAs
    df["ema20"] = df["Close"].ewm(span=20, adjust=False).mean()
    df["ema50"] = df["Close"].ewm(span=50, adjust=False).mean()
    df["ema200"] = df["Close"].ewm(span=200, adjust=False).mean()

    # RSI Wilder
    delta = df["Close"].diff()
    gain = delta.where(delta > 0, 0.0).ewm(com=13, adjust=False).mean()
    loss = (-delta.where(delta < 0, 0.0)).ewm(com=13, adjust=False).mean()
    df["rsi"] = 100 - (100 / (1 + gain / (loss + 1e-9)))

    # True Range + ATR
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

    # ADX real con DI+/DI-
    up_move = df["High"].diff()
    dn_move = (-df["Low"].diff())
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

    # Pendientes
    df["ema200_slope_5"] = df["ema200"] - df["ema200"].shift(5)
    df["ema20_slope_3"] = df["ema20"] - df["ema20"].shift(3)

    # Máximos / mínimos recientes
    df["prior_high_5"] = df["High"].shift(1).rolling(5).max()
    df["prior_low_12"] = df["Low"].shift(1).rolling(SWING_LOOKBACK).min()

    return df


# ── Descarga ──────────────────────────────────────────────────────────────────
def fetch_data(symbol: str) -> Optional[pd.DataFrame]:
    try:
        df = yf.Ticker(symbol).history(period="2y", interval="1d", auto_adjust=True)
    except Exception as exc:
        log.warning("%s: error en descarga — %s", symbol, exc)
        return None

    required = {"High", "Low", "Close", "Volume"}
    if df is None or df.empty or not required.issubset(df.columns):
        log.warning("%s: datos inválidos", symbol)
        return None

    df = df.dropna(subset=list(required))
    if len(df) < 220:
        log.warning("%s: pocas velas (%s < 220)", symbol, len(df))
        return None

    return df


def compute_relative_strength(df: pd.DataFrame, spy_df: Optional[pd.DataFrame]) -> float:
    if spy_df is None or df is None:
        return 0.0
    if len(df) < RS_LOOKBACK + 3 or len(spy_df) < RS_LOOKBACK + 3:
        return 0.0

    sym_ret = (df["Close"].iloc[-2] / df["Close"].iloc[-2 - RS_LOOKBACK]) - 1.0
    spy_ret = (spy_df["Close"].iloc[-2] / spy_df["Close"].iloc[-2 - RS_LOOKBACK]) - 1.0
    return round((sym_ret - spy_ret) * 100, 2)


# ── Evaluación ────────────────────────────────────────────────────────────────
def evaluate_stock(symbol: str, sym_context: dict, vix: Optional[float], spy_df: Optional[pd.DataFrame]) -> Optional[StockSignal]:
    df = fetch_data(symbol)
    if df is None:
        return None

    earnings_date_str, earnings_near = get_earnings_info(symbol)
    df = add_indicators(df)

    if len(df) < max(220, RS_LOOKBACK + 5):
        return None

    last = df.iloc[-2]  # última vela cerrada
    prev = df.iloc[-3]

    name = STOCK_NAMES.get(symbol, symbol)
    group = STOCK_GROUPS.get(symbol, "Other")
    reasons: list[str] = []
    blocked: list[str] = []

    regime_score = 0.0
    setup_score = 0.0
    trigger_score = 0.0

    # ── Bloqueos duros ────────────────────────────────────────────────────────
    if earnings_near and earnings_date_str:
        blocked.append(
            f"Earnings en {earnings_date_str} (±{EARNINGS_BUFFER_DAYS} días)"
        )

    if vix is not None and vix >= VIX_BLOCK_LEVEL:
        blocked.append(f"VIX={vix:.1f} — mercado en pánico")

    if sym_context.get("hard_block_long"):
        blocked.append(f"Bloqueo manual: {sym_context.get('note', 'sin nota')}")

    extension_pct = ((float(last["Close"]) - float(last["ema200"])) / max(float(last["ema200"]), 1e-9)) * 100
    if extension_pct > 25:
        blocked.append(f"Precio sobreextendido: {extension_pct:.1f}% sobre EMA200")

    if float(last["rsi"]) > 78:
        blocked.append(f"RSI extremo ({float(last['rsi']):.1f})")

    # ── Regime ────────────────────────────────────────────────────────────────
    if float(last["Close"]) > float(last["ema200"]):
        regime_score += 1.0
        reasons.append("Precio > EMA200")

    if float(last["ema50"]) > float(last["ema200"]):
        regime_score += 0.75
        reasons.append("EMA50 > EMA200")

    if float(last["ema200_slope_5"]) > 0:
        regime_score += 0.75
        reasons.append("EMA200 con pendiente positiva")

    if float(last["plus_di"]) > float(last["minus_di"]) and float(last["adx"]) >= 18:
        regime_score += 1.0
        reasons.append(f"Direccionalidad válida (ADX {float(last['adx']):.1f})")
    else:
        blocked.append(
            f"Sin direccionalidad limpia (ADX={float(last['adx']):.1f}, "
            f"DI+={float(last['plus_di']):.1f}, DI-={float(last['minus_di']):.1f})"
        )

    # ── Setup ─────────────────────────────────────────────────────────────────
    pullback_atr = abs(float(last["Close"]) - float(last["ema20"])) / max(float(last["atr"]), 1e-9)
    if 0.15 <= pullback_atr <= 1.20:
        setup_score += 0.8
        reasons.append(f"Distancia operable a EMA20 ({pullback_atr:.2f} ATR)")
    elif pullback_atr < 0.15:
        setup_score += 0.2
        reasons.append("Precio muy cerca de EMA20")
    else:
        blocked.append(f"Precio demasiado lejos de EMA20 ({pullback_atr:.2f} ATR)")

    rsi = float(last["rsi"])
    prev_rsi = float(prev["rsi"])
    if SETUP_RSI_MIN <= rsi <= SETUP_RSI_MAX and rsi >= prev_rsi:
        setup_score += 1.0
        reasons.append(f"RSI en zona útil ({rsi:.1f})")
    elif 40 <= rsi < SETUP_RSI_MIN and rsi > prev_rsi:
        setup_score += 0.4
        reasons.append(f"RSI recuperando ({rsi:.1f})")
    else:
        blocked.append(f"RSI fuera de zona de setup ({rsi:.1f})")

    if float(last["ema20"]) > float(last["ema50"]) and float(last["ema20_slope_3"]) > 0:
        setup_score += 0.8
        reasons.append("EMA20 > EMA50 con pendiente positiva")
    elif float(last["Close"]) > float(last["ema50"]):
        setup_score += 0.4
        reasons.append("Precio sostiene EMA50")

    rs20 = 0.0 if symbol == "SPY" else compute_relative_strength(df, spy_df)
    if rs20 > 0:
        setup_score += 0.8
        reasons.append(f"Relative strength vs SPY: {rs20:+.2f}%")
    elif symbol != "SPY":
        blocked.append(f"Sin RS positiva vs SPY: {rs20:+.2f}%")

    # ── Trigger ───────────────────────────────────────────────────────────────
    broke_prior_high = float(last["Close"]) > float(last["prior_high_5"])
    bullish_reclaim = float(last["Close"]) > float(last["ema20"]) and float(prev["Close"]) <= float(prev["ema20"])
    positive_momentum = float(last["macd_hist"]) > float(prev["macd_hist"])

    if broke_prior_high:
        trigger_score += 1.0
        reasons.append("Ruptura de máximo reciente")
    elif bullish_reclaim:
        trigger_score += 0.6
        reasons.append("Reclaim sobre EMA20")

    if positive_momentum and float(last["macd_hist"]) > 0:
        trigger_score += 0.8
        reasons.append("MACD histograma acelerando > 0")
    elif positive_momentum:
        trigger_score += 0.4
        reasons.append("MACD mejorando")

    vol_ratio = float(last["vol_ratio"])
    if vol_ratio >= TRIGGER_VOL_RATIO:
        trigger_score += 0.8
        reasons.append(f"Volumen de confirmación ({vol_ratio:.2f}x)")
    elif vol_ratio >= 1.05:
        trigger_score += 0.3
        reasons.append(f"Volumen aceptable ({vol_ratio:.2f}x)")
    else:
        blocked.append(f"Volumen débil ({vol_ratio:.2f}x)")

    # ── Ajustes de contexto ───────────────────────────────────────────────────
    score_adjustment, context_note = normalize_caution_adjustment(sym_context)
    if vix is not None and VIX_CAUTION_LEVEL <= vix < VIX_BLOCK_LEVEL:
        score_adjustment -= 0.5
        reasons.append(f"VIX elevado ({vix:.1f})")

    total_score = round(regime_score + setup_score + trigger_score + score_adjustment, 2)
    if score_adjustment != 0:
        reasons.append(f"Ajuste macro/manual: {score_adjustment:+.2f}")
    if context_note:
        reasons.append(f"Contexto: {context_note}")

    # ── Gestión de riesgo estructural ─────────────────────────────────────────
    entry = float(last["Close"])
    atr = max(float(last["atr"]), entry * 0.008)
    prior_swing_low = float(last["prior_low_12"]) if pd.notna(last["prior_low_12"]) else entry - 1.8 * atr

    atr_stop = entry - 1.8 * atr
    structural_stop = min(prior_swing_low - 0.20 * atr, atr_stop)
    stop = min(entry - 0.25 * atr, structural_stop)  # evita stops por encima del entry

    risk = entry - stop
    if risk <= 0:
        blocked.append("Riesgo inválido: stop no consistente")
        stop = entry - 1.8 * atr
        risk = entry - stop

    tp = entry + 2.2 * risk
    rr = (tp - entry) / max(risk, 1e-9)

    return StockSignal(
        symbol=symbol,
        name=name,
        price=entry,
        score=total_score,
        rr=round(rr, 2),
        tp=round(tp, 2),
        stop=round(stop, 2),
        atr=round(atr, 2),
        rsi=round(rsi, 2),
        adx=round(float(last["adx"]), 2),
        group=group,
        earnings_date=earnings_date_str or "",
        regime_score=round(regime_score, 2),
        setup_score=round(setup_score, 2),
        trigger_score=round(trigger_score, 2),
        extension_pct=round(extension_pct, 2),
        rs20=round(rs20, 2),
        reasons=reasons,
        blocked=blocked,
    )


# ── Formato de alerta ─────────────────────────────────────────────────────────
def format_alert(sig: StockSignal, vix: Optional[float]) -> str:
    score_emoji = "🔥" if sig.score >= 7.0 else "📈"
    vix_line = f"📉 *VIX:* {vix:.1f}\n" if vix is not None else ""
    earnings_line = f"📅 *Próximos earnings:* {sig.earnings_date}\n" if sig.earnings_date else ""
    rs_line = f"⚔️ *RS vs SPY (20d):* {sig.rs20:+.2f}%\n" if sig.symbol != "SPY" else ""

    signal_breakdown = (
        f"🧩 *Regime/Setup/Trigger:* "
        f"{sig.regime_score:.1f}/{sig.setup_score:.1f}/{sig.trigger_score:.1f}\n"
    )

    return (
        f"{score_emoji} *ALERTA BOLSA v2: {sig.name} ({sig.symbol})*\n\n"
        f"💰 *Precio:* ${sig.price:.2f}\n"
        f"📊 *Score:* {sig.score:.1f}\n"
        f"⚖️ *R:R real:* {sig.rr:.2f}x\n"
        f"📏 *ATR:* ${sig.atr:.2f} | *ADX:* {sig.adx:.1f} | *RSI:* {sig.rsi:.1f}\n"
        f"{signal_breakdown}"
        f"{rs_line}"
        f"{vix_line}"
        f"{earnings_line}\n"
        f"🎯 *TARGET:* ${sig.tp:.2f}\n"
        f"🛑 *STOP:* ${sig.stop:.2f}\n\n"
        f"📝 *Confluencias:*\n" + "\n".join(f"  • {reason}" for reason in sig.reasons[:8])
    )


def format_reject_log(sig: StockSignal) -> str:
    if sig.blocked:
        return "; ".join(sig.blocked[:4])
    return "Sin score suficiente"


# ── Main ──────────────────────────────────────────────────────────────────────
def main() -> None:
    state = load_state()
    context = load_market_context()
    now = time.time()

    mode = "DRY RUN" if DRY_RUN else "PRODUCCIÓN"
    log.info("Iniciando escaneo v2 [%s] — %s acciones", mode, len(STOCKS))

    vix = fetch_vix()
    if vix is not None:
        if vix >= VIX_BLOCK_LEVEL:
            vix_status = "PÁNICO"
        elif vix >= VIX_CAUTION_LEVEL:
            vix_status = "NERVIOSO"
        else:
            vix_status = "NORMAL"
        log.info("VIX=%.1f — condición de mercado: %s", vix, vix_status)
    else:
        log.warning("VIX no disponible — se omite filtro macro")

    spy_df = fetch_data("SPY")
    if spy_df is None:
        log.warning("SPY no disponible — se omite relative strength benchmark")

    stats = {k: 0 for k in ("scanned", "cooldown", "no_data", "blocked", "no_signal", "alerts")}

    for symbol in STOCKS:
        last_alert = state.get(symbol, 0)
        remaining = COOLDOWN - (now - last_alert)
        if remaining > 0:
            log.info("COOLDOWN %s: %.1fh restantes", symbol, remaining / 3600)
            stats["cooldown"] += 1
            continue

        stats["scanned"] += 1
        try:
            sym_context = get_symbol_context(context, symbol)
            sig = evaluate_stock(symbol, sym_context, vix, spy_df)

            if sig is None:
                stats["no_data"] += 1
                log.warning("%s: sin datos suficientes", symbol)
                continue

            if sig.blocked:
                stats["blocked"] += 1
                log.info(
                    "%s: score=%.1f | RR=%.2f | regime/setup/trigger=%.1f/%.1f/%.1f | BLOQUEADO | %s",
                    sig.symbol,
                    sig.score,
                    sig.rr,
                    sig.regime_score,
                    sig.setup_score,
                    sig.trigger_score,
                    format_reject_log(sig),
                )
            elif sig.should_alert:
                if send_telegram(format_alert(sig, vix)):
                    state[sig.symbol] = now
                    save_state(state)
                    stats["alerts"] += 1
                    log.info(
                        "✅ ALERTA %s | score=%.1f | RR=%.2f | RS20=%+.2f%%",
                        sig.symbol,
                        sig.score,
                        sig.rr,
                        sig.rs20,
                    )
            else:
                stats["no_signal"] += 1
                log.info(
                    "%s: score=%.1f | RR=%.2f | regime/setup/trigger=%.1f/%.1f/%.1f | sin señal",
                    sig.symbol,
                    sig.score,
                    sig.rr,
                    sig.regime_score,
                    sig.setup_score,
                    sig.trigger_score,
                )

            time.sleep(1.5)

        except Exception as exc:
            log.error("%s: excepción — %s", symbol, exc, exc_info=True)

    log.info(
        "Escaneo completado | Escaneados:%s | Cooldown:%s | Sin datos:%s | Bloqueados:%s | Sin señal:%s | Alertas:%s",
        stats["scanned"],
        stats["cooldown"],
        stats["no_data"],
        stats["blocked"],
        stats["no_signal"],
        stats["alerts"],
    )

    if not DRY_RUN:
        vix_summary = f"📉 VIX: {vix:.1f}\n" if vix is not None else ""
        send_telegram(
            f"📋 *Resumen escaneo bolsa v2*\n\n"
            f"{vix_summary}"
            f"✅ Alertas enviadas: {stats['alerts']}\n"
            f"○ Sin señal: {stats['no_signal']}\n"
            f"⚠️ Bloqueadas: {stats['blocked']}\n"
            f"💤 En cooldown: {stats['cooldown']}\n"
            f"❌ Sin datos: {stats['no_data']}"
        )


if __name__ == "__main__":
    main()
