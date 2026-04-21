"""
Stock Sentinel Bot — Alertas técnicas para NYSE/Nasdaq
Iteración 1.4 aplicada:
  - Score por capas: regime / setup / trigger
  - Hard blocks solo para riesgo real
  - Warnings / penalizaciones para setup subóptimo
  - Dos playbooks: pullback continuation / breakout expansion
  - R:R estructural usando swing low + rango reciente
  - Pendiente de EMA200 para evitar tendencias planas
  - Relative strength simple vs SPY (20 sesiones)
  - Soporte a market_context_stocks.json por defecto
  - Uso real de caution_level desde market_context
  - Logging más claro para debugging y tuning
  - Earnings omitidos para ETFs (SPY/QQQ)
  - Gestión de riesgo diferenciada por playbook
  - Breakout más permisivo para tendencias fuertes
  - DRY_RUN para pruebas sin Telegram
  - Persistencia opcional de alertas a CSV histórico
  - Tracker automático de outcomes: open / hit_target / hit_stop / expired
"""

from __future__ import annotations

import json
import csv
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
ALERTS_HISTORY_FILE = os.getenv("ALERTS_HISTORY_FILE", "alerts_history.csv")
DRY_RUN = os.getenv("DRY_RUN", "false").lower() == "true"

MIN_SCORE = float(os.getenv("MIN_SCORE", "5.8"))
MIN_RR = float(os.getenv("MIN_RR", "1.6"))
COOLDOWN = int(os.getenv("COOLDOWN_HOURS", "48")) * 3600
EARNINGS_BUFFER_DAYS = int(os.getenv("EARNINGS_BUFFER_DAYS", "5"))
VIX_BLOCK_LEVEL = float(os.getenv("VIX_BLOCK_LEVEL", "30.0"))
VIX_CAUTION_LEVEL = float(os.getenv("VIX_CAUTION_LEVEL", "22.0"))
TRIGGER_VOL_RATIO = float(os.getenv("TRIGGER_VOL_RATIO", "1.00"))
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
ALERT_ETFS = os.getenv("ALERT_ETFS", "false").lower() == "true"
REQUIRE_PLAYBOOK = os.getenv("REQUIRE_PLAYBOOK", "true").lower() == "true"
TRACKER_MAX_BARS_OPEN = int(os.getenv("TRACKER_MAX_BARS_OPEN", "15"))
TRACKER_ENABLED = os.getenv("TRACKER_ENABLED", "true").lower() == "true"

DEFAULT_CONTEXT_CANDIDATES = (
    os.getenv("MARKET_CONTEXT_FILE", ""),
    "market_context_stocks.json",
    "market_context.json",
)

ALERT_HISTORY_COLUMNS = [
    "timestamp_utc",
    "symbol",
    "name",
    "group",
    "playbook",
    "price",
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
    reasons: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    blocked: list[str] = field(default_factory=list)

    @property
    def should_alert(self) -> bool:
        playbook_ok = self.signal_type in {"pullback", "breakout", "hybrid"} or not REQUIRE_PLAYBOOK
        benchmark_ok = ALERT_ETFS or self.group != "ETF"
        rs_ok = self.group == "ETF" or self.rs20 >= FINAL_RS_MIN
        return (
            self.score >= MIN_SCORE
            and self.rr >= MIN_RR
            and not self.blocked
            and playbook_ok
            and benchmark_ok
            and rs_ok
        )


# ── Telegram ──────────────────────────────────────────────────────────────────
def send_telegram(msg: str) -> bool:
    if DRY_RUN:
        log.info("[DRY RUN] Mensaje:\n%s", msg)
        return True

    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        log.warning("Telegram no configurado")
        return False

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    try:
        response = requests.post(
            url,
            json={"chat_id": TELEGRAM_CHAT_ID, "text": msg, "parse_mode": "Markdown"},
            timeout=15,
        )
        if response.status_code != 200:
            log.warning("Telegram %s: %s", response.status_code, response.text[:120])
            return False
        return True
    except Exception as exc:
        log.error("Telegram: %s", exc)
        return False


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


def ensure_alert_history_schema() -> None:
    path = Path(ALERTS_HISTORY_FILE)
    path.parent.mkdir(parents=True, exist_ok=True)

    if not path.exists() or path.stat().st_size == 0:
        return

    with path.open("r", newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        current_columns = reader.fieldnames or []
        rows = list(reader)

    if current_columns == ALERT_HISTORY_COLUMNS:
        return

    normalized_rows = [{col: row.get(col, "") for col in ALERT_HISTORY_COLUMNS} for row in rows]
    save_alert_history_rows(normalized_rows)
    log.info("Histórico CSV migrado a esquema tracker: %s", ALERTS_HISTORY_FILE)


def append_alert_history(sig: StockSignal, vix: Optional[float]) -> None:
    history_path = Path(ALERTS_HISTORY_FILE)
    history_path.parent.mkdir(parents=True, exist_ok=True)

    now_utc = datetime.now(timezone.utc).isoformat()
    row = {
        "timestamp_utc": now_utc,
        "symbol": sig.symbol,
        "name": sig.name,
        "group": sig.group,
        "playbook": sig.signal_type,
        "price": _fmt_csv_number(sig.price),
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

    file_exists = history_path.exists() and history_path.stat().st_size > 0
    with history_path.open("a", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=ALERT_HISTORY_COLUMNS)
        if not file_exists:
            writer.writeheader()
        writer.writerow(row)


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

        highs = trade_df["High"].astype(float)
        lows = trade_df["Low"].astype(float)
        closes = trade_df["Close"].astype(float)

        bars_open = int(len(trade_df))
        days_open = int((trade_df.index[-1].date() - opened_dt.date()).days)
        current_price = float(closes.iloc[-1])
        mfe_pct = ((float(highs.max()) - entry) / max(entry, 1e-9)) * 100.0
        mae_pct = ((float(lows.min()) - entry) / max(entry, 1e-9)) * 100.0

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
            row["pnl_pct"] = _fmt_csv_number(((current_price - entry) / max(entry, 1e-9)) * 100.0)
            row["exit_date"] = ""
            row["exit_price"] = ""
            row["exit_reason"] = ""
            row["closed_utc"] = ""
            stats["still_open"] += 1
        else:
            realized_pnl_pct = ((float(exit_price) - entry) / max(entry, 1e-9)) * 100.0
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
    try:
        df = yf.Ticker("^VIX").history(period="5d", interval="1d", auto_adjust=True)
        if df is not None and not df.empty:
            return round(float(df["Close"].iloc[-1]), 2)
    except Exception as exc:
        log.warning("VIX no disponible: %s", exc)
    return None


def get_earnings_info(symbol: str) -> tuple[Optional[str], bool]:
    if STOCK_GROUPS.get(symbol) == "ETF":
        return None, False

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
    df["prior_high_20"] = df["High"].shift(1).rolling(20).max()
    df["prior_low_5"] = df["Low"].shift(1).rolling(5).min()
    df["prior_low_12"] = df["Low"].shift(1).rolling(SWING_LOOKBACK).min()
    df["prior_low_20"] = df["Low"].shift(1).rolling(20).min()

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


# ── Helpers cuantitativos ─────────────────────────────────────────────────────
def compute_relative_strength(df: pd.DataFrame, spy_df: Optional[pd.DataFrame]) -> float:
    if spy_df is None or len(df) < RS_LOOKBACK + 2 or len(spy_df) < RS_LOOKBACK + 2:
        return 0.0

    asset_ret = (float(df["Close"].iloc[-2]) / float(df["Close"].iloc[-2 - RS_LOOKBACK]) - 1.0) * 100
    spy_ret = (float(spy_df["Close"].iloc[-2]) / float(spy_df["Close"].iloc[-2 - RS_LOOKBACK]) - 1.0) * 100
    return round(asset_ret - spy_ret, 2)


# ── Evaluación ────────────────────────────────────────────────────────────────
def evaluate_stock(symbol: str, sym_context: dict, vix: Optional[float], spy_df: Optional[pd.DataFrame]) -> Optional[StockSignal]:
    df = fetch_data(symbol)
    if df is None:
        return None

    earnings_date_str, earnings_near = get_earnings_info(symbol)
    df = add_indicators(df)

    if len(df) < max(220, RS_LOOKBACK + 25):
        return None

    last = df.iloc[-2]  # última vela cerrada
    prev = df.iloc[-3]

    name = STOCK_NAMES.get(symbol, symbol)
    group = STOCK_GROUPS.get(symbol, "Other")
    reasons: list[str] = []
    warnings: list[str] = []
    blocked: list[str] = []

    regime_score = 0.0
    setup_score = 0.0
    trigger_score = 0.0
    signal_type = "none"

    entry = float(last["Close"])
    atr = max(float(last["atr"]), entry * 0.008)
    rsi = float(last["rsi"])
    prev_rsi = float(prev["rsi"])
    adx = float(last["adx"])
    plus_di = float(last["plus_di"])
    minus_di = float(last["minus_di"])
    vol_ratio = float(last["vol_ratio"])
    ema20 = float(last["ema20"])
    ema50 = float(last["ema50"])
    ema200 = float(last["ema200"])
    extension_pct = ((entry - ema200) / max(ema200, 1e-9)) * 100
    pullback_atr = abs(entry - ema20) / max(atr, 1e-9)
    rs20 = 0.0 if symbol == "SPY" else compute_relative_strength(df, spy_df)

    prior_high_5 = float(last["prior_high_5"]) if pd.notna(last["prior_high_5"]) else entry
    prior_high_20 = float(last["prior_high_20"]) if pd.notna(last["prior_high_20"]) else entry + 2.0 * atr
    prior_low_5 = float(last["prior_low_5"]) if pd.notna(last["prior_low_5"]) else entry - 1.2 * atr
    prior_swing_low = float(last["prior_low_12"]) if pd.notna(last["prior_low_12"]) else entry - 1.8 * atr
    prior_low_20 = float(last["prior_low_20"]) if pd.notna(last["prior_low_20"]) else prior_swing_low

    # ── Bloqueos duros ────────────────────────────────────────────────────────
    if earnings_near and earnings_date_str:
        blocked.append(f"Earnings en {earnings_date_str} (±{EARNINGS_BUFFER_DAYS} días)")

    if vix is not None and vix >= VIX_BLOCK_LEVEL:
        blocked.append(f"VIX={vix:.1f} — mercado en pánico")

    if sym_context.get("hard_block_long"):
        blocked.append(f"Bloqueo manual: {sym_context.get('note', 'sin nota')}")

    if extension_pct > 30:
        blocked.append(f"Precio sobreextendido: {extension_pct:.1f}% sobre EMA200")
    elif extension_pct > 24:
        setup_score -= 0.6
        warnings.append(f"Extensión alta: {extension_pct:.1f}% sobre EMA200")

    if rsi > 80:
        blocked.append(f"RSI extremo ({rsi:.1f})")
    elif rsi > BREAKOUT_RSI_MAX:
        setup_score -= 0.5
        warnings.append(f"RSI caliente ({rsi:.1f})")

    if adx < WEAK_ADX_BLOCK and plus_di <= minus_di:
        blocked.append(
            f"Sin direccionalidad real (ADX={adx:.1f}, DI+={plus_di:.1f}, DI-={minus_di:.1f})"
        )

    # ── Regime ────────────────────────────────────────────────────────────────
    if entry > ema200:
        regime_score += 1.0
        reasons.append("Precio > EMA200")

    if ema50 > ema200:
        regime_score += 0.75
        reasons.append("EMA50 > EMA200")

    if float(last["ema200_slope_5"]) > 0:
        regime_score += 0.75
        reasons.append("EMA200 con pendiente positiva")

    if plus_di > minus_di and adx >= 18:
        regime_score += 1.0
        reasons.append(f"Direccionalidad válida (ADX {adx:.1f})")
    elif plus_di > minus_di and adx >= WEAK_ADX_BLOCK:
        regime_score += 0.4
        warnings.append(f"Direccionalidad todavía débil (ADX {adx:.1f})")
    elif adx >= 18:
        regime_score -= 0.4
        warnings.append(f"DI sin liderazgo claro (DI+ {plus_di:.1f} vs DI- {minus_di:.1f})")

    # ── Setup base ────────────────────────────────────────────────────────────
    if 0.15 <= pullback_atr <= PULLBACK_MAX_ATR:
        setup_score += 0.8
        reasons.append(f"Distancia operable a EMA20 ({pullback_atr:.2f} ATR)")
    elif pullback_atr < 0.15:
        setup_score += 0.2
        reasons.append("Precio muy cerca de EMA20")
    elif pullback_atr <= BREAKOUT_MAX_ATR:
        setup_score -= 0.15
        warnings.append(f"Lejos de EMA20 para pullback ({pullback_atr:.2f} ATR)")
    else:
        setup_score -= 0.45
        warnings.append(f"Muy extendido vs EMA20 ({pullback_atr:.2f} ATR)")

    if SETUP_RSI_MIN <= rsi <= SETUP_RSI_MAX and rsi >= prev_rsi:
        setup_score += 1.0
        reasons.append(f"RSI en zona ideal ({rsi:.1f})")
    elif SETUP_RSI_MAX < rsi <= BREAKOUT_RSI_MAX and adx >= 20:
        setup_score += 0.45
        reasons.append(f"RSI fuerte de tendencia ({rsi:.1f})")
    elif 40 <= rsi < SETUP_RSI_MIN and rsi > prev_rsi:
        setup_score += 0.35
        reasons.append(f"RSI recuperando ({rsi:.1f})")
    else:
        setup_score -= 0.5
        warnings.append(f"RSI fuera de zona ideal ({rsi:.1f})")

    if ema20 > ema50 and float(last["ema20_slope_3"]) > 0:
        setup_score += 0.8
        reasons.append("EMA20 > EMA50 con pendiente positiva")
    elif entry > ema50:
        setup_score += 0.4
        reasons.append("Precio sostiene EMA50")
    else:
        setup_score -= 0.2
        warnings.append("Precio por debajo de EMA50")

    if symbol != "SPY":
        if rs20 > 1.0:
            setup_score += 0.9
            reasons.append(f"RS positiva vs SPY: {rs20:+.2f}%")
        elif rs20 > 0:
            setup_score += 0.4
            reasons.append(f"RS levemente positiva vs SPY: {rs20:+.2f}%")
        elif rs20 > -1.0:
            setup_score -= 0.2
            warnings.append(f"RS plana vs SPY: {rs20:+.2f}%")
        else:
            setup_score -= 0.7
            warnings.append(f"RS negativa vs SPY: {rs20:+.2f}%")

    # ── Trigger base ──────────────────────────────────────────────────────────
    broke_prior_high_5 = entry > prior_high_5
    broke_prior_high_20 = entry > prior_high_20
    near_breakout = entry >= prior_high_20 * BREAKOUT_NEAR_PCT
    bullish_reclaim = entry > ema20 and float(prev["Close"]) <= float(prev["ema20"])
    positive_momentum = float(last["macd_hist"]) > float(prev["macd_hist"])

    if broke_prior_high_5:
        trigger_score += 0.8
        reasons.append("Ruptura de máximo reciente")
    elif bullish_reclaim:
        trigger_score += 0.5
        reasons.append("Reclaim sobre EMA20")
    elif near_breakout:
        trigger_score += 0.35
        reasons.append("Cerca de ruptura del máximo de 20 sesiones")

    if positive_momentum and float(last["macd_hist"]) > 0:
        trigger_score += 0.8
        reasons.append("MACD histograma acelerando > 0")
    elif positive_momentum:
        trigger_score += 0.4
        reasons.append("MACD mejorando")

    if vol_ratio >= TRIGGER_VOL_RATIO:
        trigger_score += 0.8
        reasons.append(f"Volumen de confirmación ({vol_ratio:.2f}x)")
    elif vol_ratio >= 0.95:
        trigger_score += 0.15
        reasons.append(f"Volumen aceptable ({vol_ratio:.2f}x)")
    else:
        trigger_score -= 0.4
        warnings.append(f"Volumen flojo ({vol_ratio:.2f}x)")

    # ── Playbooks ─────────────────────────────────────────────────────────────
    pullback_trend_strong = entry > ema200 and ema50 > ema200 and ema20 > ema50 and adx >= 18
    breakout_structure = (
        broke_prior_high_20
        or near_breakout
        or (
            broke_prior_high_5
            and positive_momentum
            and trigger_score >= 1.6
            and entry >= prior_high_20 * 0.985
        )
    )

    is_pullback = (
        pullback_trend_strong
        and 0.15 <= pullback_atr <= PULLBACK_MAX_ATR
        and SETUP_RSI_MIN <= rsi <= max(SETUP_RSI_MAX, 68)
    )

    is_breakout = (
        breakout_structure
        and vol_ratio >= 0.95
        and rs20 >= BREAKOUT_RS_MIN
        and adx >= 18
        and rsi <= BREAKOUT_RSI_MAX
        and pullback_atr <= BREAKOUT_MAX_ATR
        and entry > ema50
    )

    # Playbook híbrido: expansión temprana sobre tendencia, aunque no esté aún en 20D high limpio.
    is_hybrid = (
        not is_breakout
        and not is_pullback
        and entry > ema200
        and ema50 > ema200
        and entry > ema50
        and broke_prior_high_5
        and positive_momentum
        and trigger_score >= 1.8
        and adx >= 18
        and rsi <= BREAKOUT_RSI_MAX
        and pullback_atr <= BREAKOUT_MAX_ATR
        and rs20 >= max(BREAKOUT_RS_MIN, -0.25)
    )

    if is_pullback:
        signal_type = "pullback"
        setup_score += 1.0
        reasons.append("Playbook activo: Pullback Continuation")

    if is_breakout:
        signal_type = "breakout" if signal_type == "none" else "hybrid"
        trigger_score += 1.2
        reasons.append("Playbook activo: Breakout Expansion")
    elif is_hybrid:
        signal_type = "hybrid"
        trigger_score += 0.9
        reasons.append("Playbook activo: Early Expansion / Hybrid")

    if signal_type == "none":
        setup_score -= 0.7
        warnings.append("No encaja limpio en pullback ni breakout")

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

    # ── Gestión de riesgo por playbook ────────────────────────────────────────
    range_20 = max(prior_high_20 - prior_low_20, 1.2 * atr)
    dist_to_high20 = max(prior_high_20 - entry, 0.0)
    measured_move = max(0.75 * range_20, 1.6 * atr)

    if signal_type == "breakout":
        raw_stop = max(prior_high_5 - 0.30 * atr, ema20 - 0.35 * atr, entry - 0.95 * atr)
        stop = min(raw_stop, entry - 0.12 * atr)
        risk = entry - stop
        tp = max(
            prior_high_20 + 0.20 * atr,
            entry + measured_move,
            entry + 1.25 * risk,
        )

    elif signal_type == "hybrid":
        raw_stop = max(prior_low_5 - 0.20 * atr, ema20 - 0.45 * atr, entry - 1.05 * atr)
        stop = min(raw_stop, entry - 0.15 * atr)
        risk = entry - stop
        tp = max(
            prior_high_20 + 0.15 * atr,
            entry + max(0.60 * range_20, 1.5 * atr),
            entry + 1.20 * risk,
        )

    elif signal_type == "pullback":
        raw_stop = min(prior_swing_low - 0.12 * atr, ema50 - 0.12 * atr, entry - 0.80 * atr)
        stop = min(raw_stop, entry - 0.15 * atr)
        risk = entry - stop
        tp = max(
            prior_high_20 + 0.10 * atr,
            entry + max(0.55 * range_20, 1.3 * atr),
            entry + 1.15 * risk,
        )

    else:
        raw_stop = min(prior_swing_low - 0.10 * atr, ema50 - 0.15 * atr, entry - 0.90 * atr)
        stop = min(raw_stop, entry - 0.15 * atr)
        risk = entry - stop
        tp = max(entry + 1.00 * atr, prior_high_20)

    min_risk = max(0.22 * atr, entry * 0.002)
    if risk < min_risk:
        stop = entry - min_risk
        risk = min_risk

    if stop >= entry:
        blocked.append("Riesgo inválido: stop no consistente")
        stop = entry - max(0.90 * atr, entry * 0.003)
        risk = entry - stop

    if tp <= entry:
        blocked.append("Target inválido: TP no consistente")
        tp = entry + max(1.20 * atr, 0.60 * range_20)

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
        adx=round(adx, 2),
        group=group,
        earnings_date=earnings_date_str or "",
        regime_score=round(regime_score, 2),
        setup_score=round(setup_score, 2),
        trigger_score=round(trigger_score, 2),
        extension_pct=round(extension_pct, 2),
        rs20=round(rs20, 2),
        signal_type=signal_type,
        reasons=reasons,
        warnings=warnings,
        blocked=blocked,
    )


# ── Formato de alerta ─────────────────────────────────────────────────────────
def format_alert(sig: StockSignal, vix: Optional[float]) -> str:
    score_emoji = "🔥" if sig.score >= 7.0 else "📈"
    vix_line = f"📉 *VIX:* {vix:.1f}\n" if vix is not None else ""
    earnings_line = f"📅 *Próximos earnings:* {sig.earnings_date}\n" if sig.earnings_date else ""
    rs_line = f"⚔️ *RS vs SPY (20d):* {sig.rs20:+.2f}%\n" if sig.symbol != "SPY" else ""
    signal_type_line = f"🧠 *Playbook:* {sig.signal_type}\n" if sig.signal_type != "none" else ""

    signal_breakdown = (
        f"🧩 *Regime/Setup/Trigger:* "
        f"{sig.regime_score:.1f}/{sig.setup_score:.1f}/{sig.trigger_score:.1f}\n"
    )

    warnings_block = ""
    if sig.warnings:
        warnings_block = "\n⚠️ *Warnings:*\n" + "\n".join(f"  • {warn}" for warn in sig.warnings[:4])

    return (
        f"{score_emoji} *ALERTA BOLSA v2.3: {sig.name} ({sig.symbol})*\n\n"
        f"💰 *Precio:* ${sig.price:.2f}\n"
        f"📊 *Score:* {sig.score:.1f}\n"
        f"⚖️ *R:R estructural:* {sig.rr:.2f}x\n"
        f"📏 *ATR:* ${sig.atr:.2f} | *ADX:* {sig.adx:.1f} | *RSI:* {sig.rsi:.1f}\n"
        f"{signal_breakdown}"
        f"{signal_type_line}"
        f"{rs_line}"
        f"{vix_line}"
        f"{earnings_line}\n"
        f"🎯 *TARGET:* ${sig.tp:.2f}\n"
        f"🛑 *STOP:* ${sig.stop:.2f}\n\n"
        f"📝 *Confluencias:*\n" + "\n".join(f"  • {reason}" for reason in sig.reasons[:8]) +
        warnings_block
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

    mode = "DRY RUN" if DRY_RUN else "PRODUCCIÓN"
    log.info("Iniciando escaneo v2 [%s] — %s acciones", mode, len(STOCKS))
    log.info("Histórico CSV: %s", ALERTS_HISTORY_FILE)

    tracker_stats = update_alert_history_tracker()
    if tracker_stats["open_checked"] > 0:
        log.info(
            "Tracker histórico | Revisadas:%s | Target:%s | Stop:%s | Expiradas:%s | Abiertas:%s | Inválidas:%s",
            tracker_stats["open_checked"],
            tracker_stats["hit_target"],
            tracker_stats["hit_stop"],
            tracker_stats["expired"],
            tracker_stats["still_open"],
            tracker_stats["invalid"],
        )

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
                    append_alert_history(sig, vix)
                    state[sig.symbol] = now
                    save_state(state)
                    stats["alerts"] += 1
                    log.info(
                        "✅ ALERTA %s | score=%.1f | RR=%.2f | playbook=%s | RS20=%+.2f%%",
                        sig.symbol,
                        sig.score,
                        sig.rr,
                        sig.signal_type,
                        sig.rs20,
                    )
            else:
                stats["no_signal"] += 1
                log.info(
                    "%s: score=%.1f | RR=%.2f | regime/setup/trigger=%.1f/%.1f/%.1f | sin señal | %s",
                    sig.symbol,
                    sig.score,
                    sig.rr,
                    sig.regime_score,
                    sig.setup_score,
                    sig.trigger_score,
                    format_reject_log(sig),
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
