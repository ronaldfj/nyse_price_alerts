
#!/usr/bin/env python3
"""
Analyze alerts_history.csv from Stock Sentinel / RGTNYSE Bot.

Outputs:
- console summary
- performance_report.md
- optional CSV tables in ./analysis_output

Usage:
    python analyze_alerts_history.py --input alerts_history.csv
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd


DEFAULT_INPUT = "alerts_history.csv"
DEFAULT_OUTDIR = "analysis_output"


@dataclass
class Settings:
    input_path: Path
    outdir: Path
    min_closed: int = 10


NUMERIC_COLS = [
    "price", "target", "stop", "rr", "score", "regime_score", "setup_score", "trigger_score",
    "atr", "adx", "rsi", "rs20", "extension_pct", "vix", "bars_open", "days_open",
    "current_price", "pnl_pct", "mfe_pct", "mae_pct", "exit_price",
]

DATE_COLS = ["timestamp_utc", "last_checked_utc", "closed_utc", "exit_date"]


def load_history(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(f"No existe el archivo: {path}")

    df = pd.read_csv(path)
    if df.empty:
        raise ValueError(f"El archivo está vacío: {path}")

    for col in DATE_COLS:
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], utc=True, errors="coerce")

    for col in NUMERIC_COLS:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    if "status" in df.columns:
        df["status"] = df["status"].fillna("open").astype(str).str.strip().str.lower()
    else:
        df["status"] = "open"

    if "playbook" not in df.columns:
        df["playbook"] = "unknown"
    df["playbook"] = df["playbook"].fillna("unknown").astype(str).str.strip().str.lower()

    if "symbol" not in df.columns:
        df["symbol"] = "UNKNOWN"

    if "group" not in df.columns:
        df["group"] = "Unknown"

    return df


def add_derived_columns(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()

    out["risk_dollars"] = (out["price"] - out["stop"]).astype(float)
    out["reward_dollars"] = (out["target"] - out["price"]).astype(float)
    out["risk_pct_entry"] = np.where(
        out["price"] > 0, (out["risk_dollars"] / out["price"]) * 100.0, np.nan
    )

    # Realized exit price fallback hierarchy
    exit_px = out["exit_price"]
    if "current_price" in out.columns:
        exit_px = exit_px.fillna(out["current_price"])
    out["resolved_exit_price"] = exit_px

    out["realized_r"] = np.where(
        out["risk_dollars"] > 0,
        (out["resolved_exit_price"] - out["price"]) / out["risk_dollars"],
        np.nan,
    )

    # Override realized_r for canonical statuses
    out.loc[out["status"] == "hit_stop", "realized_r"] = -1.0
    out.loc[out["status"] == "hit_target", "realized_r"] = out.loc[out["status"] == "hit_target", "rr"]

    # Categoricals for analysis
    out["score_bucket"] = pd.cut(
        out["score"],
        bins=[-np.inf, 5.79, 6.49, 7.49, 8.49, np.inf],
        labels=["<5.8", "5.8-6.49", "6.5-7.49", "7.5-8.49", "8.5+"],
    )

    out["rs_bucket"] = pd.cut(
        out["rs20"],
        bins=[-np.inf, 0, 2, 5, np.inf],
        labels=["<0", "0-2", "2-5", "5+"],
    )

    out["extension_bucket"] = pd.cut(
        out["extension_pct"],
        bins=[-np.inf, 5, 10, 15, np.inf],
        labels=["<5", "5-10", "10-15", "15+"],
    )

    out["rr_bucket"] = pd.cut(
        out["rr"],
        bins=[-np.inf, 1.0, 1.5, 2.5, 4.0, np.inf],
        labels=["<1.0", "1.0-1.5", "1.5-2.5", "2.5-4.0", "4.0+"],
    )

    return out


def closed_only(df: pd.DataFrame) -> pd.DataFrame:
    return df[df["status"].isin(["hit_target", "hit_stop", "expired"])].copy()


def safe_mean(s: pd.Series) -> float:
    s = pd.to_numeric(s, errors="coerce").dropna()
    return float(s.mean()) if not s.empty else np.nan


def safe_median(s: pd.Series) -> float:
    s = pd.to_numeric(s, errors="coerce").dropna()
    return float(s.median()) if not s.empty else np.nan


def expectation_table(df: pd.DataFrame, by: str) -> pd.DataFrame:
    if df.empty or by not in df.columns:
        return pd.DataFrame()

    grouped = []
    for key, g in df.groupby(by, dropna=False):
        n = len(g)
        wins = g["status"].eq("hit_target").sum()
        stops = g["status"].eq("hit_stop").sum()
        expired = g["status"].eq("expired").sum()
        win_rate = wins / n if n else np.nan
        stop_rate = stops / n if n else np.nan
        expired_rate = expired / n if n else np.nan
        avg_r = safe_mean(g["realized_r"])
        med_r = safe_median(g["realized_r"])
        avg_rr = safe_mean(g["rr"])
        avg_days = safe_mean(g["days_open"])
        avg_score = safe_mean(g["score"])
        avg_rs20 = safe_mean(g["rs20"])
        avg_mfe = safe_mean(g["mfe_pct"])
        avg_mae = safe_mean(g["mae_pct"])
        grouped.append(
            {
                by: str(key),
                "n": int(n),
                "win_rate": round(win_rate * 100, 2),
                "stop_rate": round(stop_rate * 100, 2),
                "expired_rate": round(expired_rate * 100, 2),
                "avg_realized_r": round(avg_r, 3) if pd.notna(avg_r) else np.nan,
                "median_realized_r": round(med_r, 3) if pd.notna(med_r) else np.nan,
                "avg_rr": round(avg_rr, 2) if pd.notna(avg_rr) else np.nan,
                "avg_days_open": round(avg_days, 2) if pd.notna(avg_days) else np.nan,
                "avg_score": round(avg_score, 2) if pd.notna(avg_score) else np.nan,
                "avg_rs20": round(avg_rs20, 2) if pd.notna(avg_rs20) else np.nan,
                "avg_mfe_pct": round(avg_mfe, 2) if pd.notna(avg_mfe) else np.nan,
                "avg_mae_pct": round(avg_mae, 2) if pd.notna(avg_mae) else np.nan,
            }
        )

    res = pd.DataFrame(grouped)
    if not res.empty and "avg_realized_r" in res.columns:
        res = res.sort_values(["avg_realized_r", "win_rate", "n"], ascending=[False, False, False])
    return res


def overall_metrics(df: pd.DataFrame) -> dict:
    n = len(df)
    wins = int(df["status"].eq("hit_target").sum())
    stops = int(df["status"].eq("hit_stop").sum())
    expired = int(df["status"].eq("expired").sum())
    avg_r = safe_mean(df["realized_r"])
    med_r = safe_median(df["realized_r"])
    win_rate = wins / n if n else np.nan
    stop_rate = stops / n if n else np.nan
    expired_rate = expired / n if n else np.nan
    avg_rr = safe_mean(df["rr"])
    avg_score = safe_mean(df["score"])
    avg_days = safe_mean(df["days_open"])
    avg_mfe = safe_mean(df["mfe_pct"])
    avg_mae = safe_mean(df["mae_pct"])

    return {
        "closed_trades": n,
        "wins": wins,
        "stops": stops,
        "expired": expired,
        "win_rate_pct": round(win_rate * 100, 2) if pd.notna(win_rate) else np.nan,
        "stop_rate_pct": round(stop_rate * 100, 2) if pd.notna(stop_rate) else np.nan,
        "expired_rate_pct": round(expired_rate * 100, 2) if pd.notna(expired_rate) else np.nan,
        "avg_realized_r": round(avg_r, 3) if pd.notna(avg_r) else np.nan,
        "median_realized_r": round(med_r, 3) if pd.notna(med_r) else np.nan,
        "avg_rr": round(avg_rr, 2) if pd.notna(avg_rr) else np.nan,
        "avg_score": round(avg_score, 2) if pd.notna(avg_score) else np.nan,
        "avg_days_open": round(avg_days, 2) if pd.notna(avg_days) else np.nan,
        "avg_mfe_pct": round(avg_mfe, 2) if pd.notna(avg_mfe) else np.nan,
        "avg_mae_pct": round(avg_mae, 2) if pd.notna(avg_mae) else np.nan,
    }


def suggestion_lines(df_closed: pd.DataFrame) -> list[str]:
    suggestions: list[str] = []

    if df_closed.empty:
        return ["No hay trades cerrados todavía; junta más muestra antes de recalibrar."]

    score_tbl = expectation_table(df_closed, "score_bucket")
    rs_tbl = expectation_table(df_closed, "rs_bucket")
    pb_tbl = expectation_table(df_closed, "playbook")
    ext_tbl = expectation_table(df_closed, "extension_bucket")

    # Score threshold suggestion
    if not score_tbl.empty:
        candidates = score_tbl[score_tbl["n"] >= 5].sort_values("avg_realized_r", ascending=False)
        if not candidates.empty:
            best = candidates.iloc[0]
            suggestions.append(
                f"Score: el bucket más sólido es {best['score_bucket']} "
                f"(n={int(best['n'])}, avg_R={best['avg_realized_r']}). "
                f"Úsalo como referencia para revisar MIN_SCORE."
            )

    # RS threshold suggestion
    if not rs_tbl.empty and len(rs_tbl) >= 2:
        neg = rs_tbl[rs_tbl["rs_bucket"] == "<0"]
        pos = rs_tbl[rs_tbl["rs_bucket"].isin(["0-2", "2-5", "5+"])]
        if not neg.empty and not pos.empty:
            neg_r = safe_mean(neg["avg_realized_r"])
            pos_r = safe_mean(pos["avg_realized_r"])
            if pd.notna(neg_r) and pd.notna(pos_r) and pos_r > neg_r:
                suggestions.append(
                    f"RS20: los trades con RS no negativa rinden mejor que los de RS<0 "
                    f"({round(pos_r,3)}R vs {round(neg_r,3)}R promedio por bucket). "
                    f"Eso apoya endurecer FINAL_RS_MIN."
                )

    # Playbook suggestion
    if not pb_tbl.empty:
        viable = pb_tbl[pb_tbl["n"] >= 5].sort_values("avg_realized_r", ascending=False)
        if not viable.empty:
            top = viable.iloc[0]
            worst = viable.iloc[-1]
            suggestions.append(
                f"Playbook: {top['playbook']} lidera en avg_R={top['avg_realized_r']} "
                f"(n={int(top['n'])})."
            )
            if top["playbook"] != worst["playbook"] and pd.notna(worst["avg_realized_r"]):
                suggestions.append(
                    f"Playbook débil: {worst['playbook']} muestra avg_R={worst['avg_realized_r']} "
                    f"(n={int(worst['n'])}); revisa si conviene endurecerlo o pausarlo."
                )

    # Extension suggestion
    if not ext_tbl.empty:
        ext_viable = ext_tbl[ext_tbl["n"] >= 5].sort_values("avg_realized_r", ascending=False)
        if not ext_viable.empty:
            top_ext = ext_viable.iloc[0]
            bot_ext = ext_viable.iloc[-1]
            if top_ext["extension_bucket"] != bot_ext["extension_bucket"]:
                suggestions.append(
                    f"Extensión: mejor bucket {top_ext['extension_bucket']} "
                    f"(avg_R={top_ext['avg_realized_r']}, n={int(top_ext['n'])}); "
                    f"peor bucket {bot_ext['extension_bucket']} "
                    f"(avg_R={bot_ext['avg_realized_r']}, n={int(bot_ext['n'])}). "
                    f"Úsalo para calibrar BREAKOUT_MAX_ATR / tolerancia a sobreextensión."
                )

    # Expiry suggestion
    exp_rate = (df_closed["status"] == "expired").mean()
    if exp_rate >= 0.35:
        med_days = safe_median(df_closed.loc[df_closed["status"] == "expired", "days_open"])
        suggestions.append(
            f"Expiry alto: {round(exp_rate*100,2)}% de trades cerraron por expired. "
            f"Revisa TRACKER_MAX_BARS_OPEN y/o targets demasiado ambiciosos. "
            f"Mediana de días en expirados: {round(med_days,1) if pd.notna(med_days) else 'n/a'}."
        )

    # High RR inflation suggestion
    rr_high = df_closed[df_closed["rr"] >= 4]
    if len(rr_high) >= 5:
        rr_high_r = safe_mean(rr_high["realized_r"])
        all_r = safe_mean(df_closed["realized_r"])
        if pd.notna(rr_high_r) and pd.notna(all_r) and rr_high_r <= all_r:
            suggestions.append(
                f"RR alto no está mejorando resultados: trades con RR>=4 tienen avg_R={round(rr_high_r,3)} "
                f"vs avg global {round(all_r,3)}. Eso sugiere stop demasiado corto o target inflado."
            )

    if not suggestions:
        suggestions.append("Aún no hay diferencias claras por bucket; acumula más trades cerrados antes de mover parámetros.")

    return suggestions


def dataframe_to_markdown(df: pd.DataFrame, max_rows: int = 20) -> str:
    if df.empty:
        return "_sin datos_"
    slim = df.head(max_rows).copy()
    return slim.to_markdown(index=False)


def write_report(
    settings: Settings,
    raw_df: pd.DataFrame,
    df_closed: pd.DataFrame,
    overall: dict,
    tables: dict[str, pd.DataFrame],
    suggestions: list[str],
) -> Path:
    report_path = settings.outdir / "performance_report.md"
    settings.outdir.mkdir(parents=True, exist_ok=True)

    lines: list[str] = []
    lines.append("# Performance report — RGTNYSE / Stock Sentinel")
    lines.append("")
    lines.append(f"- Archivo analizado: `{settings.input_path}`")
    lines.append(f"- Alertas totales: **{len(raw_df)}**")
    lines.append(f"- Trades cerrados: **{len(df_closed)}**")
    lines.append(f"- Trades abiertos: **{int(raw_df['status'].eq('open').sum())}**")
    lines.append("")

    lines.append("## Resumen global")
    lines.append("")
    for k, v in overall.items():
        lines.append(f"- **{k}**: {v}")
    lines.append("")

    lines.append("## Sugerencias automáticas")
    lines.append("")
    for s in suggestions:
        lines.append(f"- {s}")
    lines.append("")

    for title, table in tables.items():
        lines.append(f"## {title}")
        lines.append("")
        lines.append(dataframe_to_markdown(table))
        lines.append("")

    report_path.write_text("\n".join(lines), encoding="utf-8")
    return report_path


def save_tables(outdir: Path, tables: dict[str, pd.DataFrame]) -> None:
    outdir.mkdir(parents=True, exist_ok=True)
    for name, table in tables.items():
        filename = name.lower().replace(" ", "_").replace("/", "_") + ".csv"
        table.to_csv(outdir / filename, index=False)


def print_console_summary(report_path: Path, overall: dict, suggestions: list[str]) -> None:
    print("\n=== RESUMEN GLOBAL ===")
    for k, v in overall.items():
        print(f"{k}: {v}")

    print("\n=== SUGERENCIAS ===")
    for s in suggestions:
        print(f"- {s}")

    print(f"\nReporte guardado en: {report_path}")


def parse_args() -> Settings:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", default=DEFAULT_INPUT, help="Ruta a alerts_history.csv")
    parser.add_argument("--outdir", default=DEFAULT_OUTDIR, help="Carpeta de salida")
    args = parser.parse_args()
    return Settings(input_path=Path(args.input), outdir=Path(args.outdir))


def main() -> None:
    settings = parse_args()
    raw_df = load_history(settings.input_path)
    df = add_derived_columns(raw_df)
    df_closed = closed_only(df)

    overall = overall_metrics(df_closed)
    tables = {
        "By playbook": expectation_table(df_closed, "playbook"),
        "By score bucket": expectation_table(df_closed, "score_bucket"),
        "By RS bucket": expectation_table(df_closed, "rs_bucket"),
        "By extension bucket": expectation_table(df_closed, "extension_bucket"),
        "By symbol": expectation_table(df_closed, "symbol"),
        "By group": expectation_table(df_closed, "group"),
        "By RR bucket": expectation_table(df_closed, "rr_bucket"),
    }
    suggestions = suggestion_lines(df_closed)

    save_tables(settings.outdir, tables)
    report_path = write_report(settings, df, df_closed, overall, tables, suggestions)
    print_console_summary(report_path, overall, suggestions)


if __name__ == "__main__":
    main()
