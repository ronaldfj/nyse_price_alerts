"""
inspector.py — Stock Sentinel Inspector (v2.10)
Evalúa cualquier acción con el motor idéntico a alert.py.
Sin modificaciones al bot. Sin envío a Telegram.

Uso:
    streamlit run inspector.py --server.port 8501
"""
from __future__ import annotations

import sys
from pathlib import Path

# alert.py está en el mismo directorio
sys.path.insert(0, str(Path(__file__).parent))

import streamlit as st

st.set_page_config(
    page_title="Stock Sentinel Inspector",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Importar del bot (sin modificar alert.py)
from alert import (
    MIN_RR,
    MIN_SCORE,
    STOCK_NAMES,
    STOCKS,
    compute_market_breadth,
    evaluate_stock,
    fetch_data,
    fetch_vix,
    get_symbol_context,
    load_market_context,
)

# ── Cache de datos costosos ───────────────────────────────────────────────────

@st.cache_data(ttl=300, show_spinner=False)
def _get_vix_and_breadth() -> tuple:
    return fetch_vix(), compute_market_breadth()


@st.cache_data(ttl=300, show_spinner=False)
def _get_spy_df():
    return fetch_data("SPY")


@st.cache_data(ttl=86400, show_spinner=False)
def _get_market_context():
    return load_market_context()


# ── Layout principal ─────────────────────────────────────────────────────────

st.title("Stock Sentinel Inspector")
st.caption(
    "Motor idéntico al bot de alertas (v2.10 breakout-only) · sin envío a Telegram · "
    f"Score mínimo: **{MIN_SCORE}** · RR mínimo: **{MIN_RR}**"
)

# ── Sidebar: contexto de mercado ─────────────────────────────────────────────

with st.sidebar:
    st.header("Mercado")

    if st.button("Refrescar datos", use_container_width=True):
        st.cache_data.clear()
        st.rerun()

    with st.spinner("Cargando VIX y Breadth..."):
        vix, breadth = _get_vix_and_breadth()

    # VIX
    if vix is not None:
        st.metric("VIX", f"{vix:.1f}")
        if vix >= 30:
            st.error("Pánico — bloqueo total")
        elif vix >= 22:
            st.warning("Elevado — penalty −0.50")
        else:
            st.success("Normal")
    else:
        st.metric("VIX", "N/D")
        st.warning("No disponible")

    st.divider()

    # Breadth
    if breadth is not None:
        st.metric("Breadth S&P 500", f"{breadth:.1f}%")
        if breadth < 40:
            st.error("Crítica — hard block")
        elif breadth < 50:
            st.warning("Limitada — penalty −0.30")
        else:
            st.success("Saludable")
    else:
        st.metric("Breadth S&P 500", "N/D")
        st.info("No disponible")

    st.divider()
    st.caption(
        "VIX y Breadth se actualizan cada 5 min.\n"
        "Datos de precio: caché de 5 min (yfinance)."
    )

# ── Selector de símbolo ──────────────────────────────────────────────────────

col_mode, col_sym, col_btn = st.columns([2, 4, 1])

with col_mode:
    mode = st.radio(
        "Fuente",
        ["Universo (42)", "Ticker libre"],
        horizontal=False,
        label_visibility="collapsed",
    )

with col_sym:
    if mode == "Universo (42)":
        symbol: str = st.selectbox(
            "Acción",
            options=STOCKS,
            format_func=lambda s: f"{s}  —  {STOCK_NAMES.get(s, s)}",
            label_visibility="collapsed",
        )
    else:
        raw = st.text_input(
            "Ticker",
            value="TSLA",
            placeholder="Ej: TSLA, COIN, UBER, PLTR",
            label_visibility="collapsed",
        )
        symbol = raw.strip().upper()

with col_btn:
    st.write("")  # spacer vertical
    evaluar = st.button("Evaluar →", type="primary", use_container_width=True)

# ── Evaluación ────────────────────────────────────────────────────────────────

if not evaluar:
    st.info("Seleccioná una acción y presioná **Evaluar →** para ver el análisis completo.")
    st.stop()

if not symbol:
    st.error("Ingresá un ticker válido.")
    st.stop()

with st.spinner(f"Evaluando {symbol}..."):
    try:
        ctx = _get_market_context()
        sym_ctx = get_symbol_context(ctx, symbol)
        spy_df = _get_spy_df()
        sig = evaluate_stock(symbol, sym_ctx, vix, spy_df, breadth)
    except Exception as exc:
        st.error(f"Error al evaluar **{symbol}**: {exc}")
        st.stop()

if sig is None:
    st.error(
        f"No hay suficientes datos históricos para **{symbol}** "
        "(se requieren al menos 220 barras diarias)."
    )
    st.stop()

st.divider()

# ── Banner de estado ──────────────────────────────────────────────────────────

if sig.blocked:
    st.error(f"BLOQUEADA — {sig.blocked[0]}")
elif sig.should_alert:
    st.success(f"ALERTA  ·  {sig.name}  ·  Breakout Expansion")
else:
    st.warning(
        f"SIN SEÑAL  ·  {sig.name}  ·  "
        f"score {sig.score:.2f} (mín {MIN_SCORE}) · RR {sig.rr:.2f} (mín {MIN_RR})"
    )

# ── Métricas resumen ──────────────────────────────────────────────────────────

m1, m2, m3, m4, m5 = st.columns(5)

m1.metric("Precio", f"${sig.price:.2f}")
m2.metric(
    "Score Total",
    f"{sig.score:.2f}",
    delta=f"{sig.score - MIN_SCORE:+.2f} vs {MIN_SCORE}",
    delta_color="normal",
)
m3.metric(
    "Risk/Reward",
    f"{sig.rr:.2f}×",
    delta=f"{sig.rr - MIN_RR:+.2f} vs {MIN_RR}",
    delta_color="normal",
)
m4.metric("Confluencia", f"{sig.confluence_count}/5")
m5.metric("RS vs SPY", f"{sig.rs20:+.2f}%")

# ── Desglose tri-capa ─────────────────────────────────────────────────────────

st.subheader("Desglose Tri-Capa")

r_col, s_col, t_col = st.columns(3)

# Rangos referenciales para normalizar la barra de progreso
_REGIME_MAX = 5.0
_SETUP_MAX  = 3.5   # puede ser negativo; usamos offset
_SETUP_MIN  = -2.5
_TRIGGER_MAX = 5.0


def _bar(value: float, vmin: float, vmax: float) -> float:
    """Normaliza value a [0, 1] dado un rango [vmin, vmax]."""
    if vmax <= vmin:
        return 0.0
    return max(0.0, min(1.0, (value - vmin) / (vmax - vmin)))


with r_col:
    st.markdown("#### Regime Score")
    st.caption("Tendencia estructural")
    st.progress(_bar(sig.regime_score, 0, _REGIME_MAX))
    st.metric("", f"{sig.regime_score:.2f}", help="EMA200, EMA50, Supertrend, ADX/DI")

with s_col:
    st.markdown("#### Setup Score")
    st.caption("Calidad de entrada")
    st.progress(_bar(sig.setup_score, _SETUP_MIN, _SETUP_MAX))
    st.metric("", f"{sig.setup_score:.2f}", help="RSI, EMA20/50, RS vs SPY, extensión")

with t_col:
    st.markdown("#### Trigger Score")
    st.caption("Catalizador de activación")
    st.progress(_bar(sig.trigger_score, 0, _TRIGGER_MAX))
    st.metric("", f"{sig.trigger_score:.2f}", help="Prior high, MACD, volumen, Supertrend flip")

# ── Indicadores clave ─────────────────────────────────────────────────────────

st.subheader("Indicadores Clave")

i1, i2, i3, i4, i5, i6 = st.columns(6)
i1.metric("RSI (14)", f"{sig.rsi:.1f}")
i2.metric("ADX (14)", f"{sig.adx:.1f}")
i3.metric("ATR (14)", f"${sig.atr:.2f}")
i4.metric("Extensión EMA200", f"{sig.extension_pct:.1f}%")
i5.metric(
    "Supertrend",
    "Alcista" if sig.supertrend_bull else "Bajista",
    delta=f"val={sig.supertrend_val:.2f}",
    delta_color="off",
)
i6.metric("Grupo / Sector", sig.group if sig.group != "Other" else "—")

# ── Setup de trade ────────────────────────────────────────────────────────────

st.subheader("Setup de Trade")

t1, t2, t3, t4 = st.columns(4)
t1.metric("Entry (último cierre)", f"${sig.price:.2f}")
t2.metric("Stop Loss", f"${sig.stop:.2f}", delta=f"−${sig.price - sig.stop:.2f}", delta_color="inverse")
t3.metric("Target (TP)", f"${sig.tp:.2f}", delta=f"+${sig.tp - sig.price:.2f}")
t4.metric("Trailing Stop inicial", f"${sig.trailing_stop_initial:.2f}")

p1, p2, p3 = st.columns(3)
p1.metric("Posición (acciones)", f"{sig.position_size_shares:,}")
p2.metric("Posición (USD)", f"${sig.position_size_usd:,.0f}")
p3.metric("Riesgo USD", f"${sig.risk_usd:.2f}")

if sig.earnings_date:
    st.info(f"Earnings: {sig.earnings_date}")

# ── Señales, advertencias y bloqueos ─────────────────────────────────────────

st.subheader("Señales Detectadas")

col_r, col_w, col_b = st.columns(3)

with col_r:
    st.markdown(f"**Razones** ({len(sig.reasons)})")
    if sig.reasons:
        for r in sig.reasons:
            st.success(r, icon="✅")
    else:
        st.info("Ninguna")

with col_w:
    st.markdown(f"**Advertencias** ({len(sig.warnings)})")
    if sig.warnings:
        for w in sig.warnings:
            st.warning(w, icon="⚠️")
    else:
        st.success("Ninguna")

with col_b:
    st.markdown(f"**Bloqueos** ({len(sig.blocked)})")
    if sig.blocked:
        for b in sig.blocked:
            st.error(b, icon="🚫")
    else:
        st.success("Sin bloqueos")

# ── Footer ────────────────────────────────────────────────────────────────────

st.divider()
st.caption(
    f"Última vela evaluada: `{sig.trigger_candle_utc}` · "
    f"Rank score: `{sig.rank_score:.2f}` · "
    f"Signal type: `{sig.signal_type}`"
)
