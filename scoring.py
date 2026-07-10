"""
Stock Sentinel — scoring.py
============================
Motor de scoring/filtros compartido entre alert.py (vivo) y backtest.py
(historico).

Por que existe: signals.py (v2.9) unifico el calculo de INDICADORES, pero su
propio docstring dejaba explicito que evaluate_stock()/evaluate_bar() seguian
con "scoring acoplado al modo (live vs backtest)... su unificacion completa es
trabajo de iteraciones futuras". Una auditoria posterior confirmo que ese
drift era real y grave: backtest.py nunca incorporo el hard/soft floor de
confluencia (v2.6 Fix #1), el bloqueo Supertrend+RS negativa (v2.6 Fix #3), el
ETF_RS_FLOOR ni el gate de ALERT_ETFS — es decir, varias iteraciones de
endurecimiento de calidad del sistema en vivo nunca pasaron por el backtest,
y ademas backtest.py aplicaba el descuento de RS a ETFs sectoriales (XLK,
XLF, etc.) que alert.py explicitamente exime. Confirmado reproduciblemente
con un harness de datos sinteticos antes de este refactor (ver golden master).

Esta funcion es DETERMINISTICA y de solo lectura de indicadores ya calculados
(last/prev = df.iloc[i-1]/df.iloc[i-2], con las columnas que produce
signals.add_indicators). No hace I/O, no conoce Telegram, earnings, el gap
filter de pre-alerta ni breadth — esos siguen siendo responsabilidad de cada
caller (viven solo en alert.py) o no aplican al backtest historico (breadth y
earnings no tienen equivalente historico limpio con los datos disponibles;
ver CLAUDE.md Roadmap).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

import numpy as np
import pandas as pd


# ── Parametros compartidos ───────────────────────────────────────────────────
@dataclass(frozen=True)
class CoreParams:
    """Umbrales que ambos motores deben usar bit a bit — construidos por cada
    caller a partir de sus propias env vars (mismos nombres/defaults en
    alert.py y backtest.py, ya sincronizados por el workflow)."""

    setup_rsi_min: float
    setup_rsi_max: float
    breakout_rsi_max: float
    pullback_max_atr: float
    breakout_max_atr: float
    weak_adx_block: float
    breakout_rs_min: float
    breakout_near_pct: float
    final_rs_min: float
    final_rs_min_by_group: dict
    vix_block_level: float
    vix_caution_level: float
    vix_low_level: float
    breakout_atr_gate: float
    breakout_extended_vol_ratio: float
    breakout_extended_vol_ratio_low_vix: float
    slope_consistency_ratio: float
    slope_weak_penalty: float
    trigger_vol_ratio: float
    breakout_vol_hard_gate: float
    volume_profile_lookback: int
    volume_profile_penalty: float
    supertrend_regime_block: bool
    supertrend_block_adx_min: float
    supertrend_block_rs_neg: bool
    confluence_hard_floor: int
    confluence_soft_floor: int
    confluence_low_penalty: float
    confluence_bonus: float
    adaptive_rr_extension_threshold: float
    adaptive_rr_multiplier: float
    min_rr: float
    etf_rs_floor: float
    index_etfs: frozenset
    sector_etfs: frozenset
    # Breadth: solo lo usa alert.py (backtest.py no tiene equivalente historico limpio
    # con los datos disponibles); defaults presentes para que backtest.py no tenga que
    # pasarlos si nunca pasa breadth_pct a evaluate_core.
    breadth_min_pct: float = 50.0
    breadth_block_below: float = 40.0


@dataclass
class CoreScoreResult:
    regime_score: float = 0.0
    setup_score: float = 0.0
    trigger_score: float = 0.0
    score_adjustment: float = 0.0
    total_score: float = 0.0
    signal_type: str = "none"
    confluence_count: int = 0
    supertrend_bull: bool = False
    supertrend_cross_up: bool = False
    supertrend_val: float = 0.0
    entry: float = 0.0
    atr: float = 0.0
    rsi: float = 0.0
    adx: float = 0.0
    extension_pct: float = 0.0
    pullback_atr: float = 0.0
    trend_quality: float = 0.0
    stop: float = 0.0
    tp: float = 0.0
    rr: float = 0.0
    reasons: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    blocked: list[str] = field(default_factory=list)


# ── Nucleo de scoring ─────────────────────────────────────────────────────────
def evaluate_core(
    symbol: str,
    group: str,
    last: pd.Series,
    prev: pd.Series,
    rs20: float,
    vix: Optional[float],
    recent_volumes: np.ndarray,
    p: CoreParams,
    base_score_adjustment: float = 0.0,
    breadth_pct: Optional[float] = None,
) -> CoreScoreResult:
    """Evalua una barra ya cerrada (last) contra la anterior (prev) y devuelve
    el desglose de score + reasons/warnings/blocked + stop/tp/rr estructural.
    `last`/`prev` deben venir de un DataFrame procesado por
    signals.add_indicators (mismas columnas en alert.py y backtest.py).

    `base_score_adjustment`: unico parametro "live-only" que se filtra hasta
    aca — el ajuste manual de market_context_stocks.json (normalize_caution_
    adjustment) participa en el MISMO acumulador que despues modifican el
    caution de VIX y la confluencia (asi es como alert.py lo hacia antes del
    refactor: una sola variable corrida de principio a fin). backtest.py no
    tiene contexto manual historico, asi que siempre pasa 0.0."""

    res = CoreScoreResult()
    reasons, warnings, blocked = res.reasons, res.warnings, res.blocked

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

    prior_high_5 = float(last["prior_high_5"]) if pd.notna(last["prior_high_5"]) else entry
    prior_high_20 = float(last["prior_high_20"]) if pd.notna(last["prior_high_20"]) else entry + 2.0 * atr
    prior_swing_low = float(last["prior_low_12"]) if pd.notna(last["prior_low_12"]) else entry - 1.8 * atr
    prior_low_20 = float(last["prior_low_20"]) if pd.notna(last["prior_low_20"]) else prior_swing_low

    st_trend_last = int(last["st_trend"]) if pd.notna(last.get("st_trend")) else 0
    st_trend_prev = int(prev["st_trend"]) if pd.notna(prev.get("st_trend")) else 0
    st_value_last = float(last["st_value"]) if pd.notna(last.get("st_value")) else 0.0
    supertrend_bull = st_trend_last == 1
    supertrend_cross_up = (st_trend_prev == -1) and (st_trend_last == 1)

    res.entry, res.atr, res.rsi, res.adx = entry, atr, rsi, adx
    res.extension_pct, res.pullback_atr = extension_pct, pullback_atr
    res.supertrend_bull, res.supertrend_cross_up, res.supertrend_val = (
        supertrend_bull, supertrend_cross_up, st_value_last,
    )
    res.trend_quality = round(plus_di / (plus_di + minus_di + 1e-9), 2)

    regime_score = 0.0
    setup_score = 0.0
    trigger_score = 0.0

    # ── Hard blocks estructurales ─────────────────────────────────────────
    if vix is not None and vix >= p.vix_block_level:
        blocked.append(f"VIX={vix:.1f} — mercado en pánico")

    # v2.5 #6: breadth filter (solo cuando el caller la provee — hoy solo alert.py).
    # Se resta directo de setup_score (no de un acumulador aparte) para que participe
    # en el MISMO round(...) final que el resto de los componentes, igual que antes.
    if breadth_pct is not None:
        if breadth_pct < p.breadth_block_below:
            blocked.append(f"Breadth pobre ({breadth_pct:.1f}% < {p.breadth_block_below}%) — mercado debil")
        elif breadth_pct < p.breadth_min_pct:
            warnings.append(f"Breadth limitada ({breadth_pct:.1f}% < {p.breadth_min_pct}%)")
            setup_score -= 0.3

    # v2.6 Fix #2/#3: Supertrend bajista — bloquea con ADX>=umbral O RS negativa
    if p.supertrend_regime_block and not supertrend_bull:
        if adx >= p.supertrend_block_adx_min:
            blocked.append(
                f"Supertrend bajista (ST={st_value_last:.2f}, ADX={adx:.1f} >= "
                f"{p.supertrend_block_adx_min}) — sin sesgo alcista"
            )
        elif p.supertrend_block_rs_neg and rs20 < 0:
            blocked.append(
                f"Supertrend bajista (ST={st_value_last:.2f}) + RS negativa ({rs20:+.2f}%) — sector en lag"
            )

    extension_hard_blocked = extension_pct > 30
    if extension_hard_blocked:
        blocked.append(f"Precio sobreextendido: {extension_pct:.1f}% sobre EMA200")
    elif extension_pct > 20:
        ext_penalty = 0.45 * ((extension_pct - 20) / 10.0) ** 2 + 0.45
        setup_score -= round(ext_penalty, 2)
        warnings.append(f"Extension alta: {extension_pct:.1f}% sobre EMA200 (penalty={ext_penalty:.2f})")

    if rsi > 80:
        blocked.append(f"RSI extremo ({rsi:.1f})")
    elif rsi > p.breakout_rsi_max:
        setup_score -= 0.5
        warnings.append(f"RSI caliente ({rsi:.1f})")

    if adx < p.weak_adx_block:
        blocked.append(f"Tendencia sin fuerza suficiente (ADX={adx:.1f} < {p.weak_adx_block:.0f})")
    elif plus_di <= minus_di and adx >= 18:
        blocked.append(f"Dirección bajista (DI+={plus_di:.1f} <= DI-={minus_di:.1f}, ADX={adx:.1f})")

    # ── Regime score ───────────────────────────────────────────────────────
    if entry > ema200:
        regime_score += 1.0
        reasons.append("Precio > EMA200")
    if ema50 > ema200:
        regime_score += 0.75
        reasons.append("EMA50 > EMA200")

    slope5 = float(last["ema200_slope_5"])
    slope3 = float(last["ema200_slope_3"]) if "ema200_slope_3" in last.index else slope5
    if slope5 > 0:
        if slope3 > 0 and slope5 >= slope3 * p.slope_consistency_ratio:
            regime_score += 0.75
            reasons.append("EMA200 con pendiente positiva consistente")
        else:
            regime_score += 0.75 - p.slope_weak_penalty
            warnings.append(f"EMA200 slope inconsistente (slope5={slope5:.2f} vs slope3={slope3:.2f})")
    else:
        regime_score -= 0.2
        warnings.append("EMA200 sin pendiente positiva")

    if supertrend_cross_up:
        regime_score += 1.2
        reasons.append(f"Supertrend: cruce alcista reciente (ST={st_value_last:.2f})")
    elif supertrend_bull:
        regime_score += 0.6
        reasons.append(f"Supertrend alcista (ST={st_value_last:.2f})")
    else:
        regime_score -= 0.5
        warnings.append(f"Supertrend bajista (ST={st_value_last:.2f})")

    di_total = plus_di + minus_di + 1e-9
    trend_quality = plus_di / di_total
    if plus_di > minus_di and adx >= 18:
        quality_bonus = round(1.0 * trend_quality * 2, 2)
        regime_score += quality_bonus
        reasons.append(f"Direccionalidad valida (ADX {adx:.1f}, quality={trend_quality:.2f})")
    elif plus_di > minus_di and adx >= p.weak_adx_block:
        regime_score += 0.4 * trend_quality * 2
        warnings.append(f"Direccionalidad todavia debil (ADX {adx:.1f})")
    elif adx >= 18:
        regime_score -= 0.4
        warnings.append(f"DI sin liderazgo claro (DI+ {plus_di:.1f} vs DI- {minus_di:.1f})")

    # ── Setup score ────────────────────────────────────────────────────────
    if 0.15 <= pullback_atr <= p.pullback_max_atr:
        setup_score += 0.8
        reasons.append(f"Distancia operable a EMA20 ({pullback_atr:.2f} ATR)")
    elif pullback_atr < 0.15:
        setup_score += 0.2
        reasons.append("Precio muy cerca de EMA20")
    elif pullback_atr <= p.breakout_max_atr:
        setup_score -= 0.15
        warnings.append(f"Lejos de EMA20 para pullback ({pullback_atr:.2f} ATR)")
    else:
        setup_score -= 0.45
        warnings.append(f"Muy extendido vs EMA20 ({pullback_atr:.2f} ATR)")

    if p.setup_rsi_min <= rsi <= p.setup_rsi_max and rsi >= prev_rsi:
        setup_score += 1.0
        reasons.append(f"RSI en zona ideal ({rsi:.1f})")
    elif p.setup_rsi_max < rsi <= p.breakout_rsi_max and adx >= 20:
        setup_score += 0.45
        reasons.append(f"RSI fuerte de tendencia ({rsi:.1f})")
    elif 40 <= rsi < p.setup_rsi_min and rsi > prev_rsi:
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

    # FIX: backtest.py solo eximia a "SPY" de la comparacion de RS (`if symbol
    # != "SPY"`), aplicando el descuento/penalizacion de RS tambien a QQQ y a
    # los ETFs sectoriales (XLK, XLF, etc.), algo que alert.py ya evitaba
    # explicitamente (`if symbol not in INDEX_ETFS and symbol not in
    # SECTOR_ETFS`). Un ETF sectorial no "compite" contra SPY de la misma
    # forma que una accion — penalizarlo por RS negativa duplicaba castigo
    # con el ETF_RS_FLOOR de mas abajo, que es el filtro pensado para ETFs.
    is_etf = symbol in p.index_etfs or symbol in p.sector_etfs
    if not is_etf:
        rs_group_discount = 0.5 if group in p.final_rs_min_by_group else 1.0
        if rs20 > 1.0:
            setup_score += 0.9
            reasons.append(f"RS positiva vs SPY: {rs20:+.2f}%")
        elif rs20 > 0:
            setup_score += 0.4
            reasons.append(f"RS levemente positiva vs SPY: {rs20:+.2f}%")
        elif rs20 > -1.0:
            setup_score -= 0.2 * rs_group_discount
            warnings.append(f"RS plana vs SPY: {rs20:+.2f}% (grupo={group})")
        else:
            setup_score -= 0.7 * rs_group_discount
            warnings.append(
                f"RS negativa vs SPY: {rs20:+.2f}% (grupo={group}, "
                f"threshold={p.final_rs_min_by_group.get(group, p.final_rs_min):.1f}%)"
            )

    # ── Trigger score ──────────────────────────────────────────────────────
    broke_prior_high_5 = entry > prior_high_5
    broke_prior_high_20 = entry > prior_high_20
    near_breakout = entry >= prior_high_20 * p.breakout_near_pct
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

    if supertrend_cross_up:
        trigger_score += 0.6
        reasons.append("Supertrend: flip alcista = entrada de tendencia")

    if positive_momentum and float(last["macd_hist"]) > 0:
        trigger_score += 0.8
        reasons.append("MACD histograma acelerando > 0")
    elif positive_momentum:
        trigger_score += 0.4
        reasons.append("MACD mejorando")

    if vol_ratio >= p.trigger_vol_ratio:
        trigger_score += 0.8
        reasons.append(f"Volumen de confirmacion ({vol_ratio:.2f}x)")
    elif vol_ratio >= 0.95:
        trigger_score += 0.15
        reasons.append(f"Volumen aceptable ({vol_ratio:.2f}x)")
    else:
        trigger_score -= 0.4
        warnings.append(f"Volumen flojo ({vol_ratio:.2f}x)")

    effective_vol_gate = (
        p.breakout_extended_vol_ratio_low_vix
        if (vix is not None and vix < p.vix_low_level)
        else p.breakout_extended_vol_ratio
    )
    if pullback_atr > p.breakout_atr_gate and vol_ratio < effective_vol_gate:
        trigger_score -= 0.7
        warnings.append(
            f"Breakout extendido sin vol suficiente ({pullback_atr:.2f} ATR, "
            f"vol={vol_ratio:.2f}x < {effective_vol_gate:.1f}x requerido, VIX={vix})"
        )
        if 2.0 <= pullback_atr < 2.5:
            setup_score -= 0.5
            warnings.append(f"Setup penalty: zona de bajo edge (ext={pullback_atr:.2f} ATR, vol insuficiente)")

    if len(recent_volumes) >= p.volume_profile_lookback:
        vol_decreasing = all(
            recent_volumes[i] > recent_volumes[i + 1] for i in range(len(recent_volumes) - 1)
        )
        if vol_decreasing:
            trigger_score -= p.volume_profile_penalty
            warnings.append(
                f"Volumen decreciente ultimas {p.volume_profile_lookback} velas — posible distribucion"
            )

    # ── Playbook (solo breakout desde v2.10) ────────────────────────────────
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
    is_breakout = (
        breakout_structure
        and vol_ratio >= 0.95
        and rs20 >= p.breakout_rs_min
        and adx >= 18
        and rsi <= p.breakout_rsi_max
        and pullback_atr <= p.breakout_max_atr
        and entry > ema50
    )

    signal_type = "none"
    if is_breakout:
        signal_type = "breakout"
        trigger_score += 1.2
        reasons.append("Playbook: Breakout Expansion")

        # v2.11: hard gate de volumen para breakout — Fase C live (n=28 cerrados):
        # vol<1.5x → -0.482R con 14/18 stops; vol>=1.5x → +1.236R con 50% WR.
        # Default 0 = desactivado; activar via env SOLO tras validar en backtest A/B.
        if p.breakout_vol_hard_gate > 0 and vol_ratio < p.breakout_vol_hard_gate:
            blocked.append(
                f"Volumen insuficiente para breakout "
                f"({vol_ratio:.2f}x < {p.breakout_vol_hard_gate:.1f}x hard gate)"
            )

    if signal_type == "none":
        setup_score -= 0.7
        warnings.append("No encaja como breakout")

    # ── Confluencia (v2.1/v2.3/v2.6, ahora unificada) ───────────────────────
    score_adjustment = base_score_adjustment
    if vix is not None and p.vix_caution_level <= vix < p.vix_block_level:
        score_adjustment -= 0.5
        reasons.append(f"VIX elevado ({vix:.1f})")

    confluence_signals = [
        broke_prior_high_5,
        bullish_reclaim,
        supertrend_cross_up,
        positive_momentum and float(last["macd_hist"]) > 0,
        vol_ratio >= p.trigger_vol_ratio,
    ]
    confluence_count = sum(bool(s) for s in confluence_signals)

    # FIX: backtest.py solo tenia "if confluence_count >= threshold: bonus" —
    # sin hard floor (<2 = block, v2.6 Fix #1), sin soft floor (<3 = penalty),
    # sin la penalizacion de confluencia=5 (v2.3, backtest en vivo mostro 0%
    # WR / -0.543R en ese bucket). Con esto, symbolos con 0-1 senales de
    # confluencia podian generar "trades" en el backtest que jamas habrian
    # alertado en produccion.
    if confluence_count < p.confluence_hard_floor:
        blocked.append(
            f"Confluencia insuficiente ({confluence_count}/5 < {p.confluence_hard_floor} requerido) — "
            f"sin catalizadores de entrada"
        )
    elif confluence_count < p.confluence_soft_floor:
        score_adjustment -= p.confluence_low_penalty
        warnings.append(f"Confluencia baja ({confluence_count}/5 senales) — penalty {p.confluence_low_penalty}")
    elif confluence_count == 4:
        score_adjustment += p.confluence_bonus
        reasons.append(f"Confluencia optima (4/5 senales) +{p.confluence_bonus}")
    elif confluence_count == 5:
        score_adjustment -= 0.6
        warnings.append("Confluencia maxima (5/5) — posible chasing, penalizacion aplicada")
    else:
        # confluence_count == confluence_soft_floor exacto (3 con defaults):
        # zona neutra documentada — ver FIX equivalente en alert.py.
        reasons.append(f"Confluencia neutra ({confluence_count}/5 senales) — sin ajuste")

    total_score = round(regime_score + setup_score + trigger_score + score_adjustment, 2)

    # ── Stop / Target / RR estructural ──────────────────────────────────────
    range_20 = max(prior_high_20 - prior_low_20, 1.2 * atr)
    measured_move = max(0.75 * range_20, 1.6 * atr)

    if signal_type == "breakout":
        raw_stop = max(prior_high_5 - 0.30 * atr, ema20 - 0.35 * atr)
        conservative_floor = entry - 1.50 * atr
        stop = min(raw_stop, conservative_floor)
        stop = min(stop, entry - 0.25 * atr)
        risk = entry - stop
        tp = max(prior_high_20 + 0.20 * atr, entry + measured_move, entry + 1.25 * risk)
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

    effective_min_rr = p.min_rr
    if extension_pct > p.adaptive_rr_extension_threshold:
        effective_min_rr = round(p.min_rr * p.adaptive_rr_multiplier, 2)
        if rr < effective_min_rr:
            warnings.append(
                f"RR insuficiente para setup extendido ({rr:.2f} < {effective_min_rr:.2f} requerido)"
            )
    if rr < effective_min_rr and extension_pct > p.adaptive_rr_extension_threshold and not extension_hard_blocked:
        blocked.append(
            f"Adaptive RR insuficiente: {rr:.2f} < {effective_min_rr:.2f} "
            f"(extension={extension_pct:.1f}% > {p.adaptive_rr_extension_threshold}%)"
        )

    res.regime_score = round(regime_score, 2)
    res.setup_score = round(setup_score, 2)
    res.trigger_score = round(trigger_score, 2)
    res.score_adjustment = round(score_adjustment, 2)
    res.total_score = total_score
    res.signal_type = signal_type
    res.confluence_count = confluence_count
    res.stop = stop
    res.tp = tp
    res.rr = rr
    return res


# ── Filtro final (should_alert) ──────────────────────────────────────────────
def passes_final_filters(
    symbol: str,
    group: str,
    signal_type: str,
    score: float,
    rr: float,
    blocked: list,
    rs20: float,
    require_playbook: bool,
    min_score: float,
    min_rr: float,
    alert_etfs: bool,
    final_rs_min: float,
    final_rs_min_by_group: dict,
    etf_rs_floor: float,
    index_etfs: frozenset,
    sector_etfs: frozenset,
) -> bool:
    """Gate final compartido — antes vivia solo en StockSignal.should_alert
    (alert.py); backtest.py reimplementaba una version incompleta inline (sin
    benchmark_ok/ALERT_ETFS ni el rs_ok especifico de ETFs), por lo que podia
    generar "trades" para SPY/QQQ (que nunca alertarian en vivo con
    ALERT_ETFS=false) y aplicar el FINAL_RS_MIN global a ETFs sectoriales en
    vez de ETF_RS_FLOOR."""
    playbook_ok = signal_type == "breakout" or not require_playbook
    benchmark_ok = alert_etfs or symbol not in index_etfs

    if symbol in index_etfs:
        rs_ok = True
    elif symbol in sector_etfs:
        rs_ok = rs20 >= etf_rs_floor
    else:
        rs_min = final_rs_min_by_group.get(group, final_rs_min)
        rs_ok = rs20 >= rs_min

    return (
        score >= min_score
        and rr >= min_rr
        and not blocked
        and playbook_ok
        and benchmark_ok
        and rs_ok
    )
