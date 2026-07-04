"""
Stock Sentinel — Advanced Analytics (Fase A)
==============================================
Metricas quant-grade sobre alerts_history.csv o backtest_trades.csv.

Outputs:
  - advanced_report.md      reporte completo en markdown
  - equity_curve.csv        curva de capital trade-por-trade
  - monte_carlo.csv         resultados de N simulaciones
  - distribution_r.csv      distribucion completa de R por bucket

Uso:
  python advanced_analytics.py --input backtest_output/backtest_trades.csv
  python advanced_analytics.py --input alerts_history.csv --capital 10000
  python advanced_analytics.py --input backtest_output/backtest_trades.csv --mc-runs 5000

Costos asumidos (configurables via CLI):
  - Comision: $1 por trade (round-trip)
  - Slippage: 0.05% por entry y 0.05% por exit (0.1% total)
"""

from __future__ import annotations

import argparse
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd


logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s", datefmt="%H:%M:%S")
log = logging.getLogger("advanced_analytics")


# ── Config ──────────────────────────────────────────────────────────────────
@dataclass
class Settings:
    input_path: Path
    outdir: Path
    initial_capital: float
    risk_per_trade_pct: float
    commission_per_trade: float
    slippage_pct: float
    mc_runs: int
    rolling_window_trades: int
    filter_playbook: str = ""


# ── Carga + normalizacion ───────────────────────────────────────────────────
def load_trades(path: Path) -> pd.DataFrame:
    """Carga el CSV y filtra solo trades cerrados con datos validos."""
    if not path.exists():
        raise FileNotFoundError(f"No existe: {path}")

    df = pd.read_csv(path)
    if df.empty:
        raise ValueError(f"Archivo vacio: {path}")

    # Normalizar columnas numericas
    num_cols = ["price", "real_entry", "target", "stop", "rr", "score", "pnl_pct",
                "mfe_pct", "mae_pct", "exit_price", "bars_open", "days_open",
                "rs20", "extension_pct", "vol_ratio", "confluence_count"]
    for c in num_cols:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce")

    # Filtrar a cerrados
    if "status" in df.columns:
        df["status"] = df["status"].fillna("open").astype(str).str.lower().str.strip()
        df = df[df["status"].isin(["hit_target", "hit_stop", "expired"])].copy()

    # Fecha de cierre
    if "closed_utc" in df.columns:
        df["closed_dt"] = pd.to_datetime(df["closed_utc"], utc=True, errors="coerce")
    elif "exit_date" in df.columns:
        df["closed_dt"] = pd.to_datetime(df["exit_date"], utc=True, errors="coerce")
    else:
        df["closed_dt"] = pd.to_datetime(df.get("timestamp_utc"), utc=True, errors="coerce")

    df = df.dropna(subset=["closed_dt", "price", "stop"])
    df = df.sort_values("closed_dt").reset_index(drop=True)

    # FIX (mejora institucional #2): "effective_entry" = real_entry (Open real de la
    # primera barra posterior a la señal/alerta) cuando esta disponible, si no "price".
    # Para backtest_trades.csv ambas columnas ya coinciden (price = real_entry desde el
    # Fix #1 de simulate_trade); para alerts_history.csv historico (generado antes de
    # esta mejora) o trades aun sin una barra cerrada, real_entry puede venir vacio/0 —
    # se cae a "price" en ese caso, igual que se comportaba antes de agregar la columna.
    if "real_entry" in df.columns:
        df["effective_entry"] = df["real_entry"].where(df["real_entry"] > 0, df["price"])
    else:
        df["effective_entry"] = df["price"]

    log.info("Cargados %s trades cerrados desde %s", len(df), path)
    return df


# ── Calculos base ──────────────────────────────────────────────────────────
def compute_realized_r(df: pd.DataFrame) -> pd.Series:
    """R realizado por trade: (exit_price - price) / (price - stop), uniforme
    para todos los status cerrados (hit_target, hit_stop, expired).
    # FIX: la version anterior usaba la columna "rr" (RR estructural, calculado sobre el
    # precio TEORICO de la barra de senal) para trades hit_target, en vez de recalcular
    # contra "price". En backtest_trades.csv, "price" es el real_entry (Open real de la
    # barra siguiente tras el fix de look-ahead de simulate_trade), asi que "rr" y "price"
    # tienen bases distintas: cualquier gap de hasta 2% (el umbral del gap filter) entre el
    # cierre teorico de la senal y la apertura real se colaba sin corregir en el lado
    # ganador de la distribucion, contaminando expectancy, Monte Carlo y equity curve.
    # exit_price ya contiene el precio de salida real (target/stop/cierre por time-stop)
    # para cualquier status cerrado, asi que una sola formula basta: para hit_stop,
    # exit_price siempre iguala a stop por construccion, dando -1.0 automaticamente.
    """
    entry = df["effective_entry"] if "effective_entry" in df.columns else df["price"]
    risk = entry - df["stop"]
    exit_p = df["exit_price"]
    if "current_price" in df.columns:
        exit_p = exit_p.fillna(df["current_price"])
    exit_p = exit_p.fillna(entry)
    return (exit_p - entry) / (risk + 1e-9)


def apply_costs(realized_r: pd.Series, df: pd.DataFrame, settings: Settings) -> pd.Series:
    """Resta comisiones y slippage de cada R realizado.
    Costos expresados en R: cada $ de costo = (costo/risk_per_share)."""
    entry = df["effective_entry"] if "effective_entry" in df.columns else df["price"]
    risk_per_share = (entry - df["stop"]).abs()
    # Comision en R = comision / (risk_per_share * shares)
    # Asumimos sizing por % riesgo: shares = (capital * risk%) / risk_per_share
    risk_budget = settings.initial_capital * (settings.risk_per_trade_pct / 100.0)
    shares = (risk_budget / risk_per_share).round()
    notional = entry * shares

    commission_dollars = settings.commission_per_trade  # round-trip
    slippage_dollars = notional * (settings.slippage_pct / 100.0) * 2  # entry + exit
    total_cost = commission_dollars + slippage_dollars

    cost_in_r = total_cost / (risk_per_share * shares).replace(0, np.nan)
    cost_in_r = cost_in_r.fillna(0)

    return realized_r - cost_in_r


# ── Equity curve ────────────────────────────────────────────────────────────
def build_equity_curve(df: pd.DataFrame, realized_r: pd.Series, settings: Settings) -> pd.DataFrame:
    """Curva de equity con compounding fijo por % riesgo."""
    capital = settings.initial_capital
    rows = []
    peak = capital
    max_dd = 0.0
    max_dd_duration = 0
    current_dd_bars = 0

    for i, (idx, row) in enumerate(df.iterrows()):
        risk_amount = capital * (settings.risk_per_trade_pct / 100.0)
        pnl_dollars = realized_r.iloc[i] * risk_amount
        capital += pnl_dollars

        peak = max(peak, capital)
        dd = (capital - peak) / peak * 100.0  # negativo
        max_dd = min(max_dd, dd)

        if dd < 0:
            current_dd_bars += 1
            max_dd_duration = max(max_dd_duration, current_dd_bars)
        else:
            current_dd_bars = 0

        rows.append({
            "trade_n":       i + 1,
            "closed_dt":     row["closed_dt"],
            "symbol":        row.get("symbol", ""),
            "status":        row["status"],
            "realized_r":    round(realized_r.iloc[i], 3),
            "pnl_dollars":   round(pnl_dollars, 2),
            "capital":       round(capital, 2),
            "peak":          round(peak, 2),
            "drawdown_pct":  round(dd, 2),
            "in_drawdown":   dd < -0.01,
        })

    eq_df = pd.DataFrame(rows)
    return eq_df


# ── Monte Carlo: bootstrap (sample CON reemplazo) ──────────────────────────
def monte_carlo_reorder(realized_r: pd.Series, settings: Settings, n_runs: int = 1000) -> pd.DataFrame:
    """Bootstrap: muestrea N trades CON reemplazo de la distribucion empirica.
    Bug fix v2: con compounding fijo, una simple permutacion da el mismo capital
    final (la multiplicacion es conmutativa). El verdadero Monte Carlo requiere
    bootstrap — cada run puede tener trades repetidos o ausentes, generando
    distribuciones reales de equity y drawdown."""
    rng = np.random.default_rng(seed=42)
    r_array = realized_r.dropna().values
    n_trades = len(r_array)

    if n_trades == 0:
        return pd.DataFrame()

    results = []
    for run in range(n_runs):
        # Bootstrap: sample CON reemplazo, mismo n_trades
        sampled = rng.choice(r_array, size=n_trades, replace=True)

        capital = settings.initial_capital
        peak = capital
        max_dd = 0.0
        consec_losses = 0
        max_consec_losses = 0

        for r in sampled:
            risk_amount = capital * (settings.risk_per_trade_pct / 100.0)
            capital += r * risk_amount
            peak = max(peak, capital)
            dd = (capital - peak) / peak * 100.0
            max_dd = min(max_dd, dd)

            if r < 0:
                consec_losses += 1
                max_consec_losses = max(max_consec_losses, consec_losses)
            else:
                consec_losses = 0

        results.append({
            "run":              run,
            "final_capital":    round(capital, 2),
            "total_return_pct": round((capital / settings.initial_capital - 1) * 100, 2),
            "max_drawdown_pct": round(max_dd, 2),
            "max_consec_losses": max_consec_losses,
        })

    return pd.DataFrame(results)


# ── Distribucion de R ──────────────────────────────────────────────────────
def distribution_summary(realized_r: pd.Series) -> dict:
    r = realized_r.dropna()
    if r.empty:
        return {}

    return {
        "n":             len(r),
        "mean":          round(float(r.mean()), 3),
        "median":        round(float(r.median()), 3),
        "std":           round(float(r.std()), 3),
        "min":           round(float(r.min()), 3),
        "max":           round(float(r.max()), 3),
        "q05":           round(float(r.quantile(0.05)), 3),
        "q25":           round(float(r.quantile(0.25)), 3),
        "q75":           round(float(r.quantile(0.75)), 3),
        "q95":           round(float(r.quantile(0.95)), 3),
        "skew":          round(float(r.skew()), 3),
        "kurtosis":      round(float(r.kurtosis()), 3),
        "winning_trades": int((r > 0).sum()),
        "losing_trades":  int((r < 0).sum()),
        "expectancy":    round(float(r.mean()), 3),
        "win_rate_pct":  round(float((r > 0).mean()) * 100, 2),
    }


def distribution_buckets(realized_r: pd.Series) -> pd.DataFrame:
    r = realized_r.dropna()
    if r.empty:
        return pd.DataFrame()

    bins = [-np.inf, -1.5, -1.0, -0.5, 0, 0.5, 1.0, 1.5, 2.0, 3.0, 5.0, np.inf]
    labels = ["< -1.5R", "-1.5 a -1R", "-1 a -0.5R", "-0.5 a 0R", "0 a 0.5R",
              "0.5 a 1R", "1 a 1.5R", "1.5 a 2R", "2 a 3R", "3 a 5R", "> 5R"]
    cats = pd.cut(r, bins=bins, labels=labels)
    counts = cats.value_counts().sort_index()
    pct = (counts / len(r) * 100).round(1)

    return pd.DataFrame({"bucket": counts.index.astype(str), "n": counts.values, "pct": pct.values})


# ── Rolling metrics ────────────────────────────────────────────────────────
def rolling_metrics(realized_r: pd.Series, window: int = 30) -> pd.DataFrame:
    r = realized_r.dropna().reset_index(drop=True)
    if len(r) < window:
        return pd.DataFrame()

    rolling = pd.DataFrame({
        "trade_n":      range(window, len(r) + 1),
        "rolling_mean": r.rolling(window).mean().dropna().values,
        "rolling_std":  r.rolling(window).std().dropna().values,
    })
    # Sharpe-equivalente para R (no anualizado)
    rolling["rolling_sharpe"] = (rolling["rolling_mean"] / rolling["rolling_std"]).round(3)
    rolling = rolling.round(3)
    return rolling


# ── Time exposure ──────────────────────────────────────────────────────────
def time_exposure_stats(df: pd.DataFrame) -> dict:
    if "bars_open" not in df.columns:
        return {}

    bars = pd.to_numeric(df["bars_open"], errors="coerce").dropna()
    if bars.empty:
        return {}

    total_bars = float(bars.sum())
    avg_bars = float(bars.mean())
    n_trades = len(bars)
    # Asumimos 252 dias de trading por año
    days_total = (df["closed_dt"].max() - df["closed_dt"].min()).days
    if days_total == 0:
        return {"n_trades": n_trades, "avg_bars_per_trade": round(avg_bars, 2)}

    # Time in market estimado (asumiendo 1 trade a la vez)
    time_in_market_pct = (total_bars / max(days_total, 1)) * 100

    return {
        "n_trades":            n_trades,
        "total_days":          days_total,
        "avg_bars_per_trade":  round(avg_bars, 2),
        "median_bars":         round(float(bars.median()), 2),
        "max_bars":            int(bars.max()),
        "time_in_market_pct":  round(min(time_in_market_pct, 100.0), 2),
    }


# ── Reporte ─────────────────────────────────────────────────────────────────
def write_report(settings: Settings, df: pd.DataFrame, realized_r: pd.Series,
                 equity_df: pd.DataFrame, mc_df: pd.DataFrame,
                 dist_summary: dict, dist_buckets: pd.DataFrame,
                 rolling_df: pd.DataFrame, exposure: dict,
                 realized_r_with_costs: pd.Series) -> Path:
    settings.outdir.mkdir(parents=True, exist_ok=True)
    report_path = settings.outdir / "advanced_report.md"

    lines = []
    lines.append("# Advanced Analytics Report")
    lines.append("")
    lines.append(f"- Archivo: `{settings.input_path}`")
    lines.append(f"- Trades cerrados: **{len(df)}**")
    lines.append(f"- Capital inicial: **${settings.initial_capital:,.0f}**")
    lines.append(f"- Riesgo por trade: **{settings.risk_per_trade_pct}%**")
    lines.append(f"- Comision: **${settings.commission_per_trade}** | Slippage: **{settings.slippage_pct}%** por lado")
    lines.append("")

    # Equity curve summary
    if not equity_df.empty:
        final_cap = equity_df["capital"].iloc[-1]
        max_dd_pct = equity_df["drawdown_pct"].min()
        days_in_dd = int(equity_df["in_drawdown"].sum())
        lines.append("## Equity Curve (con compounding)")
        lines.append("")
        lines.append(f"- Capital final: **${final_cap:,.2f}**")
        lines.append(f"- Retorno total: **{(final_cap / settings.initial_capital - 1) * 100:+.2f}%**")
        lines.append(f"- Max drawdown: **{max_dd_pct:.2f}%**")
        lines.append(f"- Trades en drawdown: **{days_in_dd}/{len(equity_df)} ({days_in_dd / len(equity_df) * 100:.1f}%)**")
        lines.append("")

    # Distribucion
    if dist_summary:
        lines.append("## Distribucion de R (sin costos)")
        lines.append("")
        for k, v in dist_summary.items():
            lines.append(f"- **{k}**: {v}")
        lines.append("")

    # Costos
    cost_summary = distribution_summary(realized_r_with_costs)
    if cost_summary:
        lines.append("## Distribucion de R (con costos)")
        lines.append("")
        lines.append(f"- Expectancy original: **{dist_summary.get('expectancy')}R**")
        lines.append(f"- Expectancy con costos: **{cost_summary.get('expectancy')}R**")
        lines.append(f"- Degradacion por costos: **{(cost_summary.get('expectancy', 0) - dist_summary.get('expectancy', 0)):.3f}R/trade**")
        lines.append("")

    # Distribution buckets
    if not dist_buckets.empty:
        lines.append("## Distribucion por bucket de R")
        lines.append("")
        lines.append(dist_buckets.to_markdown(index=False))
        lines.append("")

    # Monte Carlo
    if not mc_df.empty:
        lines.append(f"## Monte Carlo ({len(mc_df)} simulaciones)")
        lines.append("")
        lines.append(f"- Capital final mediano: **${mc_df['final_capital'].median():,.2f}**")
        lines.append(f"- Capital final p05 (peor 5%): **${mc_df['final_capital'].quantile(0.05):,.2f}**")
        lines.append(f"- Capital final p95 (mejor 5%): **${mc_df['final_capital'].quantile(0.95):,.2f}**")
        lines.append(f"- Drawdown mediano: **{mc_df['max_drawdown_pct'].median():.2f}%**")
        lines.append(f"- Drawdown p95 (peor caso): **{mc_df['max_drawdown_pct'].quantile(0.05):.2f}%**")
        lines.append(f"- Mediana de prob. de ganar dinero: **{(mc_df['total_return_pct'] > 0).mean() * 100:.1f}%**")
        lines.append(f"- Max losses consecutivas (p95): **{int(mc_df['max_consec_losses'].quantile(0.95))}**")
        lines.append(f"- Max losses consecutivas peor caso: **{int(mc_df['max_consec_losses'].max())}**")
        lines.append("")

    # Rolling
    if not rolling_df.empty:
        lines.append(f"## Rolling Metrics (ventana={settings.rolling_window_trades} trades)")
        lines.append("")
        lines.append(f"- Sharpe rolling promedio: **{rolling_df['rolling_sharpe'].mean():.3f}**")
        lines.append(f"- Sharpe rolling min: **{rolling_df['rolling_sharpe'].min():.3f}**")
        lines.append(f"- Sharpe rolling max: **{rolling_df['rolling_sharpe'].max():.3f}**")
        # ¿el edge es estable?
        first_half = rolling_df.iloc[:len(rolling_df) // 2]["rolling_mean"].mean()
        second_half = rolling_df.iloc[len(rolling_df) // 2:]["rolling_mean"].mean()
        lines.append(f"- Mean R primera mitad: **{first_half:.3f}R**")
        lines.append(f"- Mean R segunda mitad: **{second_half:.3f}R**")
        lines.append(f"- Edge degradation: **{second_half - first_half:+.3f}R**")
        lines.append("")

    # Exposure
    if exposure:
        lines.append("## Time Exposure")
        lines.append("")
        for k, v in exposure.items():
            lines.append(f"- **{k}**: {v}")
        lines.append("")

    # Veredicto
    lines.append("## Veredicto cuantitativo")
    lines.append("")
    expectancy = dist_summary.get("expectancy", 0)
    cost_expectancy = cost_summary.get("expectancy", 0) if cost_summary else 0
    if cost_expectancy <= 0:
        lines.append("⛔ **Sistema NO rentable con costos reales**")
    elif cost_expectancy < 0.05:
        lines.append("⚠️ **Sistema marginalmente rentable** — el edge es muy delgado para sostener slippage real")
    elif cost_expectancy < 0.15:
        lines.append("🟡 **Sistema con edge real pero modesto** — necesita disciplina extrema")
    else:
        lines.append("✅ **Sistema con edge robusto** — preserva expectancy bajo costos")

    lines.append("")

    # Comparacion edge primera vs segunda mitad
    if not rolling_df.empty:
        deg = second_half - first_half
        if deg < -0.1:
            lines.append("⚠️ **Edge degradandose** — segunda mitad rinde menos que la primera (posible overfitting)")
        elif deg > 0.1:
            lines.append("✅ **Edge fortaleciendose** — segunda mitad rinde mas que la primera")
        else:
            lines.append("🟢 **Edge estable** — sin degradacion notable entre periodos")

    report_path.write_text("\n".join(lines), encoding="utf-8")
    return report_path


# ── CLI ─────────────────────────────────────────────────────────────────────
def parse_args() -> Settings:
    p = argparse.ArgumentParser(description="Stock Sentinel — Advanced Analytics")
    p.add_argument("--input", required=True, help="Ruta a CSV (alerts_history o backtest_trades)")
    p.add_argument("--outdir", default="analytics_output")
    p.add_argument("--capital", type=float, default=10000.0)
    p.add_argument("--risk-pct", type=float, default=1.0)
    p.add_argument("--commission", type=float, default=1.0)
    p.add_argument("--slippage-pct", type=float, default=0.05)
    p.add_argument("--mc-runs", type=int, default=1000)
    p.add_argument("--rolling-window", type=int, default=30)
    p.add_argument("--filter-playbook", type=str, default="",
                   help="Filtrar por playbook: 'breakout', 'pullback', 'hybrid', o vacio (todos)")
    args = p.parse_args()

    return Settings(
        input_path=Path(args.input),
        outdir=Path(args.outdir),
        initial_capital=args.capital,
        risk_per_trade_pct=args.risk_pct,
        commission_per_trade=args.commission,
        slippage_pct=args.slippage_pct,
        mc_runs=args.mc_runs,
        rolling_window_trades=args.rolling_window,
        filter_playbook=args.filter_playbook.strip().lower(),
    )


def main() -> None:
    settings = parse_args()
    settings.outdir.mkdir(parents=True, exist_ok=True)

    df = load_trades(settings.input_path)
    if df.empty:
        log.warning("Sin trades cerrados — no se puede analizar")
        return

    # Filtro por playbook (Fase B)
    if settings.filter_playbook:
        if "playbook" not in df.columns:
            log.warning("Columna 'playbook' no encontrada — filtro ignorado")
        else:
            before = len(df)
            df = df[df["playbook"].astype(str).str.strip().str.lower() == settings.filter_playbook].copy()
            df = df.reset_index(drop=True)
            log.info("Filtro playbook='%s': %s/%s trades", settings.filter_playbook, len(df), before)
            if df.empty:
                log.warning("Sin trades para playbook='%s'", settings.filter_playbook)
                return

    realized_r = compute_realized_r(df)
    realized_r_with_costs = apply_costs(realized_r, df, settings)

    log.info("Generando equity curve...")
    equity_df = build_equity_curve(df, realized_r, settings)
    equity_df.to_csv(settings.outdir / "equity_curve.csv", index=False)

    log.info("Generando equity curve con costos...")
    equity_df_costs = build_equity_curve(df, realized_r_with_costs, settings)
    equity_df_costs.to_csv(settings.outdir / "equity_curve_with_costs.csv", index=False)

    log.info("Distribucion de R...")
    dist_summary = distribution_summary(realized_r)
    dist_buckets = distribution_buckets(realized_r)
    dist_buckets.to_csv(settings.outdir / "distribution_r.csv", index=False)

    log.info("Monte Carlo (%s simulaciones)...", settings.mc_runs)
    mc_df = monte_carlo_reorder(realized_r, settings, n_runs=settings.mc_runs)
    mc_df.to_csv(settings.outdir / "monte_carlo.csv", index=False)

    log.info("Rolling metrics (ventana=%s trades)...", settings.rolling_window_trades)
    rolling_df = rolling_metrics(realized_r, window=settings.rolling_window_trades)
    rolling_df.to_csv(settings.outdir / "rolling_metrics.csv", index=False)

    log.info("Time exposure...")
    exposure = time_exposure_stats(df)

    log.info("Generando reporte final...")
    report_path = write_report(
        settings, df, realized_r, equity_df, mc_df,
        dist_summary, dist_buckets, rolling_df, exposure, realized_r_with_costs,
    )

    # Resumen consola
    print(f"\n{'='*60}")
    print(f"ADVANCED ANALYTICS COMPLETO")
    print(f"{'='*60}")
    print(f"Trades analizados : {len(df)}")
    print(f"Expectancy        : {dist_summary.get('expectancy', 'n/a')}R/trade (sin costos)")
    print(f"Expectancy real   : {distribution_summary(realized_r_with_costs).get('expectancy', 'n/a')}R/trade (con costos)")
    if not equity_df.empty:
        print(f"Capital final     : ${equity_df['capital'].iloc[-1]:,.2f}")
        print(f"Max drawdown      : {equity_df['drawdown_pct'].min():.2f}%")
    if not mc_df.empty:
        print(f"MC P(profit) >0   : {(mc_df['total_return_pct'] > 0).mean() * 100:.1f}%")
        print(f"MC peor drawdown  : {mc_df['max_drawdown_pct'].quantile(0.05):.2f}%")
    print(f"\nReporte: {report_path}")
    print(f"Outputs en: {settings.outdir}/")


if __name__ == "__main__":
    main()
