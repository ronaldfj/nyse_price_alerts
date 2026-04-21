"""
Stock Sentinel Bot — Alertas técnicas para NYSE/Nasdaq
Versión mejorada con:
  - ATR real (True Range con High/Low)
  - ADX real con DI+/DI-
  - RSI Wilder correcto
  - Sistema de score graduado (no binario)
  - Filtro de volumen relativo
  - MACD como señal adicional
  - EMA50 como nivel intermedio
  - Logging estructurado
  - Gestión de estado en memoria (sin lecturas redundantes)
  - DRY_RUN para pruebas sin Telegram
"""

import logging
import os
import time
import json
from dataclasses import dataclass, field
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

# Grupos para diversificación en el resumen
STOCK_GROUPS = {
    "AAPL": "Tech", "MSFT": "Tech", "NVDA": "Tech",
    "AMZN": "Tech", "GOOGL": "Tech", "META": "Tech",
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
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID   = os.getenv("TELEGRAM_CHAT_ID", "")
STATE_FILE         = os.getenv("STOCK_STATE_FILE", "stock_state.json")
DRY_RUN            = os.getenv("DRY_RUN", "false").lower() == "true"

MIN_SCORE  = float(os.getenv("MIN_SCORE", "4.5"))   # sobre ~8.5 máximo posible
MIN_RR     = float(os.getenv("MIN_RR", "1.8"))       # más realista que 2.0 para diario
COOLDOWN   = int(os.getenv("COOLDOWN_HOURS", "48")) * 3600  # 48h para diario


# ── Dataclass de señal ────────────────────────────────────────────────────────
@dataclass
class StockSignal:
    symbol:   str
    name:     str
    price:    float
    score:    float
    rr:       float
    tp:       float
    stop:     float
    atr:      float
    rsi:      float = 0.0
    group:    str = "Other"
    reasons:  list = field(default_factory=list)
    blocked:  list = field(default_factory=list)

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


# ── Indicadores técnicos ──────────────────────────────────────────────────────
def add_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """
    Aplica todos los indicadores con fórmulas correctas.
    Requiere columnas: High, Low, Close, Volume.
    """
    # EMAs
    df["ema20"]  = df["Close"].ewm(span=20,  adjust=False).mean()
    df["ema50"]  = df["Close"].ewm(span=50,  adjust=False).mean()
    df["ema200"] = df["Close"].ewm(span=200, adjust=False).mean()

    # RSI Wilder (com=13 equivale a alpha=1/14)
    delta = df["Close"].diff()
    gain  = delta.where(delta > 0, 0.0).ewm(com=13, adjust=False).mean()
    loss  = (-delta.where(delta < 0, 0.0)).ewm(com=13, adjust=False).mean()
    df["rsi"] = 100 - (100 / (1 + gain / (loss + 1e-9)))

    # True Range y ATR real (usa High y Low)
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
    ema12        = df["Close"].ewm(span=12, adjust=False).mean()
    ema26        = df["Close"].ewm(span=26, adjust=False).mean()
    df["macd"]      = ema12 - ema26
    df["macd_sig"]  = df["macd"].ewm(span=9, adjust=False).mean()
    df["macd_hist"] = df["macd"] - df["macd_sig"]

    # Volumen relativo
    df["vol_ratio"] = df["Volume"] / (df["Volume"].rolling(20).mean() + 1e-9)

    return df


# ── Descarga y validación ─────────────────────────────────────────────────────
def fetch_data(symbol: str) -> Optional[pd.DataFrame]:
    """Descarga datos diarios y valida columnas y cantidad mínima."""
    try:
        df = yf.Ticker(symbol).history(period="2y", interval="1d")
    except Exception as e:
        log.warning(f"{symbol}: error en descarga — {e}")
        return None

    required = {"High", "Low", "Close", "Volume"}
    if df is None or df.empty or not required.issubset(df.columns):
        log.warning(f"{symbol}: datos inválidos o columnas faltantes")
        return None

    df = df.dropna(subset=list(required))

    # Necesitamos al menos 220 velas para EMA200 estable
    if len(df) < 220:
        log.warning(f"{symbol}: pocas velas ({len(df)} < 220)")
        return None

    return df


# ── Evaluación ────────────────────────────────────────────────────────────────
def evaluate_stock(symbol: str) -> Optional[StockSignal]:
    df = fetch_data(symbol)
    if df is None:
        return None

    df = add_indicators(df)

    # Última vela cerrada (no la vela en formación)
    last = df.iloc[-2]
    prev = df.iloc[-3]

    name  = STOCK_NAMES.get(symbol, symbol)
    group = STOCK_GROUPS.get(symbol, "Other")

    score, reasons, blocked = 0.0, [], []

    # ── Bloqueos duros ────────────────────────────────────────────────────────

    # RSI sobrecomprado extremo — alto riesgo de reversión
    if last["rsi"] > 78:
        blocked.append(f"RSI sobrecomprado ({last['rsi']:.1f}) — esperar corrección")

    # Precio muy extendido sobre EMA200 (>25%) — riesgo de mean reversion
    extension = (last["Close"] - last["ema200"]) / last["ema200"] * 100
    if extension > 25:
        blocked.append(f"Precio {extension:.1f}% sobre EMA200 — sobreextendido")

    # ── Señales de entrada ────────────────────────────────────────────────────

    # 1. Tendencia macro — EMA200 (peso alto)
    if last["Close"] > last["ema200"]:
        score += 2.0
        reasons.append("Tendencia alcista (>EMA200)")

    # 2. Estructura de EMAs — jerarquía alcista
    if last["ema20"] > last["ema50"] > last["ema200"]:
        score += 1.5
        reasons.append("EMA20 > EMA50 > EMA200 — estructura alcista")
    elif last["Close"] > last["ema50"] > last["ema200"]:
        score += 0.75
        reasons.append("Precio sobre EMA50 y EMA200")

    # 3. ADX con dirección correcta
    if last["adx"] > 25 and last["plus_di"] > last["minus_di"]:
        score += 1.5
        reasons.append(f"Tendencia fuerte ADX={last['adx']:.1f}, DI+>{last['minus_di']:.1f}")
    elif last["adx"] > 18 and last["plus_di"] > last["minus_di"]:
        score += 0.75
        reasons.append(f"Tendencia moderada ADX={last['adx']:.1f}")

    # 4. RSI con momentum (rango realista para acciones en diario)
    if 45 < last["rsi"] < 70 and last["rsi"] > prev["rsi"]:
        score += 1.0
        reasons.append(f"RSI momentum ({last['rsi']:.1f}↑)")
    elif 40 < last["rsi"] <= 45:
        score += 0.4
        reasons.append(f"RSI recuperando ({last['rsi']:.1f})")

    # 5. Cruce EMA20 alcista
    if last["Close"] > last["ema20"] and prev["Close"] <= prev["ema20"]:
        score += 1.0
        reasons.append("Cruce alcista EMA20")
    elif last["Close"] > last["ema20"]:
        score += 0.5
        reasons.append("Precio sobre EMA20")

    # 6. MACD cruce alcista
    if last["macd_hist"] > 0 and prev["macd_hist"] <= 0:
        score += 1.0
        reasons.append("Cruce MACD alcista")
    elif last["macd_hist"] > 0 and last["macd"] > 0:
        score += 0.5
        reasons.append("MACD positivo")

    # 7. Volumen confirmando (bonus)
    if last["vol_ratio"] > 1.5:
        score += 0.5
        reasons.append(f"Volumen elevado ({last['vol_ratio']:.1f}x promedio)")

    # ── Gestión de riesgo con ATR real ────────────────────────────────────────
    atr    = max(float(last["atr"]), float(last["Close"]) * 0.01)
    stop   = float(last["Close"]) - (atr * 2.0)
    tp     = float(last["Close"]) + (atr * 4.0)
    risk   = float(last["Close"]) - stop
    rr     = (tp - float(last["Close"])) / max(risk, 1e-9)

    return StockSignal(
        symbol  = symbol,
        name    = name,
        price   = float(last["Close"]),
        score   = round(score, 2),
        rr      = round(rr, 2),
        tp      = round(tp, 2),
        stop    = round(stop, 2),
        atr     = round(atr, 2),
        rsi     = round(float(last["rsi"]), 2),
        group   = group,
        reasons = reasons,
        blocked = blocked,
    )


# ── Formato de alerta ─────────────────────────────────────────────────────────
def format_alert(sig: StockSignal) -> str:
    score_emoji = "🔥" if sig.score >= 7.0 else "📈"
    blocked_note = ""
    if sig.blocked:
        blocked_note = f"\n⚠️ *Advertencias:* {', '.join(sig.blocked)}"

    return (
        f"{score_emoji} *ALERTA BOLSA: {sig.name} ({sig.symbol})*\n\n"
        f"💰 *Precio:* ${sig.price:.2f}\n"
        f"📊 *Score:* {sig.score:.1f}/8.5\n"
        f"⚖️ *R:R:* {sig.rr:.2f}x\n"
        f"📏 *ATR:* ${sig.atr:.2f}\n\n"
        f"🎯 *TARGET:* ${sig.tp:.2f}\n"
        f"🛑 *STOP:*   ${sig.stop:.2f}\n"
        f"{blocked_note}\n"
        f"📝 *Señales:*\n" +
        "\n".join(f"  • {r}" for r in sig.reasons)
    )


# ── Main ──────────────────────────────────────────────────────────────────────
def main():
    state = load_state()
    now   = time.time()

    mode = "DRY RUN" if DRY_RUN else "PRODUCCIÓN"
    log.info(f"Iniciando escaneo [{mode}] — {len(STOCKS)} acciones")

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
            sig = evaluate_stock(symbol)

            if sig is None:
                stats["no_data"] += 1
                log.warning(f"{symbol}: sin datos suficientes")
                continue

            # Log siempre el resultado
            status = "⚠️ BLOQUEADO" if sig.blocked else ("✅ ALERTA" if sig.should_alert else "○ sin señal")
            log.info(
                f"{sig.symbol}: score={sig.score:.1f} | R:R={sig.rr:.2f} | "
                f"RSI={sig.rsi:.1f} | ADX={sig.atr:.1f} | {status}"
            )

            if sig.blocked:
                stats["blocked"] += 1
                for b in sig.blocked:
                    log.info(f"  └ {b}")
            elif sig.should_alert:
                if send_telegram(format_alert(sig)):
                    state[symbol] = now
                    save_state(state)
                    stats["alerts"] += 1
                    log.info(f"✅ Alerta enviada: {sig.name}")
            else:
                stats["no_signal"] += 1

            time.sleep(2.0)  # Rate limit de Yahoo Finance

        except Exception as e:
            log.error(f"{symbol}: excepción — {e}", exc_info=True)

    # Resumen final
    log.info(
        f"Escaneo completado | "
        f"Escaneados:{stats['scanned']} | "
        f"Cooldown:{stats['cooldown']} | "
        f"Sin datos:{stats['no_data']} | "
        f"Bloqueados:{stats['blocked']} | "
        f"Sin señal:{stats['no_signal']} | "
        f"Alertas:{stats['alerts']}"
    )

    # Resumen por Telegram si hubo alertas
    if stats["alerts"] > 0 and not DRY_RUN:
        send_telegram(
            f"📋 *Resumen escaneo bolsa*\n\n"
            f"✅ Alertas enviadas: {stats['alerts']}\n"
            f"○ Sin señal: {stats['no_signal']}\n"
            f"⚠️ Bloqueadas: {stats['blocked']}\n"
            f"💤 En cooldown: {stats['cooldown']}"
        )


if __name__ == "__main__":
    main()
