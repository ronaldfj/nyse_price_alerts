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

import altair as alt
import numpy as np
import pandas as pd
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
.signal-info { background: #eef6ff; border: 1px solid #b6d4fe; }

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
    ACCOUNT_SIZE_USD,
    ALERTS_HISTORY_FILE,
    MIN_RR,
    MIN_SCORE,
    RISK_PER_TRADE_PCT,
    STOCK_NAMES,
    STOCKS,
    compute_market_breadth,
    evaluate_stock,
    fetch_data,
    fetch_vix,
    get_symbol_context,
    load_market_context,
)
from analyze_alerts_history import (
    add_derived_columns,
    closed_only,
    expectation_table,
    load_history,
    overall_metrics,
    suggestion_lines,
)
from advanced_analytics import Settings as MCSettings
from advanced_analytics import apply_costs, monte_carlo_reorder

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
    icons = {"ok": "✅", "warn": "⚠️", "block": "🚫", "info": "💡"}
    css   = {"ok": "signal-ok", "warn": "signal-warn", "block": "signal-block", "info": "signal-info"}
    st.markdown(f"""
    <div class="signal-item {css[kind]}">
      <span>{icons[kind]}</span>
      <span>{text}</span>
    </div>
    """, unsafe_allow_html=True)


def _stat_card(icon: str, label: str, value: str, sub: str, color: str) -> None:
    st.markdown(f"""
    <div class="card" style="border-left: 4px solid {color}; padding: 0.8rem 1rem;">
      <div style="font-size:0.78rem;color:#888;">{icon} {label}</div>
      <div style="font-size:1.7rem;font-weight:700;color:{color};">{value}</div>
      <div style="font-size:0.75rem;color:{color};">{sub}</div>
    </div>
    """, unsafe_allow_html=True)


# Estado -> (etiqueta con icono, color) para la bitácora e historial de alertas.
_STATUS_META = {
    "hit_target": ("✅ Ganador", "#28a745"),
    "hit_stop": ("🚫 Stop", "#dc3545"),
    "expired": ("⏱️ Expirado", "#fd7e14"),
    "open": ("🕐 Abierto", "#6c757d"),
}

# Mismos supuestos de costos que advanced_analytics.py / CLAUDE.md §6, para que la
# expectancy en vivo sea comparable con el 0.269R post-costos del backtest de 3 años.
_MC_RUNS = 2000
_COST_COMMISSION_USD = 1.0
_COST_SLIPPAGE_PCT = 0.05
_BACKTEST_BASELINE_R = 0.269


def _profitability_verdict(n_closed: int, p_profit: float, avg_r_costs: float) -> tuple[str, str, str]:
    """Traduce el bootstrap a un veredicto en lenguaje simple.
    Umbrales fijos de antemano — no se ajustan a los datos actuales."""
    if n_closed < 15:
        return "🔵", "Datos insuficientes todavía para opinar", "#6c757d"
    if avg_r_costs <= 0:
        return "🔴", "Sin edge — expectancy negativa incluso con esta muestra", "#dc3545"
    if n_closed < 30:
        return "🟡", "Señal positiva, pero la muestra todavía es chica para confirmarlo", "#fd7e14"
    if p_profit >= 80:
        return "🟢", "Rentable con confianza estadística razonable", "#28a745"
    if p_profit >= 60:
        return "🟡", "Rentable pero no concluyente — seguir de cerca", "#fd7e14"
    return "🔴", "Sin edge claro — la mayoría de las simulaciones no ganan", "#dc3545"


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


@st.cache_data(ttl=300, show_spinner=False)
def _get_alert_history() -> pd.DataFrame | None:
    """Carga y enriquece alerts_history.csv reusando analyze_alerts_history.py
    (fuente única de verdad para el cálculo de performance — no duplicar aquí)."""
    try:
        raw = load_history(Path(ALERTS_HISTORY_FILE))
    except (FileNotFoundError, ValueError):
        return None
    return add_derived_columns(raw)


# ── Vista: Historial de Alertas ────────────────────────────────────────────────

def _render_history_view() -> None:
    st.caption(
        "Performance real del bot en producción — aciertos (✅ hit\\_target) y "
        "desaciertos (🚫 hit\\_stop / ⏱️ expired) de las alertas ya cerradas."
    )

    df = _get_alert_history()
    if df is None:
        st.info(f"Todavía no existe `{ALERTS_HISTORY_FILE}` con alertas registradas.")
        return

    df_closed = closed_only(df)
    total = len(df)
    n_open = int(df["status"].eq("open").sum())
    n_closed = len(df_closed)

    if df_closed.empty:
        st.info(
            f"Hay {total} alertas registradas pero ninguna cerrada todavía "
            "(todas siguen en seguimiento). Volvé cuando se resuelva la primera."
        )
        return

    if n_closed < 30:
        st.warning(
            f"Muestra chica: solo **{n_closed}** trades cerrados. Tratá estas cifras "
            "como orientativas — no como validación estadística (referencia interna del "
            "proyecto: <30 trades cerrados implica riesgo de overfitting si se ajustan "
            "parámetros en base a esto)."
        )

    # ── Veredicto: ¿es rentable? ─────────────────────────────────────────────
    st.markdown("### ¿El bot es rentable?")

    mc_settings = MCSettings(
        input_path=Path(ALERTS_HISTORY_FILE),
        outdir=Path("."),
        initial_capital=ACCOUNT_SIZE_USD,
        risk_per_trade_pct=RISK_PER_TRADE_PCT,
        commission_per_trade=_COST_COMMISSION_USD,
        slippage_pct=_COST_SLIPPAGE_PCT,
        mc_runs=_MC_RUNS,
        rolling_window_trades=30,
    )
    r_raw = df_closed["realized_r"]
    r_costs = apply_costs(r_raw, df_closed, mc_settings)
    avg_r_raw = float(r_raw.mean())
    avg_r_costs = float(r_costs.mean())

    mc = monte_carlo_reorder(r_costs, mc_settings, n_runs=_MC_RUNS)
    p_profit = float((mc["total_return_pct"] > 0).mean() * 100) if not mc.empty else float("nan")

    v_icon, v_headline, v_color = _profitability_verdict(n_closed, p_profit, avg_r_costs)

    st.markdown(f"""
    <div class="card" style="border-left: 6px solid {v_color}; padding:1.2rem 1.4rem;">
      <div style="font-size:0.78rem;color:#888;letter-spacing:0.02em;">
        VEREDICTO — bootstrap de {_MC_RUNS} simulaciones sobre los {n_closed} trades cerrados reales
      </div>
      <div style="font-size:1.5rem;font-weight:700;color:{v_color};margin-top:2px;">{v_icon} {v_headline}</div>
    </div>
    """, unsafe_allow_html=True)

    v1, v2, v3, v4 = st.columns(4)
    v1.metric(
        "P(retorno > 0)", f"{p_profit:.1f}%" if pd.notna(p_profit) else "N/D",
        help=f"De {_MC_RUNS} simulaciones que remuestrean (con reemplazo) los {n_closed} trades cerrados reales, "
             "% que terminaron con ganancia neta. No es una garantía a futuro: resume qué tan robusto es el "
             "resultado observado frente al azar de qué trades tocaron y en qué orden.",
    )
    v2.metric(
        "Expectancy con costos", f"{avg_r_costs:+.3f}R",
        help=f"R promedio por trade después de comisión (${_COST_COMMISSION_USD:.2f} round-trip) y slippage "
             f"({_COST_SLIPPAGE_PCT:.2f}% por lado) — mismos supuestos que el backtest de 3 años. "
             f"Sin costos: {avg_r_raw:+.3f}R.",
    )
    if not mc.empty:
        med_ret = mc["total_return_pct"].median()
        p05_ret = mc["total_return_pct"].quantile(0.05)
        p95_ret = mc["total_return_pct"].quantile(0.95)
    else:
        med_ret = p05_ret = p95_ret = float("nan")
    v3.metric(
        "Retorno simulado (mediana)", f"{med_ret:+.1f}%" if pd.notna(med_ret) else "N/D",
        help=f"Retorno mediano sobre ${ACCOUNT_SIZE_USD:,.0f} de capital simulado, con sizing de "
             f"{RISK_PER_TRADE_PCT:.1f}% de riesgo por trade, a través de las {_MC_RUNS} simulaciones bootstrap.",
    )
    v4.metric(
        "Rango p05 – p95",
        f"{p05_ret:+.1f}% / {p95_ret:+.1f}%" if pd.notna(p05_ret) else "N/D",
        help="Intervalo donde cayó el 90% de las simulaciones. Cuanto más ancho, más incertidumbre "
             "queda todavía con esta cantidad de trades — se va a ir angostando a medida que se acumule muestra.",
    )

    if not mc.empty:
        counts, edges = np.histogram(mc["total_return_pct"], bins=30)
        hist_df = pd.DataFrame({"bin_left": edges[:-1], "bin_right": edges[1:], "count": counts})
        hist_df["bin_center"] = (hist_df["bin_left"] + hist_df["bin_right"]) / 2

        st.caption(
            f"Distribución de resultados en las {_MC_RUNS} simulaciones bootstrap "
            f"(remuestreo con reemplazo de los {n_closed} trades reales)."
        )
        hist = alt.Chart(hist_df).mark_bar().encode(
            x=alt.X("bin_left:Q", title="Retorno total simulado (%)"),
            x2="bin_right:Q",
            y=alt.Y("count:Q", title="N° de simulaciones"),
            color=alt.condition("datum.bin_center >= 0", alt.value("#28a745"), alt.value("#dc3545")),
            tooltip=[
                alt.Tooltip("bin_left:Q", format="+.1f", title="Desde %"),
                alt.Tooltip("bin_right:Q", format="+.1f", title="Hasta %"),
                alt.Tooltip("count:Q", title="Simulaciones"),
            ],
        )
        zero_rule_mc = alt.Chart(pd.DataFrame({"x": [0]})).mark_rule(color="#333", strokeWidth=1.5).encode(x="x:Q")
        st.altair_chart((hist + zero_rule_mc).properties(height=220), use_container_width=True)

    st.caption(
        f"Referencia: el backtest histórico de 3 años documenta una expectancy de "
        f"{_BACKTEST_BASELINE_R:+.3f}R/trade post-costos. Real hasta ahora: {avg_r_costs:+.3f}R/trade post-costos "
        f"({'por encima' if avg_r_costs >= _BACKTEST_BASELINE_R else 'por debajo'} del baseline, con muchísima "
        "menos muestra que el backtest)."
    )

    st.divider()

    # ── Puntualidad de entrada ───────────────────────────────────────────────
    st.markdown("### ¿Las alertas entran a tiempo?")
    st.caption(
        "MFE/MAE (ya registrados por el tracker) son el mejor y el peor precio alcanzado después de "
        "la alerta, medidos en múltiplos de riesgo (R). Sirven como proxy de timing: una entrada puntual "
        "debería moverse a favor con poco \"dolor\" (MAE) antes de resolver. Ojo: no sabemos en qué barra "
        "ocurrió cada extremo dentro del trade, solo el valor alcanzado — es una lectura aproximada, no exacta."
    )

    tim = df_closed.dropna(subset=["mfe_pct", "mae_pct", "risk_dollars"]).copy()
    tim = tim[tim["risk_dollars"] > 0]

    if tim.empty:
        st.caption("Sin datos de MFE/MAE todavía para medir puntualidad.")
    else:
        tim["mfe_r"] = (tim["mfe_pct"] / 100.0 * tim["effective_entry"]) / tim["risk_dollars"]
        tim["mae_r"] = (tim["mae_pct"] / 100.0 * tim["effective_entry"]) / tim["risk_dollars"]

        winners = tim[tim["status"] == "hit_target"]
        losers = tim[tim["status"] == "hit_stop"]

        heat_winners = float(winners["mae_r"].mean()) if not winners.empty else float("nan")
        bounce_losers = float(losers["mfe_r"].mean()) if not losers.empty else float("nan")
        capture_eff = float((winners["realized_r"] / winners["mfe_r"]).mean()) if not winners.empty else float("nan")

        t1, t2, t3 = st.columns(3)
        t1.metric(
            "Heat en ganadores", f"{heat_winners:+.2f}R" if pd.notna(heat_winners) else "N/D",
            help="Adverse excursion promedio (peor drawdown) que tuvieron que aguantar los trades que "
                 "terminaron en target, antes de resolver a favor. Cerca de 0R = entrada limpia, se movió "
                 "a favor casi de inmediato. Cerca de -1R = estuvo al borde del stop antes de dar vuelta — "
                 "señal de timing marginal (entrada temprana).",
        )
        t2.metric(
            "Rebote en perdedores", f"{bounce_losers:+.2f}R" if pd.notna(bounce_losers) else "N/D",
            help="Favorable excursion promedio que alcanzaron los trades que terminaron en stop, antes de "
                 "fallar. Si es alto, hubo algo de continuación a favor antes de fallar (no fue un error de "
                 "dirección total). Cerca de 0R = fueron directo al stop sin ningún avance previo.",
        )
        t3.metric(
            "Eficiencia de captura", f"{capture_eff * 100:.0f}%" if pd.notna(capture_eff) else "N/D",
            help="Entre los trades ganadores, qué % del mejor movimiento a favor (MFE) terminó cobrando "
                 "el sistema al cerrar en el target. Bajo = el target queda corto frente a lo que el "
                 "movimiento realmente daba.",
        )

        scatter = alt.Chart(tim).mark_circle(size=90, opacity=0.75).encode(
            x=alt.X("mae_r:Q", title="Peor momento del trade (MAE, en R)"),
            y=alt.Y("realized_r:Q", title="Resultado final (R)"),
            color=alt.Color(
                "status:N",
                title="Resultado",
                scale=alt.Scale(
                    domain=["hit_target", "hit_stop", "expired"],
                    range=["#28a745", "#dc3545", "#fd7e14"],
                ),
            ),
            tooltip=[
                alt.Tooltip("symbol:N", title="Símbolo"),
                alt.Tooltip("mae_r:Q", title="MAE (R)", format="+.2f"),
                alt.Tooltip("mfe_r:Q", title="MFE (R)", format="+.2f"),
                alt.Tooltip("realized_r:Q", title="Resultado (R)", format="+.2f"),
                alt.Tooltip("status:N", title="Estado"),
            ],
        )
        zero_v = alt.Chart(pd.DataFrame({"x": [0]})).mark_rule(color="#adb5bd", strokeDash=[4, 4]).encode(x="x:Q")
        zero_h = alt.Chart(pd.DataFrame({"y": [0]})).mark_rule(color="#adb5bd", strokeDash=[4, 4]).encode(y="y:Q")
        st.caption(
            "Cada punto es un trade cerrado. Cuanto más pegado a 0 en el eje X (MAE), más limpio el timing "
            "de entrada — lejos a la izquierda significa que tuvo que aguantar mucho drawdown antes de resolver."
        )
        st.altair_chart((scatter + zero_v + zero_h).properties(height=320), use_container_width=True)

    st.divider()

    overall = overall_metrics(df_closed)

    # ── KPIs ────────────────────────────────────────────────────────────────
    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Alertas totales", total,
               help="Todas las alertas generadas por el bot, incluidas las que siguen abiertas.")
    k2.metric("Cerradas / Abiertas", f"{n_closed} / {n_open}",
               help="Trades ya resueltos (ganador, stop o expirado) vs. los que el tracker todavía sigue.")
    k3.metric("Win Rate", f"{overall['win_rate_pct']:.1f}%",
               help="% de trades cerrados que llegaron al target (hit_target) sobre el total de cerrados.")
    k4.metric("R promedio realizado", f"{overall['avg_realized_r']:+.2f}R",
               help="Expectancy real: ganancia/pérdida promedio por trade en múltiplos de riesgo (R). "
                    "Positivo = el sistema gana dinero en promedio.")

    k5, k6, k7, k8 = st.columns(4)
    k5.metric("Mediana R", f"{overall['median_realized_r']:+.2f}R",
               help="La mitad de los trades cerrados rindió más que esto, la otra mitad menos. "
                    "Menos sensible a outliers que el promedio.")
    k6.metric("Tasa de Stop", f"{overall['stop_rate_pct']:.1f}%",
               help="% de trades cerrados que tocaron el stop loss.")
    k7.metric("Tasa de Expirado", f"{overall['expired_rate_pct']:.1f}%",
               help="% de trades que se cerraron por vencimiento del plazo máximo (20 barras) "
                    "sin tocar target ni stop.")
    k8.metric("Días promedio abierto", f"{overall['avg_days_open']:.1f}",
               help="Cuántos días de mercado, en promedio, estuvo abierta una posición hasta cerrarse.")

    st.divider()

    # ── Aciertos y desaciertos ──────────────────────────────────────────────
    st.markdown("##### Aciertos y desaciertos")
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        _stat_card("✅", "Ganadores", str(overall["wins"]),
                    f"{overall['win_rate_pct']:.1f}% de cerradas", "#28a745")
    with c2:
        _stat_card("🚫", "Stops", str(overall["stops"]),
                    f"{overall['stop_rate_pct']:.1f}% de cerradas", "#dc3545")
    with c3:
        _stat_card("⏱️", "Expirados", str(overall["expired"]),
                    f"{overall['expired_rate_pct']:.1f}% de cerradas", "#fd7e14")
    with c4:
        pct_open = (n_open / total * 100) if total else 0.0
        _stat_card("🕐", "Abiertas ahora", str(n_open), f"{pct_open:.1f}% del total", "#6c757d")

    st.divider()

    # ── Curva de equity ─────────────────────────────────────────────────────
    st.markdown("##### Curva de equity (R acumulado)")
    st.caption(
        "Suma acumulada de R realizado, trade a trade, ordenada por fecha de cierre. "
        "Sube = el sistema viene ganando; baja = viene perdiendo."
    )

    eq = df_closed.dropna(subset=["realized_r"]).copy()
    date_col = "closed_utc" if "closed_utc" in eq.columns and eq["closed_utc"].notna().any() else "timestamp_utc"
    eq = eq.dropna(subset=[date_col]).sort_values(date_col)

    if len(eq) >= 2:
        eq["cum_r"] = eq["realized_r"].cumsum()
        eq["trade_n"] = range(1, len(eq) + 1)

        base = alt.Chart(eq).encode(x=alt.X("trade_n:Q", title="N° de trade cerrado"))
        zero_rule = alt.Chart(pd.DataFrame({"y": [0]})).mark_rule(
            strokeDash=[4, 4], color="#adb5bd"
        ).encode(y="y:Q")
        line = base.mark_line(color="#0066cc", strokeWidth=2.5).encode(
            y=alt.Y("cum_r:Q", title="R acumulado")
        )
        points = base.mark_circle(size=60).encode(
            y="cum_r:Q",
            color=alt.condition("datum.realized_r >= 0", alt.value("#28a745"), alt.value("#dc3545")),
            tooltip=[
                alt.Tooltip("symbol:N", title="Símbolo"),
                alt.Tooltip(f"{date_col}:T", title="Cierre"),
                alt.Tooltip("realized_r:Q", title="R del trade", format="+.2f"),
                alt.Tooltip("cum_r:Q", title="R acumulado", format="+.2f"),
                alt.Tooltip("status:N", title="Resultado"),
            ],
        )
        st.altair_chart(
            (zero_rule + line + points).properties(height=280),
            use_container_width=True,
        )
    else:
        st.caption("Necesitás al menos 2 trades cerrados con fecha para trazar la curva.")

    st.divider()

    # ── Rendimiento por categoría ───────────────────────────────────────────
    st.markdown("##### Rendimiento por categoría")
    dims = {
        "Playbook": "playbook",
        "Score": "score_bucket",
        "RS vs SPY": "rs_bucket",
        "Extensión": "extension_bucket",
        "Risk/Reward": "rr_bucket",
        "Símbolo": "symbol",
        "Grupo/Sector": "group",
    }
    dim_label = st.selectbox("Agrupar por", options=list(dims.keys()))
    col = dims[dim_label]
    tbl = expectation_table(df_closed, col)

    if tbl.empty:
        st.caption("Sin datos suficientes para esta categoría.")
    else:
        bar = alt.Chart(tbl).mark_bar(size=18).encode(
            y=alt.Y(f"{col}:N", sort="-x", title=None),
            x=alt.X("avg_realized_r:Q", title="R promedio realizado"),
            color=alt.condition("datum.avg_realized_r >= 0", alt.value("#28a745"), alt.value("#dc3545")),
            tooltip=[
                alt.Tooltip(f"{col}:N", title=dim_label),
                alt.Tooltip("n:Q", title="Trades"),
                alt.Tooltip("win_rate:Q", title="Win rate %", format=".1f"),
                alt.Tooltip("avg_realized_r:Q", title="R promedio", format="+.2f"),
            ],
        )
        zero_rule2 = alt.Chart(pd.DataFrame({"x": [0]})).mark_rule(color="#adb5bd").encode(x="x:Q")
        text = bar.mark_text(align="left", dx=4, color="#555").encode(
            text=alt.Text("avg_realized_r:Q", format="+.2f")
        )
        st.altair_chart(
            (bar + zero_rule2 + text).properties(height=max(120, 32 * len(tbl))),
            use_container_width=True,
        )

        st.dataframe(
            tbl.rename(columns={
                col: dim_label, "n": "Trades", "win_rate": "Win Rate %",
                "avg_realized_r": "Avg R", "avg_rr": "Avg RR planificado",
                "avg_days_open": "Días promedio",
            }),
            width="stretch",
            hide_index=True,
        )

    st.divider()

    # ── Lecturas automáticas ────────────────────────────────────────────────
    st.markdown("##### Lecturas automáticas")
    st.caption(
        "Observaciones calculadas sobre los trades cerrados — sirven para calibrar "
        "parámetros, no como verdad absoluta con muestra chica."
    )
    for s in suggestion_lines(df_closed):
        _signal_row(s, "info")

    st.divider()

    # ── Bitácora de trades ──────────────────────────────────────────────────
    st.markdown("##### Bitácora de trades")
    log_cols = [
        "timestamp_utc", "symbol", "playbook", "score", "rr", "status",
        "realized_r", "days_open", "effective_entry", "resolved_exit_price",
    ]
    log_df = df.sort_values("timestamp_utc", ascending=False)[
        [c for c in log_cols if c in df.columns]
    ].copy()
    log_df["status"] = log_df["status"].map(lambda s: _STATUS_META.get(s, (s, "#000"))[0])
    log_df = log_df.rename(columns={
        "timestamp_utc": "Fecha alerta", "symbol": "Símbolo", "playbook": "Playbook",
        "score": "Score", "rr": "RR plan.", "status": "Resultado",
        "realized_r": "R realizado", "days_open": "Días abierto",
        "effective_entry": "Entry real", "resolved_exit_price": "Exit",
    })
    st.dataframe(log_df, width="stretch", hide_index=True)


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

view = st.segmented_control(
    "Vista",
    options=["🔍 Evaluar Ticker", "📊 Historial de Alertas"],
    default="🔍 Evaluar Ticker",
    label_visibility="collapsed",
)

if view == "📊 Historial de Alertas":
    st.divider()
    _render_history_view()
    st.stop()

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
