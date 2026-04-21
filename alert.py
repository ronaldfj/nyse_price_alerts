"""
Stock Sentinel Bot — Alertas técnicas para NYSE/Nasdaq
Versión con filtros de madurez:
  - ATR real (True Range con High/Low)
  - ADX real con DI+/DI-
  - RSI Wilder correcto
  - Sistema de score graduado
  - Filtro de volumen relativo
  - MACD como señal adicional
  - EMA50 como nivel intermedio
  - Bloqueo por earnings próximos (±5 días)
  - Filtro VIX macro global
  - market_context.json para sesgo manual
  - Logging estructurado con campos correctos
  - DRY_RUN para pruebas sin Telegram
"""

import logging
import os
import time
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import pandas as pd
import yfinance as yf
import requests

# ── Logging ───────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("stock-sentinel")

# ── Universo de acciones ──────────────────────────────────────────────────────
STOCK_NAMES = {
    "AAPL":  "Apple Inc.",
    "MSFT":  "Microsoft Corp.",
    "NVDA":  "NVIDIA Corp.",
    "AMZN":  "Amazon.com Inc.",
    "GOOGL": "Alphabet Inc.",
    "META":  "Meta Platforms",
    "TSLA":  "Tesla, Inc.",
    "BRK-B": "Berkshire Hathaway",
    "V":     "Visa Inc.",
    "JPM":   "JPMorgan Chase",
    "UNH":   "UnitedHealth Group",
    "MA":    "Mastercard Inc.",
    "AVGO":  "Broadcom Inc.",
    "HD":    "Home Depot Inc.",
    "PG":    "Procter & Gamble",
    "COST":  "Costco Wholesale",
    "SPY":   "S&P 500 ETF",
    "QQQ":   "Nasdaq 100 ETF",
}

STOCK_GROUPS = {
    "AAPL": "Tech",  "MSFT": "Tech",  "NVDA": "Tech",
    "AMZN": "Tech",  "GOOGL": "Tech", "META": "Tech",
    "AVGO": "Tech",
    "TSLA": "Consumer", "HD": "Consumer", "PG": "Consumer",
    "COST": "Consumer",
    "JPM": "Finance", "V": "Finance", "MA": "Finance",
    "BRK-B": "Finance",
    "UNH": "Health",
    "SPY": "ETF", "QQQ": "ETF",
}

STOCKS = list(STOCK_NAMES.keys())

# ── Configuración ─────────────────────────────────────────────────────────────
TELEGRAM_BOT_TOKEN   = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID     = os.getenv("TELEGRAM_CHAT_ID", "")
STATE_FILE           = os.getenv("STOCK_STATE_FILE", "stock_state.json")
MARKET_CONTEXT_FILE  = os.getenv("MARKET_CONTEXT_FILE", "market_context.json")
DRY_RUN              = os.getenv("DRY_RUN", "false").lower() == "true"

MIN_SCORE            = float(os.getenv("MIN_SCORE", "6.0"))
MIN_RR               = float(os.getenv("MIN_RR", "1.8"))
COOLDOWN             = int(os.getenv("COOLDOWN_HOURS", "48")) * 3600
EARNINGS_BUFFER_DAYS = int(os.getenv("EARNINGS_BUFFER_DAYS", "5"))
VIX_BLOCK_LEVEL      = float(os.getenv("VIX_BLOCK_LEVEL", "30.0"))
VIX_CAUTION_LEVEL    = float(os.getenv("VIX_CAUTION_LEVEL", "22.0"))


# ── Dataclass de señal ────────────────────────────────────────────────────────
@dataclass
class StockSignal:
    symbol:        str
    name:          str
    price:         float
    score:         float
    rr:            float
    tp:            float
    stop:          float
    atr:           float
    rsi:           float = 0.0
    adx:           float = 0.0
    group:         str   = "Other"
    earnings_date: str   = ""
    reasons:       list  = field(default_factory=list)
    blocked:       list  = field(default_factory=list)

    @property
    def should_alert(self) -> bool:
        return self.score >= MIN_SCORE and self.rr >= MIN_RR and not self.blocked


# ── Telegram ──────────────────────────────────────────────────────────────────
def send_telegram(msg: str) -> bool:
    if DRY_RUN:
        log.info(f"[DRY RUN] Mensaje:\n{msg}")
        return True
    if not TELEGRAM_BOT_TOKEN:
        log.warning("TELEGRAM_BOT_TOKEN no configurado")
        return False
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    try:
        r = requests.post(
            url,
            json={"chat_id": TELEGRAM_CHAT_ID, "text": msg, "parse_mode": "Markdown"},
            timeout=15,
        )
        if r.status_code != 200:
            log.warning(f"Telegram {r.status_code}: {r.text[:80]}")
            return False
        return True
    except Exception as e:
        log.error(f"Telegram: {e}")
        return False


# ── Estado ────────────────────────────────────────────────────────────────────
def load_state() -> dict:
    try:
        p = Path(STATE_FILE)
        return json.loads(p.read_text()) if p.exists() else {}
    except Exception as e:
        log.error(f"Cargando estado: {e}")
        return {}

def save_state(state: dict) -> None:
    try:
        Path(STATE_FILE).write_text(json.dumps(state, indent=2))
    except Exception as e:
        log.error(f"Guardando estado: {e}")


# ── Contexto macro manual ─────────────────────────────────────────────────────
def load_market_context() -> dict:
    """
    Carga market_context.json si existe.
    Misma estructura que el crypto bot — permite sesgo manual por símbolo.
    """
    p = Path(MARKET_CONTEXT_FILE)
    if not p.exists():
        return {}
    try:
        raw = json.loads(p.read_text())
        return raw if isinstance(raw, dict) else {}
    except Exception as e:
        log.warning(f"No se pudo leer {MARKET_CONTEXT_FILE}: {e}")
        return {}

def get_symbol_context(context: dict, symbol: str) -> dict:
    """Fusiona GLOBAL + símbolo específico, símbolo tiene prioridad."""
    merged = {}
    merged.update(context.get("GLOBAL", {}))
    merged.update(context.get(symbol, {}))
    return merged


# ── VIX — filtro macro global ─────────────────────────────────────────────────
def fetch_vix() -> Optional[float]:
    """
    Obtiene el VIX actual vía yfinance.
    VIX > VIX_BLOCK_LEVEL  → bloquea todas las señales (mercado en pánico)
    VIX > VIX_CAUTION_LEVEL → penaliza score (mercado nervioso)
    """
    try:
        df = yf.Ticker("^VIX").history(period="2d", interval="1d")
        if df is not None and not df.empty:
            return round(float(df["Close"].iloc[-1]), 2)
    except Exception as e:
        log.warning(f"VIX no disponible: {e}")
    return None


# ── Earnings — filtro de riesgo binario ───────────────────────────────────────
def get_earnings_info(symbol: str) -> tuple[Optional[str], bool]:
    """
    Retorna (fecha_earnings_str, earnings_próximos).
    earnings_próximos = True si hay earnings en ±EARNINGS_BUFFER_DAYS días.
    Usa ticker.calendar de yfinance.
    """
    try:
        ticker = yf.Ticker(symbol)
        cal = ticker.calendar

        # yfinance puede retornar dict o DataFrame según la versión
        earnings_date = None
        if isinstance(cal, dict):
            earnings_date = cal.get("Earnings Date")
            if isinstance(earnings_date, list) and earnings_date:
                earnings_date = earnings_date[0]
        elif isinstance(cal, pd.DataFrame) and not cal.empty:
            if "Earnings Date" in cal.index:
                val = cal.loc["Earnings Date"].iloc[0]
                earnings_date = val

        if earnings_date is None:
            return None, False

        # Normalizar a datetime
        if hasattr(earnings_date, "to_pydatetime"):
            earnings_dt = earnings_date.to_pydatetime()
        elif isinstance(earnings_date, datetime):
            earnings_dt = earnings_date
        else:
            return str(earnings_date), False

        # Comparar con hoy (sin timezone)
        now = datetime.now(timezone.utc)
        if earnings_dt.tzinfo is None:
            earnings_dt = earnings_dt.replace(tzinfo=timezone.utc)

        days_diff = abs((earnings_dt - now).days)
        date_str  = earnings_dt.strftime("%Y-%m-%d")
        is_near   = days_diff <= EARNINGS_BUFFER_DAYS

        return date_str, is_near

    except Exception as e:
        log.debug(f"{symbol}: earnings no disponibles — {e}")
        return None, False


# ── Indicadores técnicos ──────────────────────────────────────────────────────
def add_indicators(df: pd.DataFrame) -> pd.DataFrame:
    # EMAs
    df["ema20"]  = df["Close"].ewm(span=20,  adjust=False).mean()
    df["ema50"]  = df["Close"].ewm(span=50,  adjust=False).mean()
    df["ema200"] = df["Close"].ewm(span=200, adjust=False).mean()

    # RSI Wilder
    delta = df["Close"].diff()
    gain  = delta.where(delta > 0, 0.0).ewm(com=13, adjust=False).mean()
    loss  = (-delta.where(delta < 0, 0.0)).ewm(com=13, adjust=False).mean()
    df["rsi"] = 100 - (100 / (1 + gain / (loss + 1e-9)))

    # True Range y ATR real
    prev_close = df["Close"].shift(1)
    tr = pd.concat([
        df["High"] - df["Low"],
        (df["High"] - prev_close).abs(),
        (df["Low"]  - prev_close).abs(),
    ], axis=1).max(axis=1)
    df["atr"] = tr.ewm(com=13, adjust=False).mean()

    # ADX real con DI+/DI-
    up_move  = df["High"].diff()
    dn_move  = (-df["Low"].diff())
    plus_dm  = up_move.where((up_move > dn_move) & (up_move > 0), 0.0)
    minus_dm = dn_move.where((dn_move > up_move) & (dn_move > 0), 0.0)
    plus_di  = 100 * plus_dm.ewm(com=13, adjust=False).mean() / (df["atr"] + 1e-9)
    minus_di = 100 * minus_dm.ewm(com=13, adjust=False).mean() / (df["atr"] + 1e-9)
    dx       = 100 * (plus_di - minus_di).abs() / (plus_di + minus_di + 1e-9)
    df["adx"]      = dx.ewm(com=13, adjust=False).mean()
    df["plus_di"]  = plus_di
    df["minus_di"] = minus_di

    # MACD
    ema12           = df["Close"].ewm(span=12, adjust=False).mean()
    ema26           = df["Close"].ewm(span=26, adjust=False).mean()
    df["macd"]      = ema12 - ema26
    df["macd_sig"]  = df["macd"].ewm(span=9, adjust=False).mean()
    df["macd_hist"] = df["macd"] - df["macd_sig"]

    # Volumen relativo
    df["vol_ratio"] = df["Volume"] / (df["Volume"].rolling(20).mean() + 1e-9)

    return df


# ── Descarga ──────────────────────────────────────────────────────────────────
def fetch_data(symbol: str) -> Optional[pd.DataFrame]:
    try:
        df = yf.Ticker(symbol).history(period="2y", interval="1d")
    except Exception as e:
        log.warning(f"{symbol}: error en descarga — {e}")
        return None

    required = {"High", "Low", "Close", "Volume"}
    if df is None or df.empty or not required.issubset(df.columns):
        log.warning(f"{symbol}: datos inválidos")
        return None

    df = df.dropna(subset=list(required))
    if len(df) < 220:
        log.warning(f"{symbol}: pocas velas ({len(df)} < 220)")
        return None

    return df


# ── Evaluación ────────────────────────────────────────────────────────────────
def evaluate_stock(
    symbol: str,
    sym_context: dict,
    vix: Optional[float],
) -> Optional[StockSignal]:

    df = fetch_data(symbol)
    if df is None:
        return None

    # Earnings — consulta antes de calcular indicadores para ahorrar tiempo
    earnings_date_str, earnings_near = get_earnings_info(symbol)

    df = add_indicators(df)

    last = df.iloc[-2]   # última vela cerrada
    prev = df.iloc[-3]

    name  = STOCK_NAMES.get(symbol, symbol)
    group = STOCK_GROUPS.get(symbol, "Other")

    score, reasons, blocked = 0.0, [], []

    # ── Bloqueos duros ────────────────────────────────────────────────────────

    # 1. Earnings próximos — riesgo binario
    if earnings_near and earnings_date_str:
        blocked.append(
            f"Earnings en {earnings_date_str} "
            f"(±{EARNINGS_BUFFER_DAYS} días) — riesgo binario"
        )

    # 2. VIX en pánico — bloqueo global
    if vix is not None and vix >= VIX_BLOCK_LEVEL:
        blocked.append(f"VIX={vix:.1f} — mercado en pánico, sin longs")

    # 3. RSI sobrecomprado extremo
    if last["rsi"] > 78:
        blocked.append(f"RSI sobrecomprado ({last['rsi']:.1f})")

    # 4. Precio muy extendido sobre EMA200
    extension = (last["Close"] - last["ema200"]) / last["ema200"] * 100
    if extension > 25:
        blocked.append(f"Precio {extension:.1f}% sobre EMA200 — sobreextendido")

    # 5. Sin tendencia direccional (bloqueo duro que pediste)
    if last["adx"] < 18 or last["plus_di"] <= last["minus_di"]:
        blocked.append(
            f"Sin tendencia direccional "
            f"(ADX={last['adx']:.1f}, DI+={last['plus_di']:.1f} vs DI-={last['minus_di']:.1f})"
        )

    # 6. Bloqueo manual desde market_context.json
    if sym_context.get("hard_block_long"):
        blocked.append(f"Bloqueado manualmente: {sym_context.get('note', 'sin nota')}")

    # ── Ajuste de score desde contexto macro manual ───────────────────────────
    score_adjustment = float(sym_context.get("score_adjustment", 0.0))

    # ── Penalización por VIX nervioso (no bloqueo) ───────────────────────────
    vix_note = ""
    if vix is not None:
        if vix >= VIX_CAUTION_LEVEL:
            score_adjustment -= 0.5
            vix_note = f"VIX={vix:.1f} — mercado nervioso (-0.5 score)"
        else:
            vix_note = f"VIX={vix:.1f} — condiciones normales"

    # ── Señales de entrada ────────────────────────────────────────────────────

    # 1. Tendencia macro EMA200
    if last["Close"] > last["ema200"]:
        score += 2.0
        reasons.append("Tendencia alcista (>EMA200)")

    # 2. Estructura de EMAs
    if last["ema20"] > last["ema50"] > last["ema200"]:
        score += 1.5
        reasons.append("EMA20 > EMA50 > EMA200 — estructura alcista")
    elif last["Close"] > last["ema50"] > last["ema200"]:
        score += 0.75
        reasons.append("Precio sobre EMA50 y EMA200")

    # 3. ADX con dirección
    if last["adx"] > 25 and last["plus_di"] > last["minus_di"]:
        score += 1.5
        reasons.append(f"Tendencia fuerte ADX={last['adx']:.1f}")
    elif last["adx"] > 18 and last["plus_di"] > last["minus_di"]:
        score += 0.75
        reasons.append(f"Tendencia moderada ADX={last['adx']:.1f}")

    # 4. RSI con momentum
    if 45 < last["rsi"] < 70 and last["rsi"] > prev["rsi"]:
        score += 1.0
        reasons.append(f"RSI momentum ({last['rsi']:.1f}↑)")
    elif 40 < last["rsi"] <= 45:
        score += 0.4
        reasons.append(f"RSI recuperando ({last['rsi']:.1f})")

    # 5. Cruce o precio sobre EMA20
    if last["Close"] > last["ema20"] and prev["Close"] <= prev["ema20"]:
        score += 1.0
        reasons.append("Cruce alcista EMA20")
    elif last["Close"] > last["ema20"]:
        score += 0.5
        reasons.append("Precio sobre EMA20")

    # 6. MACD
    if last["macd_hist"] > 0 and prev["macd_hist"] <= 0:
        score += 1.0
        reasons.append("Cruce MACD alcista")
    elif last["macd_hist"] > 0 and last["macd"] > 0:
        score += 0.5
        reasons.append("MACD positivo")

    # 7. Volumen
    if last["vol_ratio"] > 1.5:
        score += 0.5
        reasons.append(f"Volumen elevado ({last['vol_ratio']:.1f}x)")

    # Aplicar ajuste de contexto macro
    score = round(score + score_adjustment, 2)
    if score_adjustment != 0.0:
        reasons.append(f"Ajuste macro: {score_adjustment:+.1f}")

    # ── Gestión de riesgo ─────────────────────────────────────────────────────
    atr  = max(float(last["atr"]), float(last["Close"]) * 0.01)
    stop = float(last["Close"]) - (atr * 2.0)
    tp   = float(last["Close"]) + (atr * 4.0)
    risk = float(last["Close"]) - stop
    rr   = (tp - float(last["Close"])) / max(risk, 1e-9)

    return StockSignal(
        symbol        = symbol,
        name          = name,
        price         = float(last["Close"]),
        score         = score,
        rr            = round(rr, 2),
        tp            = round(tp, 2),
        stop          = round(stop, 2),
        atr           = round(atr, 2),
        rsi           = round(float(last["rsi"]), 2),
        adx           = round(float(last["adx"]), 2),
        group         = group,
        earnings_date = earnings_date_str or "",
        reasons       = reasons,
        blocked       = blocked,
    )


# ── Formato de alerta ─────────────────────────────────────────────────────────
def format_alert(sig: StockSignal, vix: Optional[float]) -> str:
    score_emoji  = "🔥" if sig.score >= 7.0 else "📈"
    vix_line     = f"📉 *VIX:* {vix:.1f}\n" if vix is not None else ""
    earnings_line = (
        f"📅 *Próximos earnings:* {sig.earnings_date}\n"
        if sig.earnings_date else ""
    )

    return (
        f"{score_emoji} *ALERTA BOLSA: {sig.name} ({sig.symbol})*\n\n"
        f"💰 *Precio:* ${sig.price:.2f}\n"
        f"📊 *Score:* {sig.score:.1f}/8.5\n"
        f"⚖️ *R:R:* {sig.rr:.2f}x\n"
        f"📏 *ATR:* ${sig.atr:.2f} | *ADX:* {sig.adx:.1f} | *RSI:* {sig.rsi:.1f}\n"
        f"{vix_line}"
        f"{earnings_line}\n"
        f"🎯 *TARGET:* ${sig.tp:.2f}\n"
        f"🛑 *STOP:*   ${sig.stop:.2f}\n\n"
        f"📝 *Señales:*\n" +
        "\n".join(f"  • {r}" for r in sig.reasons)
    )


# ── Main ──────────────────────────────────────────────────────────────────────
def main():
    state   = load_state()
    context = load_market_context()
    now     = time.time()

    mode = "DRY RUN" if DRY_RUN else "PRODUCCIÓN"
    log.info(f"Iniciando escaneo [{mode}] — {len(STOCKS)} acciones")

    # VIX una sola vez para todo el escaneo
    vix = fetch_vix()
    if vix is not None:
        vix_status = "PÁNICO" if vix >= VIX_BLOCK_LEVEL else ("NERVIOSO" if vix >= VIX_CAUTION_LEVEL else "NORMAL")
        log.info(f"VIX={vix:.1f} — condición de mercado: {vix_status}")
    else:
        log.warning("VIX no disponible — se omite filtro macro global")

    stats = {k: 0 for k in ("scanned", "cooldown", "no_data", "blocked", "no_signal", "alerts")}

    for symbol in STOCKS:
        last_alert = state.get(symbol, 0)
        remaining  = COOLDOWN - (now - last_alert)
        if remaining > 0:
            log.info(f"COOLDOWN {symbol}: {remaining/3600:.1f}h restantes")
            stats["cooldown"] += 1
            continue

        stats["scanned"] += 1
        try:
            sym_context = get_symbol_context(context, symbol)
            sig = evaluate_stock(symbol, sym_context, vix)

            if sig is None:
                stats["no_data"] += 1
                log.warning(f"{symbol}: sin datos suficientes")
                continue

            status = (
                "⚠️ BLOQUEADO" if sig.blocked
                else ("✅ ALERTA" if sig.should_alert else "○ sin señal")
            )
            log.info(
                f"{sig.symbol}: score={sig.score:.1f} | R:R={sig.rr:.2f} | "
                f"RSI={sig.rsi:.1f} | ADX={sig.adx:.1f} | {status}"
            )

            if sig.blocked:
                stats["blocked"] += 1
                for b in sig.blocked:
                    log.info(f"  └ {b}")
            elif sig.should_alert:
                if send_telegram(format_alert(sig, vix)):
                    state[symbol] = now
                    save_state(state)
                    stats["alerts"] += 1
                    log.info(f"✅ Alerta enviada: {sig.name}")
            else:
                stats["no_signal"] += 1

            time.sleep(2.0)

        except Exception as e:
            log.error(f"{symbol}: excepción — {e}", exc_info=True)

    log.info(
        f"Escaneo completado | "
        f"Escaneados:{stats['scanned']} | Cooldown:{stats['cooldown']} | "
        f"Sin datos:{stats['no_data']} | Bloqueados:{stats['blocked']} | "
        f"Sin señal:{stats['no_signal']} | Alertas:{stats['alerts']}"
    )

    # Resumen siempre por Telegram
    if not DRY_RUN:
        vix_summary = f"📉 VIX: {vix:.1f}\n" if vix is not None else ""
        send_telegram(
            f"📋 *Resumen escaneo bolsa*\n\n"
            f"{vix_summary}"
            f"✅ Alertas enviadas: {stats['alerts']}\n"
            f"○ Sin señal: {stats['no_signal']}\n"
            f"⚠️ Bloqueadas: {stats['blocked']}\n"
            f"💤 En cooldown: {stats['cooldown']}\n"
            f"❌ Sin datos: {stats['no_data']}"
        )


if __name__ == "__main__":
    main()
