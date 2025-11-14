from __future__ import annotations

import json
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.append(str(PROJECT_ROOT))

from backend.app.analytics import build_time_series, compute_compstat
from backend.app.data_loader import CrimeDataRepository


def main() -> None:
    repo = CrimeDataRepository()
    df = repo.load(force=True)
    latest_date = df["occurred_ts"].max()

    compstat_overall = compute_compstat(df)
    compstat_category = compute_compstat(df, group_by="crime_category")
    hour_distribution = (
        df.groupby("hour_of_day").size().reset_index(name="count").sort_values("hour_of_day")
    )
    day_distribution = (
        df.groupby("day_of_week").size().reset_index(name="count").sort_values("count", ascending=False)
    )
    beats_distribution = (
        df.groupby("Beats").size().reset_index(name="count").sort_values("count", ascending=False)
    )
    recent_series = build_time_series(df, freq="D", periods=60).to_dict(orient="records")

    report_path = Path("analysis/eda_report.md")
    summary_path = Path("analysis/eda_summary.json")

    top_categories = df.groupby("crime_category").size().sort_values(ascending=False).head(10)
    peak_hour = (
        hour_distribution.loc[hour_distribution["count"].idxmax(), "hour_of_day"]
        if not hour_distribution.empty
        else None
    )

    report_lines = [
        "# Arlington East District Crime - Exploratory Analysis",
        "",
        f"- Total incidents: **{len(df):,}**",
        f"- Coverage: **{df['occurred_date'].min()} - {df['occurred_date'].max()}**",
        f"- Latest record timestamp: **{latest_date}**",
        "",
        "## CompStat Windows (overall)",
    ]
    for label, windows in compstat_overall.items():
        report_lines.append(f"### {label}")
        for entry in windows:
            period_change = (
                f"{entry['period_change'] * 100:.1f}% vs prior period"
                if entry["period_change"] is not None
                else "N/A"
            )
            yoy_change = (
                f"{entry['yoy_change'] * 100:.1f}% YoY"
                if entry["yoy_change"] is not None
                else "N/A"
            )
            report_lines.append(
                f"- {entry['window_days']}-day: {entry['current_count']:,} incidents | {period_change} | {yoy_change}"
            )
        report_lines.append("")

    report_lines.append("## Top crime categories")
    for category, count in top_categories.items():
        report_lines.append(f"- {category}: {int(count):,}")

    report_lines.append("")
    report_lines.append("## Temporal patterns")
    if peak_hour is not None:
        report_lines.append(
            f"- Hour-of-day intensity peaks at {int(peak_hour):02d}:00 with elevated evening activity."
        )

    report_path.write_text("\n".join(report_lines))

    summary_payload = {
        "compstat_overall": compstat_overall,
        "compstat_by_category": compstat_category,
        "hour_distribution": hour_distribution.to_dict(orient="records"),
        "day_distribution": day_distribution.to_dict(orient="records"),
        "beats_distribution": beats_distribution.to_dict(orient="records"),
        "recent_daily_counts": recent_series,
        "top_categories": top_categories.to_dict(),
    }
    summary_path.write_text(json.dumps(summary_payload, indent=2, default=str))


if __name__ == "__main__":
    main()
