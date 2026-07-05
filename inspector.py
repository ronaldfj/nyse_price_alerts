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

sys.path.insert(0, str(Path(__file__).parent))

import streamlit as st

st.set_page_config(
    page_title="Stock Sentinel Inspector",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── CSS custom ────────────────────────────────────────────────────────────────

st.markdown("""
<style>
/* Cards generales */
.card {
    background: #f8f9fa;
    border-radius: 10px;
    padding: 1.2rem 1.4rem;
    margin-bottom: 0.8rem;
}
/* Borde izquierdo coloreado según estado */
.card-alert  { border-left: 5px solid #28a745; background: #f0fff4; }
.card-block  { border-left: 5px solid #dc3545; background: #fff5f5; }
.card-warn   { border-left: 5px solid #fd7e14; background: #fff8f0; }
.card-neutral{ border-left: 5px solid #6c757d; background: #f8f9fa; }

/* Score grande */
.score-big { font-size: 3rem; font-weight: 700; line-height: 1; margin: 0; }
.score-label { font-size: 0.85rem; color: #666; margin-top: 2px; }

/* Barra de score manual (reemplaza st.progress que se ve genérica) */
.bar-wrap  { background: #e9ecef; border-radius: 6px; height: 14px; overflow: hidden; margin: 4px 0 2px; }
.bar-fill  { height: 100%; border-radius: 6px; transition: width 0.3s; }
.bar-green  { background: linear-gradient(90deg, #28a745, #5cb85c); }
.bar-orange { background: linear-gradient(90deg, #fd7e14, #ffc107); }
.bar-red    { background: linear-gradient(90deg, #dc3545, #e06c75); }
.bar-blue   { background: linear-gradient(90deg, #0066cc, #4dabf7); }

/* Trade setup */
.trade-row { display: flex; justify-content: space-between; gap: 0.5rem; margin: 0.5rem 0; }
.trade-cell { flex: 1; background: #fff; border-radius: 8px; padding: 0.7rem; text-align: center; border: 1px solid #dee2e6; }
.trade-cell .val { font-size: 1.2rem; font-weight: 700; }
.trade-cell .lbl { font-size: 0.75rem; color: #888; }
.trade-cell .stop-val { color: #dc3545; }
.trade-cell .tp-val   { color: #28a745; }

/* Confluence dots */
.dot { display: inline-block; width: 14px; height: 14px; border-radius: 50%; margin: 0 2px; }
.dot-on  { background: #28a745; }
.dot-off { background: #dee2e6; }
.dot-warn { background: #fd7e14; }

/* Señales list items */
.signal-item {
    padding: 0.45rem 0.75rem;
    border-radius: 6px;
    margin-bottom: 0.4rem;
    font-size: 0.9rem;
    display: flex;
    align-items: flex-start;
    gap: 0.5rem;
}
.signal-ok   { background: #f0fff4; border: 1px solid #c3e6cb; }
.signal-warn { background: #fff8f0; border: 1px solid #ffe0b2; }
.signal-block{ background: #fff5f5; border: 1px solid #f5c6cb; }

/* Score formula */
.formula {
    font-family: monospace;
    font-size: 0.9rem;
    background: #272822;
    color: #f8f8f2;
    padding: 0.6rem 1rem;
    border-radius: 6px;
    margin: 0.5rem 0 1rem;
}
.formula .reg  { color: #66d9e8; }
.formula .set  { color: #a9dc76; }
.formula .tri  { color: #ffd866; }
.formula .adj  { color: #ff6188; }
.formula .tot  { color: #fff; font-weight: bold; }

/* Tooltip explicativo — hover sobre cualquier etiqueta con ⓘ */
.tooltip-wrap {
    position: relative;
    display: inline-block;
    cursor: help;
    border-bottom: 1px dotted #999;
}
.tooltip-icon { font-size: 0.72em; color: #888; margin-left: 2px; }
.tooltip-wrap .tooltip-box {
    visibility: hidden;
    opacity: 0;
    position: absolute;
    top: 135%;
    left: 50%;
    transform: translateX(-50%);
    background: #272822;
    color: #f8f8f2;
    text-align: left;
    padding: 0.55rem 0.75rem;
    border-radius: 6px;
    font-size: 0.78rem;
    font-weight: 400;
    line-height: 1.35;
    width: 230px;
    z-index: 999;
    transition: opacity 0.15s ease;
    box-shadow: 0 2px 10px rgba(0,0,0,0.3);
}
.tooltip-wrap .tooltip-box::after {
    content: "";
    position: absolute;
    bottom: 100%;
    left: 50%;
    margin-left: -5px;
    border-width: 5px;
    border-style: solid;
    border-color: transparent transparent #272822 transparent;
}
.tooltip-wrap.tooltip-right .tooltip-box { left: auto; right: 0; transform: none; }
.tooltip-wrap.tooltip-right .tooltip-box::after { left: auto; right: 10px; margin-left: 0; }
.tooltip-wrap:hover .tooltip-box { visibility: visible; opacity: 1; }
</style>
""", unsafe_allow_html=True)

# ── Imports del bot ───────────────────────────────────────────────────────────

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

# ── Helpers ───────────────────────────────────────────────────────────────────

def _pct(value: float, vmin: float, vmax: float) -> float:
    if vmax <= vmin:
        return 0.0
    return max(0.0, min(1.0, (value - vmin) / (vmax - vmin)))


def _bar_color(pct: float) -> str:
    if pct >= 0.6:
        return "bar-green"
    if pct >= 0.35:
        return "bar-orange"
    return "bar-red"


def _score_bar(label: str, value: float, vmin: float, vmax: float, color: str = "", tip: str = "") -> None:
    pct = _pct(value, vmin, vmax)
    css_color = color or _bar_color(pct)
    label_html = _tip(label, tip) if tip else label
    st.markdown(f"""
    <div style="margin-bottom:0.6rem;">
      <div style="display:flex; justify-content:space-between; font-size:0.82rem; color:#555; margin-bottom:2px;">
        <span>{label_html}</span><span><b>{value:.2f}</b></span>
      </div>
      <div class="bar-wrap">
        <div class="bar-fill {css_color}" style="width:{pct*100:.1f}%"></div>
      </div>
    </div>
    """, unsafe_allow_html=True)


def _dots(active: int, total: int = 5) -> str:
    dots = ""
    for i in range(total):
        if i < active:
            css = "dot-on" if active >= 4 else ("dot-warn" if active >= 2 else "dot-off")
            dots += f'<span class="dot {css}"></span>'
        else:
            dots += '<span class="dot dot-off"></span>'
    return dots


def _tip(label: str, explanation: str, align: str = "left") -> str:
    """Envuelve una etiqueta con un tooltip ⓘ (hover) en lenguaje simple."""
    cls = "tooltip-wrap tooltip-right" if align == "right" else "tooltip-wrap"
    return (
        f'<span class="{cls}">{label}<span class="tooltip-icon">ⓘ</span>'
        f'<span class="tooltip-box">{explanation}</span></span>'
    )


def _signal_row(text: str, kind: str) -> None:
    icons = {"ok": "✅", "warn": "⚠️", "block": "🚫"}
    css   = {"ok": "signal-ok", "warn": "signal-warn", "block": "signal-block"}
    st.markdown(f"""
    <div class="signal-item {css[kind]}">
      <span>{icons[kind]}</span>
      <span>{text}</span>
    </div>
    """, unsafe_allow_html=True)


# ── Cache ─────────────────────────────────────────────────────────────────────

@st.cache_data(ttl=300, show_spinner=False)
def _get_market() -> tuple:
    return fetch_vix(), compute_market_breadth()


@st.cache_data(ttl=300, show_spinner=False)
def _get_spy():
    return fetch_data("SPY")


@st.cache_data(ttl=86400, show_spinner=False)
def _get_context():
    return load_market_context()


# ── Sidebar ───────────────────────────────────────────────────────────────────

with st.sidebar:
    st.markdown("### Mercado")
    if st.button("Refrescar", use_container_width=True):
        st.cache_data.clear()
        st.rerun()

    with st.spinner(""):
        vix, breadth = _get_market()

    # VIX
    vix_str = f"{vix:.1f}" if vix is not None else "N/D"
    if vix is None:
        vix_color, vix_label = "#6c757d", "No disponible"
    elif vix >= 30:
        vix_color, vix_label = "#dc3545", "Pánico — bloqueo total"
    elif vix >= 22:
        vix_color, vix_label = "#fd7e14", "Elevado — penalty −0.50"
    else:
        vix_color, vix_label = "#28a745", "Normal"

    vix_tip = _tip(
        "VIX",
        "El “índice del miedo”: mide cuánto nerviosismo hay en el mercado en general "
        "(no en esta acción puntual). Bajo (&lt;22) = calma. Alto (≥30) = pánico, "
        "y el sistema bloquea todas las alertas por seguridad.",
    )
    st.markdown(f"""
    <div class="card" style="border-left: 4px solid {vix_color}; padding: 0.8rem 1rem; margin-bottom:0.6rem;">
      <div style="font-size:0.75rem;color:#888;">{vix_tip}</div>
      <div style="font-size:1.8rem;font-weight:700;color:{vix_color};">{vix_str}</div>
      <div style="font-size:0.78rem;color:{vix_color};">{vix_label}</div>
    </div>
    """, unsafe_allow_html=True)

    # Breadth
    b_str = f"{breadth:.1f}%" if breadth is not None else "N/D"
    if breadth is None:
        b_color, b_label = "#6c757d", "No disponible"
    elif breadth < 40:
        b_color, b_label = "#dc3545", "Crítica — hard block"
    elif breadth < 50:
        b_color, b_label = "#fd7e14", "Limitada — penalty −0.30"
    else:
        b_color, b_label = "#28a745", "Saludable"

    breadth_tip = _tip(
        "Breadth S&amp;P 500",
        "“Amplitud” del mercado: qué porcentaje de las 500 empresas más grandes de EE.UU. "
        "está en tendencia alcista ahora mismo. Si es bajo, la suba general la sostienen "
        "pocas acciones — terreno más frágil para cualquier compra.",
    )
    st.markdown(f"""
    <div class="card" style="border-left: 4px solid {b_color}; padding: 0.8rem 1rem; margin-bottom:0.6rem;">
      <div style="font-size:0.75rem;color:#888;">{breadth_tip}</div>
      <div style="font-size:1.8rem;font-weight:700;color:{b_color};">{b_str}</div>
      <div style="font-size:0.78rem;color:{b_color};">{b_label}</div>
    </div>
    """, unsafe_allow_html=True)

    st.divider()
    st.caption(f"Score mín: **{MIN_SCORE}** · RR mín: **{MIN_RR}**\n\nDatos actualizados cada 5 min.")

# ── Header + Input ────────────────────────────────────────────────────────────

st.markdown("## Stock Sentinel Inspector")
st.caption("Motor idéntico al bot v2.10 (breakout-only) · sin Telegram")

col_mode, col_sym, col_btn = st.columns([2, 5, 1])

with col_mode:
    mode = st.radio("", ["Universo (42)", "Ticker libre"], horizontal=False, label_visibility="collapsed")

with col_sym:
    if mode == "Universo (42)":
        symbol: str = st.selectbox(
            "",
            options=STOCKS,
            format_func=lambda s: f"{s}  —  {STOCK_NAMES.get(s, s)}",
            label_visibility="collapsed",
        )
    else:
        raw = st.text_input("", value="TSLA", placeholder="Ej: TSLA, COIN, PLTR", label_visibility="collapsed")
        symbol = raw.strip().upper()

with col_btn:
    st.write("")
    evaluar = st.button("Evaluar →", type="primary", use_container_width=True)

st.divider()

if not evaluar:
    st.info("Seleccioná una acción y presioná **Evaluar →** para ver el análisis completo.")
    st.stop()

if not symbol:
    st.error("Ingresá un ticker válido.")
    st.stop()

# ── Evaluación ────────────────────────────────────────────────────────────────

with st.spinner(f"Descargando datos y evaluando {symbol}..."):
    try:
        ctx     = _get_context()
        sym_ctx = get_symbol_context(ctx, symbol)
        spy_df  = _get_spy()
        sig     = evaluate_stock(symbol, sym_ctx, vix, spy_df, breadth)
    except Exception as exc:
        st.error(f"Error al evaluar **{symbol}**: {exc}")
        st.stop()

if sig is None:
    st.error(f"Sin datos históricos suficientes para **{symbol}** (mínimo 220 barras).")
    st.stop()

# ── Status badge ──────────────────────────────────────────────────────────────

if sig.blocked:
    status_css, status_icon, status_text = "card-block", "🚫", f"BLOQUEADA — {sig.blocked[0]}"
elif sig.should_alert:
    status_css, status_icon, status_text = "card-alert", "🔥", f"ALERTA — Breakout Expansion"
else:
    status_css, status_icon, status_text = "card-warn", "⚠️", (
        f"SIN SEÑAL — score {sig.score:.2f} (mín {MIN_SCORE}) · RR {sig.rr:.2f}× (mín {MIN_RR})"
    )

st.markdown(f"""
<div class="card {status_css}" style="padding:1rem 1.4rem; margin-bottom:1.2rem;">
  <span style="font-size:1.1rem; font-weight:700;">{status_icon} {sig.name} ({sig.symbol}) &nbsp;·&nbsp; {sig.group}</span><br>
  <span style="font-size:0.9rem;">{status_text}</span>
</div>
""", unsafe_allow_html=True)

# ── Layout principal: columna izquierda + tabs ────────────────────────────────

left, right = st.columns([2, 3])

# ═══════════════════════════════════════════════════════════════
# COLUMNA IZQUIERDA — decisión rápida
# ═══════════════════════════════════════════════════════════════

with left:

    # Score total + RR + Confluencia
    score_color = "#28a745" if sig.score >= MIN_SCORE else "#dc3545"
    rr_color    = "#28a745" if sig.rr >= MIN_RR else "#dc3545"

    score_tip = _tip(
        "Score Total",
        "Puntaje que resume qué tan buena es la oportunidad, sumando tendencia de fondo + "
        "calidad del punto de entrada + si hay un gatillo activo ahora. Cuanto más alto, mejor. "
        f"Por debajo de {MIN_SCORE} el sistema no generaría una alerta.",
    )
    rr_tip = _tip(
        "Risk/Reward",
        "Cuánto podrías ganar por cada dólar que arriesgás. Un valor de 2.00× significa: "
        "si perdés $1 en el stop loss, el objetivo de ganancia es $2.",
        align="right",
    )
    conf_tip = _tip(
        "Confluencia",
        "Cuántas de 5 señales técnicas coinciden ahora mismo (ruptura de máximo reciente, "
        "recuperación sobre la media móvil, cambio de tendencia, impulso alcista, volumen fuerte). "
        "Más señales alineadas = decisión más confiable.",
    )
    rs_tip = _tip(
        "RS vs SPY",
        "Fuerza relativa: compara el rendimiento de esta acción contra el mercado en general "
        "(SPY, el fondo que sigue al índice S&amp;P 500) en los últimos 60 días. Positivo = le "
        "está ganando al mercado; negativo = se está quedando atrás.",
        align="right",
    )

    st.markdown(f"""
    <div class="card card-neutral" style="padding:1.2rem;">

      <div style="display:flex; justify-content:space-between; align-items:flex-start;">
        <div>
          <div class="score-label">{score_tip}</div>
          <div class="score-big" style="color:{score_color};">{sig.score:.2f}</div>
          <div class="score-label" style="color:{score_color};">mínimo {MIN_SCORE}</div>
        </div>
        <div style="text-align:right;">
          <div class="score-label">{rr_tip}</div>
          <div style="font-size:2rem; font-weight:700; color:{rr_color};">{sig.rr:.2f}×</div>
          <div class="score-label" style="color:{rr_color};">mínimo {MIN_RR}</div>
        </div>
      </div>

      <div style="border-top:1px solid #dee2e6; margin:0.8rem 0;"></div>

      <div style="display:flex; justify-content:space-between; align-items:center;">
        <div>
          <div class="score-label">{conf_tip}</div>
          <div style="margin-top:4px;">{_dots(sig.confluence_count)}</div>
          <div style="font-size:0.78rem; color:#555; margin-top:2px;">{sig.confluence_count}/5 señales activas</div>
        </div>
        <div style="text-align:right;">
          <div class="score-label">{rs_tip}</div>
          <div style="font-size:1.4rem; font-weight:700; color:{'#28a745' if sig.rs20 > 0 else '#dc3545'};">{sig.rs20:+.2f}%</div>
        </div>
      </div>

    </div>
    """, unsafe_allow_html=True)

    # Trade Setup
    risk_usd   = sig.price - sig.stop
    target_usd = sig.tp - sig.price

    entry_tip  = _tip("Entry", "Precio actual de la acción — al que, en teoría, comprarías hoy.")
    stop_tip   = _tip("Stop Loss", "Precio de salida de emergencia. Si la acción cae hasta acá, se vende para cortar la pérdida ahí y no más abajo.")
    tp_tip     = _tip("Target (TP)", "Precio objetivo de ganancia (“Take Profit”). Si sube hasta acá, sería el punto para vender y asegurar la ganancia.")
    shares_tip = _tip("Acciones", "Cantidad de acciones a comprar, calculada para que la pérdida máxima posible sea el “Riesgo USD” de al lado.")
    pos_tip    = _tip("Posición USD", "Dinero total que necesitarías para esta compra (acciones × precio de entrada).")
    risk_tip   = _tip("Riesgo USD", "Cuánto dinero perderías como máximo si el precio cae hasta el Stop Loss.")

    st.markdown("##### Trade Setup")
    st.markdown(f"""
    <div class="trade-row">
      <div class="trade-cell">
        <div class="lbl">{entry_tip}</div>
        <div class="val">${sig.price:.2f}</div>
      </div>
      <div class="trade-cell">
        <div class="lbl">{stop_tip}</div>
        <div class="val stop-val">${sig.stop:.2f}</div>
        <div class="lbl">−${risk_usd:.2f}</div>
      </div>
      <div class="trade-cell">
        <div class="lbl">{tp_tip}</div>
        <div class="val tp-val">${sig.tp:.2f}</div>
        <div class="lbl">+${target_usd:.2f}</div>
      </div>
    </div>
    <div class="trade-row">
      <div class="trade-cell">
        <div class="lbl">{shares_tip}</div>
        <div class="val">{sig.position_size_shares:,}</div>
      </div>
      <div class="trade-cell">
        <div class="lbl">{pos_tip}</div>
        <div class="val">${sig.position_size_usd:,.0f}</div>
      </div>
      <div class="trade-cell">
        <div class="lbl">{risk_tip}</div>
        <div class="val">${sig.risk_usd:.2f}</div>
      </div>
    </div>
    """, unsafe_allow_html=True)

    trailing_tip = _tip(
        "Trailing stop inicial",
        "Un stop loss “móvil”: a medida que el precio sube, este nivel sube con él para "
        "proteger las ganancias ya obtenidas, en vez de quedarse fijo.",
    )
    earnings_tip = _tip(
        "Earnings",
        "Fecha del próximo reporte de resultados trimestrales de la empresa. Ese día la "
        "acción puede moverse mucho más de lo normal, para cualquier lado.",
    )
    st.markdown(f"""
    <div style="font-size:0.8rem; color:#888; margin-top:0.3rem;">
      {trailing_tip}: <b>${sig.trailing_stop_initial:.2f}</b>
      {"&nbsp;&nbsp;·&nbsp;&nbsp;📅 " + earnings_tip + ": <b>" + sig.earnings_date + "</b>" if sig.earnings_date else ""}
    </div>
    """, unsafe_allow_html=True)

# ═══════════════════════════════════════════════════════════════
# COLUMNA DERECHA — tabs con detalle
# ═══════════════════════════════════════════════════════════════

with right:

    tab_score, tab_ind, tab_signals = st.tabs(["📊 Scoring", "📐 Indicadores", "🔍 Señales"])

    # ── TAB 1: Scoring ────────────────────────────────────────
    with tab_score:

        # Fórmula del score
        adj = round(sig.score - sig.regime_score - sig.setup_score - sig.trigger_score, 2)
        st.markdown(f"""
        <div class="formula">
          <span class="reg">{sig.regime_score:.2f}</span> (régimen)
          &nbsp;+&nbsp;
          <span class="set">{sig.setup_score:.2f}</span> (setup)
          &nbsp;+&nbsp;
          <span class="tri">{sig.trigger_score:.2f}</span> (trigger)
          &nbsp;+&nbsp;
          <span class="adj">{adj:+.2f}</span> (ajuste)
          &nbsp;=&nbsp;
          <span class="tot">{sig.score:.2f}</span>
        </div>
        """, unsafe_allow_html=True)

        # Regime
        st.markdown(_tip(
            "**Régimen** — tendencia estructural",
            "¿La acción está, de fondo, en una tendencia alcista saludable? Se mide con el "
            "promedio de 200 días (EMA200) y si tiene pendiente positiva.",
        ), unsafe_allow_html=True)
        _score_bar(
            "EMA200 + pendiente", sig.regime_score, 0, 5.0, "bar-blue",
            tip="Puntos ganados por estar sobre la EMA200 con pendiente ascendente. A más puntos, tendencia de fondo más sólida.",
        )

        # Setup
        st.markdown(_tip(
            "**Setup** — calidad de entrada",
            "¿El momento actual es un buen punto para entrar? Combina el RSI "
            "(sobrecompra/sobreventa), el cruce de medias móviles cortas y la fuerza "
            "relativa contra el mercado.",
        ), unsafe_allow_html=True)
        _score_bar(
            "RSI + EMA20/50 + RS", sig.setup_score, -2.5, 3.5, "bar-blue",
            tip="Puntos (pueden ser negativos) según qué tan sano se ve el precio de corto plazo antes de entrar.",
        )

        # Trigger
        st.markdown(_tip(
            "**Trigger** — catalizador de activación",
            "¿Pasó algo ahora mismo que sugiera que el movimiento arranca hoy? Por ejemplo: "
            "rompió un máximo reciente, mejoró el MACD, o entró volumen fuerte.",
        ), unsafe_allow_html=True)
        _score_bar(
            "Prior high + MACD + vol", sig.trigger_score, 0, 5.0, "bar-blue",
            tip="Puntos por señales de activación inmediata: ruptura de precio, impulso (MACD) y volumen.",
        )

        st.divider()

        # Score total vs mínimo
        _score_bar(
            f"Score Total (mín {MIN_SCORE})",
            sig.score,
            0,
            9.0,
            "bar-green" if sig.score >= MIN_SCORE else "bar-red",
            tip=f"Suma de régimen + setup + trigger + ajustes. Si no llega a {MIN_SCORE}, no se generaría una alerta aunque el resto se vea bien.",
        )
        _score_bar(
            f"Risk/Reward (mín {MIN_RR})",
            sig.rr,
            0,
            4.0,
            "bar-green" if sig.rr >= MIN_RR else "bar-red",
            tip=f"Ganancia potencial dividida pérdida potencial. Por debajo de {MIN_RR}×, el trade no compensa el riesgo asumido.",
        )

    # ── TAB 2: Indicadores ────────────────────────────────────
    with tab_ind:

        st.markdown("**Tendencia**")
        c1, c2, c3 = st.columns(3)
        c1.metric("Supertrend", "Alcista" if sig.supertrend_bull else "Bajista",
                  help="Dice si la tendencia de corto plazo es alcista o bajista, mirando si el precio está por encima o por debajo de una línea que se ajusta sola. (Alcista = precio sobre la línea Supertrend, period=10, mult=3.0. Bajista + ADX≥15 bloquea la alerta.)")
        c2.metric("ADX (14)", f"{sig.adx:.1f}",
                  help="Mide qué tan fuerte es la tendencia actual, sin decir la dirección. <20 débil/lateral, 20–40 moderada, >40 fuerte. Supertrend bajista + ADX≥15 = bloqueo.")
        c3.metric("Extensión EMA200", f"{sig.extension_pct:.1f}%",
                  help="Qué tan lejos está el precio de su promedio de 200 días. Muy estirado (lejos) sugiere que podría venir una pausa o corrección. >20% penaliza el score, >30% bloquea la alerta.")

        c4, c5, c6 = st.columns(3)
        c4.metric("ATR (14)", f"${sig.atr:.2f}",
                  help="Cuánto se mueve el precio en un día normal, en dólares (volatilidad). Sirve para ubicar el stop y el target a una distancia realista para esta acción en particular.")
        c5.metric("RS vs SPY (60d)", f"{sig.rs20:+.2f}%",
                  help="Compara el rendimiento de esta acción contra el mercado (SPY) en los últimos 60 días. Positivo = le ganó al mercado. Los sectores Finance/Health toleran hasta -4% igual.")
        c6.metric("Supertrend val", f"{sig.supertrend_val:.2f}",
                  help="Nivel de precio de la línea Supertrend. Mientras la tendencia sea alcista, actúa como un piso de referencia (soporte) por debajo del precio.")

        st.divider()
        st.markdown("**Momentum**")
        d1, d2, d3 = st.columns(3)
        d1.metric("RSI (14)", f"{sig.rsi:.1f}",
                  help="Mide si la acción está “sobrecomprada” (subió muy rápido, podría frenar) o “sobrevendida” (bajó mucho, podría rebotar). Zona ideal para entrar: 45–65. >80 bloquea por sobreextensión.")
        d2.metric("Precio", f"${sig.price:.2f}",
                  help="Último precio de cierre de la acción (ya ajustado por splits y dividendos). Es el precio de referencia para calcular el stop y el target.")
        d3.metric("Grupo / Sector", sig.group if sig.group != "Other" else "—",
                  help="Rubro de la empresa (ej: Tecnología, Finanzas, Salud). Se usa para exigir un umbral distinto de fuerza relativa (RS) según el sector.")

        st.divider()
        st.markdown("**Referencia de niveles**")
        e1, e2 = st.columns(2)
        e1.markdown(f"""
        | Nivel | Valor |
        |---|---|
        | Entry (cierre) | ${sig.price:.2f} |
        | Stop Loss | ${sig.stop:.2f} |
        | Target (TP) | ${sig.tp:.2f} |
        | Trailing Stop | ${sig.trailing_stop_initial:.2f} |
        """)
        e2.markdown(f"""
        | Métrica | Valor |
        |---|---|
        | Risk/Reward | {sig.rr:.2f}× |
        | Score Total | {sig.score:.2f} |
        | Confluencia | {sig.confluence_count}/5 |
        | Signal type | {sig.signal_type} |
        """)

    # ── TAB 3: Señales ────────────────────────────────────────
    with tab_signals:

        if sig.blocked:
            st.markdown(f"##### 🚫 Bloqueos ({len(sig.blocked)})")
            st.caption("Motivos que impiden la alerta aunque el score sea alto — son innegociables.")
            for b in sig.blocked:
                _signal_row(b, "block")
            st.divider()

        st.markdown(f"##### ✅ Razones ({len(sig.reasons)})")
        st.caption("Por qué el sistema considera que esta es una buena oportunidad de entrada.")
        if sig.reasons:
            for r in sig.reasons:
                _signal_row(r, "ok")
        else:
            st.caption("Ninguna")

        st.divider()

        st.markdown(f"##### ⚠️ Advertencias ({len(sig.warnings)})")
        st.caption("Señales de precaución: no bloquean la alerta, pero suman riesgo a tener en cuenta.")
        if sig.warnings:
            for w in sig.warnings:
                _signal_row(w, "warn")
        else:
            st.caption("Sin advertencias")

# ── Footer ────────────────────────────────────────────────────────────────────

st.divider()
_vela_tip = _tip("Última vela", "Fecha y hora (UTC) de la última vela diaria usada para este análisis.")
_rank_tip = _tip("Rank score", "Puntaje interno usado solo para ordenar varias alertas del mismo día por prioridad — no afecta si hay alerta o no.")
_signal_tip = _tip("Signal", "Tipo de señal detectada. Este bot solo opera bajo el modelo “breakout” (ruptura de precio).")
st.markdown(
    f'<div style="font-size:0.82rem; color:#888;">'
    f"{_vela_tip}: <code>{sig.trigger_candle_utc}</code> &nbsp;·&nbsp; "
    f"{_rank_tip}: <code>{sig.rank_score:.2f}</code> &nbsp;·&nbsp; "
    f"{_signal_tip}: <code>{sig.signal_type}</code></div>",
    unsafe_allow_html=True,
)
