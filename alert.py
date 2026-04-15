import os
import time
import json
from pathlib import Path
import pandas as pd
import yfinance as yf
import requests

# ── Configuración de Nombres (Blindaje contra bloqueos de info) ────────────────
STOCK_NAMES = {
    'AAPL': 'Apple Inc.', 'MSFT': 'Microsoft Corp.', 'NVDA': 'NVIDIA Corp.',
    'AMZN': 'Amazon.com Inc.', 'GOOGL': 'Alphabet Inc.', 'META': 'Meta Platforms',
    'TSLA': 'Tesla, Inc.', 'BRK-B': 'Berkshire Hathaway', 'V': 'Visa Inc.',
    'JPM': 'JPMorgan Chase', 'UNH': 'UnitedHealth Group', 'MA': 'Mastercard Inc.',
    'AVGO': 'Broadcom Inc.', 'HD': 'Home Depot Inc.', 'PG': 'Procter & Gamble',
    'COST': 'Costco Wholesale', 'SPY': 'S&P 500 ETF', 'QQQ': 'Nasdaq 100 ETF'
}

STOCKS = list(STOCK_NAMES.keys())

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
STATE_FILE = "stock_state.json"
MIN_SCORE = 5.0  
MIN_RR = 2.0

# ── Sistema de Alertas y Telegram ─────────────────────────────────────────────
def send_telegram(msg):
    if not TELEGRAM_BOT_TOKEN: return
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    try:
        requests.post(url, json={"chat_id": TELEGRAM_CHAT_ID, "text": msg, "parse_mode": "Markdown"}, timeout=15)
    except Exception as e: print(f"Error Telegram: {e}")

def load_state():
    try:
        if not Path(STATE_FILE).exists(): return {}
        return json.loads(Path(STATE_FILE).read_text())
    except: return {}

def mark_alerted(symbol):
    state = load_state()
    state[symbol] = time.time()
    Path(STATE_FILE).write_text(json.dumps(state))

# ── Análisis Técnico ──────────────────────────────────────────────────────────
def evaluate_stock(symbol):
    ticker = yf.Ticker(symbol)
    company_name = STOCK_NAMES.get(symbol, symbol)

    # Obtenemos historial directamente. YFinance manejará su propia sesión.
    try:
        df = ticker.history(period="1y", interval="1d")
    except Exception as e:
        print(f"❌ No se pudo conectar con {symbol}: {e}")
        return None
    
    if df is None or df.empty or len(df) < 200: 
        return None

    # Cálculo de Indicadores
    df['ema20'] = df['Close'].ewm(span=20, adjust=False).mean()
    df['ema200'] = df['Close'].ewm(span=200, adjust=False).mean()
    
    delta = df['Close'].diff()
    gain = (delta.where(delta > 0, 0)).ewm(alpha=1/14, adjust=False).mean()
    loss = (-delta.where(delta < 0, 0)).ewm(alpha=1/14, adjust=False).mean()
    df['rsi'] = 100 - (100 / (1 + (gain / (loss + 1e-9))))
    
    df['tr'] = df['Close'].diff().abs()
    df['atr'] = df['tr'].rolling(14).mean()
    p_dm = df['Close'].diff().clip(lower=0)
    m_dm = (-df['Close'].diff()).clip(lower=0)
    df['adx'] = ((p_dm - m_dm).abs() / (p_dm + m_dm + 1e-9)) * 100
    df['adx'] = df['adx'].rolling(14).mean()

    last = df.iloc[-1]
    prev = df.iloc[-2]
    score, reasons = 0, []

    if last['Close'] > last['ema200']: 
        score += 2.0; reasons.append("Tendencia Alcista (>EMA200)")
    if last['adx'] > 20: 
        score += 1.5; reasons.append(f"Fuerza de Tendencia (ADX: {last['adx']:.1f})")
    if 45 < last['rsi'] < 65 and last['rsi'] > prev['rsi']: 
        score += 1.0; reasons.append("Momento RSI Alcista")
    if last['Close'] > last['ema20'] and prev['Close'] <= prev['ema20']:
        score += 1.0; reasons.append("Cruce de Media Rápida (EMA20)")

    current_atr = last['atr'] if last['atr'] > 0 else (last['Close'] * 0.02)
    stop = last['Close'] - (current_atr * 2)
    tp = last['Close'] + (current_atr * 4.5)
    rr = (tp - last['Close']) / (last['Close'] - stop)

    return {
        "symbol": symbol, "name": company_name, "score": score, 
        "rr": rr, "price": last['Close'], "stop": stop, "tp": tp, 
        "alert": score >= MIN_SCORE and rr >= MIN_RR, "reasons": reasons
    }

def main():
    state = load_state()
    print("🚀 Iniciando escaneo de Bolsa...")
    for symbol in STOCKS:
        print(f"Procesando {ticker}... RSI: {rsi_actual}, ADX: {adx_actual}")
        last_alert = state.get(symbol, 0)
        if (time.time() - last_alert) < 86400: continue
        
        try:
            res = evaluate_stock(symbol)
            if res and res["alert"]:
                msg = (f"📈 *ALERTA BOLSA: {res['name']} ({res['symbol']})*\n\n"
                       f"💰 *Precio:* ${res['price']:.2f}\n"
                       f"📊 *Score:* {res['score']}\n"
                       f"⚖️ *R:R:* {res['rr']:.2f}\n\n"
                       f"🎯 *TARGET:* ${res['tp']:.2f}\n"
                       f"🛑 *STOP:* ${res['stop']:.2f}\n\n"
                       f"📝 *Análisis:* {', '.join(res['reasons'])}")
                send_telegram(msg)
                mark_alerted(symbol)
                print(f"✅ Alerta: {res['name']}")
            else:
                print(f"• {symbol}: Procesado.")
            
            # Pausa de seguridad
            time.sleep(3)
        except Exception as e:
            print(f"❌ Error en {symbol}: {e}")

if __name__ == "__main__":
    main()
