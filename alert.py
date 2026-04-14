import os
import time
import json
from pathlib import Path
import pandas as pd
import yfinance as yf
import requests

# ── Configuración de Mercado ──────────────────────────────────────────────────
# Las 20 acciones más líquidas del S&P 500 + ETFs principales
STOCKS = [
    'AAPL', 'MSFT', 'NVDA', 'AMZN', 'GOOGL', 'META', 'TSLA', 'BRK-B', 
    'V', 'JPM', 'UNH', 'MA', 'AVGO', 'HD', 'PG', 'COST', 'SPY', 'QQQ'
]

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
STATE_FILE = "stock_state.json"
MIN_SCORE = 5.0  # Solo señales de alta probabilidad
MIN_RR = 2.0

# ── Sistema de Alertas y Telegram ─────────────────────────────────────────────
def send_telegram(msg):
    if not TELEGRAM_BOT_TOKEN: return
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    requests.post(url, json={"chat_id": TELEGRAM_CHAT_ID, "text": msg, "parse_mode": "Markdown"})

def load_state():
    if not Path(STATE_FILE).exists(): return {}
    return json.loads(Path(STATE_FILE).read_text())

def mark_alerted(symbol):
    state = load_state()
    state[symbol] = time.time()
    Path(STATE_FILE).write_text(json.dumps(state))

# ── Análisis Técnico Institucional ───────────────────────────────────────────
def evaluate_stock(symbol):
    ticker = yf.Ticker(symbol)
    df = ticker.history(period="1y", interval="1d") # Datos diarios para más solidez
    
    if len(df) < 200: return None

    # Indicadores
    df['ema20'] = df['Close'].ewm(span=20).mean()
    df['ema200'] = df['Close'].ewm(span=200).mean()
    
    # RSI
    delta = df['Close'].diff()
    gain = (delta.where(delta > 0, 0)).ewm(alpha=1/14).mean()
    loss = (-delta.where(delta < 0, 0)).ewm(alpha=1/14).mean()
    df['rsi'] = 100 - (100 / (1 + (gain / (loss + 1e-9))))
    
    # ADX (Fuerza de tendencia)
    df['tr'] = df['Close'].diff().abs()
    df['atr'] = df['tr'].rolling(14).mean()
    p_dm = df['Close'].diff().clip(lower=0)
    m_dm = (-df['Close'].diff()).clip(lower=0)
    df['adx'] = ((p_dm - m_dm).abs() / (p_dm + m_dm + 1e-9)) * 100
    df['adx'] = df['adx'].rolling(14).mean()

    last = df.iloc[-1]
    prev = df.iloc[-2]
    score, reasons = 0, []

    # Lógica de Filtrado (Iteración de experto)
    if last['Close'] > last['ema200']: 
        score += 2.0; reasons.append("Tendencia Alcista (>EMA200)")
    if last['adx'] > 20: 
        score += 1.5; reasons.append(f"Fuerza de Tendencia (ADX: {last['adx']:.1f})")
    if 45 < last['rsi'] < 65 and last['rsi'] > prev['rsi']: 
        score += 1.0; reasons.append("Momento RSI Alcista")
    if last['Close'] > last['ema20'] and prev['Close'] <= prev['ema20']:
        score += 1.0; reasons.append("Cruce de Media Rápida (EMA20)")

    # Gestión de Riesgo (ATR dinámico)
    stop = last['Close'] - (last['atr'] * 2)
    tp = last['Close'] + (last['atr'] * 4.5)
    rr = (tp - last['Close']) / (last['Close'] - stop)

    return {
        "symbol": symbol, "score": score, "rr": rr, 
        "price": last['Close'], "stop": stop, "tp": tp, 
        "alert": score >= MIN_SCORE and rr >= MIN_RR, "reasons": reasons
    }

def main():
    state = load_state()
    for symbol in STOCKS:
        # Cooldown de 24h para acciones (movimientos más lentos)
        last_alert = state.get(symbol, 0)
        if (time.time() - last_alert) < 86400: continue
        
        try:
            res = evaluate_stock(symbol)
            if res and res["alert"]:
                msg = (f"📈 *ALERTA BOLSA (S&P500): {res['symbol']}*\n\n"
                       f"💰 *Precio:* ${res['price']:.2f}\n"
                       f"📊 *Score:* {res['score']}\n"
                       f"⚖️ *R:R:* {res['rr']:.2f}\n\n"
                       f"🎯 *TARGET:* ${res['tp']:.2f}\n"
                       f"🛑 *STOP:* ${res['stop']:.2f}\n\n"
                       f"📝 *Análisis:* {', '.join(res['reasons'])}")
                send_telegram(msg)
                mark_alerted(symbol)
                print(f"Alerta: {symbol}")
        except Exception as e: print(f"Error {symbol}: {e}")

if __name__ == "__main__":
    main()
