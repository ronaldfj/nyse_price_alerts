"""
Stock Sentinel — Comparacion de Playbooks (Fase B)
====================================================
Corre advanced_analytics sobre breakout, pullback y all combinados,
luego genera un reporte comparativo head-to-head.

Output:
  - playbook_comparison.md   tabla comparativa
  - playbook_comparison.csv  metricas en CSV
  - analytics_breakout/      analytics completo de breakouts
  - analytics_pullback/      analytics completo de pullbacks
  - analytics_all/           analytics completo (baseline)

Uso:
  python compare_playbooks.py --input backtest_output/backtest_trades.csv
  python compare_playbooks.py --input alerts_history.csv --capital 10000
"""

from __future__ import annotations

import argparse
import logging
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

# Reusar funciones de advanced_analytics
import sys
sys.path.insert(0, str(Path(__file__).parent))
from advanced_analytics import (
    load_trades, compute_realized_r, apply_costs, build_equity_curve,
    monte_carlo_reorder, distribution_summary, distribution_buckets,
    rolling_metrics, time_exposure_stats, Settings,
)


logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s", datefmt="%H:%M:%S")
log = logging.getLogger("compare_playbooks")


def analyze_subset(df: pd.DataFrame, label: str, settings: Settings, outdir: Path) -> dict:
    """Corre analytics completo sobre un subset y devuelve metricas resumen."""
    if df.empty:
        return {"playbook": label, "n": 0}

    realized_r = compute_realized_r(df).dropna()
    realized_r_costs = apply_costs(compute_realized_r(df), df, settings).dropna()

    if len(realized_r) == 0:
        return {"playbook": label, "n": 0}

    # Equity con compounding
    equity_df = build_equity_curve(df.reset_index(drop=True), realized_r, settings)
    final_cap = float(equity_df["capital"].iloc[-1]) if not equity_df.empty else settings.initial_capital
    max_dd = float(equity_df["drawdown_pct"].min()) if not equity_df.empty else 0.0

    # MC bootstrap
    mc_df = monte_carlo_reorder(realized_r, settings, n_runs=settings.mc_runs)

    # Distribucion
    dist = distribution_summary(realized_r)
    dist_costs = distribution_summary(realized_r_costs)

    # Rolling
    rolling = rolling_metrics(realized_r, window=min(settings.rolling_window_trades, max(10, len(realized_r) // 4)))
    rolling_sharpe = float(rolling["rolling_sharpe"].mean()) if not rolling.empty else float("nan")

    # Edge degradation
    edge_deg = float("nan")
    if not rolling.empty and len(rolling) >= 4:
        first_half  = float(rolling.iloc[:len(rolling) // 2]["rolling_mean"].mean())
        second_half = float(rolling.iloc[len(rolling) // 2:]["rolling_mean"].mean())
        edge_deg = round(second_half - first_half, 3)

    # Guardar outputs detallados
    outdir.mkdir(parents=True, exist_ok=True)
    equity_df.to_csv(outdir / "equity_curve.csv", index=False)
    if not mc_df.empty:
        mc_df.to_csv(outdir / "monte_carlo.csv", index=False)

    metrics = {
        "playbook":              label,
        "n":                     len(df),
        "win_rate_pct":          dist.get("win_rate_pct", 0),
        "expectancy":            dist.get("expectancy", 0),
        "expectancy_with_costs": dist_costs.get("expectancy", 0),
        "median_r":              dist.get("median", 0),
        "std_r":                 dist.get("std", 0),
        "skew":                  dist.get("skew", 0),
        "max_r":                 dist.get("max", 0),
        "min_r":                 dist.get("min", 0),
        "p95_r":                 dist.get("q95", 0),
        "p05_r":                 dist.get("q05", 0),
        "final_capital":         round(final_cap, 2),
        "total_return_pct":      round((final_cap / settings.initial_capital - 1) * 100, 2),
        "max_drawdown_pct":      round(max_dd, 2),
        "mc_median_capital":     round(float(mc_df["final_capital"].median()), 2) if not mc_df.empty else 0,
        "mc_p05_capital":        round(float(mc_df["final_capital"].quantile(0.05)), 2) if not mc_df.empty else 0,
        "mc_p95_capital":        round(float(mc_df["final_capital"].quantile(0.95)), 2) if not mc_df.empty else 0,
        "mc_median_drawdown":    round(float(mc_df["max_drawdown_pct"].median()), 2) if not mc_df.empty else 0,
        "mc_worst_drawdown":     round(float(mc_df["max_drawdown_pct"].quantile(0.05)), 2) if not mc_df.empty else 0,
        "mc_prob_profit_pct":    round(float((mc_df["total_return_pct"] > 0).mean() * 100), 2) if not mc_df.empty else 0,
        "mc_max_consec_losses_p95": int(mc_df["max_consec_losses"].quantile(0.95)) if not mc_df.empty else 0,
        "rolling_sharpe_avg":    round(rolling_sharpe, 3) if not np.isnan(rolling_sharpe) else 0,
        "edge_degradation":      edge_deg if not np.isnan(edge_deg) else 0,
    }

    return metrics


def write_comparison_report(results: list[dict], outdir: Path, settings: Settings) -> Path:
    df_comp = pd.DataFrame(results)
    df_comp.to_csv(outdir / "playbook_comparison.csv", index=False)

    md_path = outdir / "playbook_comparison.md"
    lines = []
    lines.append("# Comparacion de Playbooks — Fase B")
    lines.append("")
    lines.append(f"- Capital inicial: **${settings.initial_capital:,.0f}**")
    lines.append(f"- Riesgo por trade: **{settings.risk_per_trade_pct}%**")
    lines.append(f"- Costos: comision **${settings.commission_per_trade}** + slippage **{settings.slippage_pct}%/lado**")
    lines.append(f"- Monte Carlo: **{settings.mc_runs}** runs (bootstrap)")
    lines.append("")

    # Tabla comparativa principal
    lines.append("## Comparacion head-to-head")
    lines.append("")
    key_metrics = [
        "playbook", "n", "win_rate_pct", "expectancy", "expectancy_with_costs",
        "max_drawdown_pct", "mc_worst_drawdown", "mc_prob_profit_pct",
        "rolling_sharpe_avg", "edge_degradation",
    ]
    lines.append(df_comp[key_metrics].to_markdown(index=False))
    lines.append("")

    # Distribucion
    lines.append("## Distribucion de R")
    lines.append("")
    dist_cols = ["playbook", "n", "median_r", "std_r", "skew", "min_r", "p05_r", "p95_r", "max_r"]
    lines.append(df_comp[dist_cols].to_markdown(index=False))
    lines.append("")

    # Equity y MC
    lines.append("## Equity Curve + Monte Carlo")
    lines.append("")
    eq_cols = ["playbook", "final_capital", "total_return_pct",
               "mc_median_capital", "mc_p05_capital", "mc_p95_capital",
               "mc_median_drawdown", "mc_max_consec_losses_p95"]
    lines.append(df_comp[eq_cols].to_markdown(index=False))
    lines.append("")

    # Veredicto comparativo
    lines.append("## Veredicto comparativo")
    lines.append("")

    # Filter only real playbooks (skip 'all' and 0-trade rows)
    df_real = df_comp[(df_comp["playbook"].isin(["breakout", "pullback", "hybrid"])) & (df_comp["n"] > 0)].copy()
    if len(df_real) >= 2:
        best_exp     = df_real.loc[df_real["expectancy_with_costs"].idxmax()]
        best_sharpe  = df_real.loc[df_real["rolling_sharpe_avg"].idxmax()]
        worst_dd     = df_real.loc[df_real["max_drawdown_pct"].idxmax()]  # menos negativo = mejor

        lines.append(f"- **Mejor expectancy con costos**: `{best_exp['playbook']}` ({best_exp['expectancy_with_costs']:.3f}R, n={int(best_exp['n'])})")
        lines.append(f"- **Mejor Sharpe rolling**: `{best_sharpe['playbook']}` ({best_sharpe['rolling_sharpe_avg']:.3f})")
        lines.append(f"- **Menor drawdown**: `{worst_dd['playbook']}` ({worst_dd['max_drawdown_pct']:.2f}%)")
        lines.append("")

        # Recomendacion
        for _, row in df_real.iterrows():
            pb = row["playbook"]
            exp = row["expectancy_with_costs"]
            sharpe = row["rolling_sharpe_avg"]
            edge_deg = row["edge_degradation"]

            verdict = []
            if exp <= 0:
                verdict.append("⛔ NO rentable con costos")
            elif exp < 0.10:
                verdict.append("⚠️ marginalmente rentable")
            elif exp < 0.20:
                verdict.append("🟡 edge modesto")
            else:
                verdict.append("✅ edge robusto")

            if edge_deg < -0.10:
                verdict.append("⚠️ edge degradandose")
            elif abs(edge_deg) <= 0.05:
                verdict.append("🟢 edge estable")

            lines.append(f"### {pb}")
            lines.append(f"- {' | '.join(verdict)}")
            lines.append(f"- Expectancy con costos: **{exp:.3f}R**")
            lines.append(f"- Sharpe rolling: **{sharpe:.3f}**")
            lines.append(f"- Trades: **{int(row['n'])}**")
            lines.append(f"- Max losses consecutivas (MC p95): **{int(row['mc_max_consec_losses_p95'])}**")
            lines.append("")

    md_path.write_text("\n".join(lines), encoding="utf-8")
    return md_path


def parse_args() -> Settings:
    p = argparse.ArgumentParser(description="Comparacion de Playbooks — Fase B")
    p.add_argument("--input", required=True)
    p.add_argument("--outdir", default="playbook_comparison_output")
    p.add_argument("--capital", type=float, default=10000.0)
    p.add_argument("--risk-pct", type=float, default=1.0)
    p.add_argument("--commission", type=float, default=1.0)
    p.add_argument("--slippage-pct", type=float, default=0.05)
    p.add_argument("--mc-runs", type=int, default=2000)
    p.add_argument("--rolling-window", type=int, default=30)
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
    )


def main() -> None:
    settings = parse_args()
    settings.outdir.mkdir(parents=True, exist_ok=True)

    log.info("Cargando trades...")
    df_all = load_trades(settings.input_path)
    if df_all.empty:
        log.error("Sin trades para analizar")
        return

    if "playbook" not in df_all.columns:
        log.error("Columna 'playbook' no encontrada en CSV — no se puede comparar")
        return

    df_all["playbook_norm"] = df_all["playbook"].astype(str).str.strip().str.lower()

    log.info("Distribucion de playbooks: %s", df_all["playbook_norm"].value_counts().to_dict())

    results = []
    for label in ["all", "breakout", "pullback", "hybrid"]:
        if label == "all":
            subset = df_all
        else:
            subset = df_all[df_all["playbook_norm"] == label].copy()

        log.info("Analizando '%s' (%s trades)...", label, len(subset))
        sub_outdir = settings.outdir / f"analytics_{label}"
        metrics = analyze_subset(subset, label, settings, sub_outdir)
        results.append(metrics)

    log.info("Generando reporte comparativo...")
    report_path = write_comparison_report(results, settings.outdir, settings)

    # Console summary
    df_comp = pd.DataFrame(results)
    df_real = df_comp[df_comp["playbook"].isin(["breakout", "pullback", "hybrid"]) & (df_comp["n"] > 0)]

    print(f"\n{'='*70}")
    print(f"COMPARACION DE PLAYBOOKS — FASE B")
    print(f"{'='*70}")
    cols_print = ["playbook", "n", "win_rate_pct", "expectancy_with_costs",
                  "max_drawdown_pct", "rolling_sharpe_avg", "edge_degradation"]
    print(df_comp[cols_print].to_string(index=False))

    if not df_real.empty:
        best = df_real.loc[df_real["expectancy_with_costs"].idxmax()]
        print(f"\n→ Mejor playbook por expectancy con costos: {best['playbook']} ({best['expectancy_with_costs']:.3f}R, n={int(best['n'])})")

    print(f"\nReporte: {report_path}")
    print(f"Outputs en: {settings.outdir}/")


if __name__ == "__main__":
    main()
