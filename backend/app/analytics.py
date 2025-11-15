from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import date, datetime, timedelta
from typing import Dict, Iterable, List, Optional

import pandas as pd

WINDOWS = (7, 28, 365)


@dataclass
class WindowComparison:
    label: str
    window_days: int
    start_date: date
    end_date: date
    current_count: int
    previous_period_count: int
    yoy_count: int

    @property
    def period_change(self) -> Optional[float]:
        if self.previous_period_count == 0:
            return None
        return (self.current_count - self.previous_period_count) / self.previous_period_count

    @property
    def yoy_change(self) -> Optional[float]:
        if self.yoy_count == 0:
            return None
        return (self.current_count - self.yoy_count) / self.yoy_count

    def as_dict(self) -> Dict[str, Optional[float]]:
        payload = asdict(self)
        payload["period_change"] = self.period_change
        payload["yoy_change"] = self.yoy_change
        return payload


def _filter_by_range(
    df: pd.DataFrame,
    start_date: date,
    end_date: date,
) -> pd.DataFrame:
    """Return rows between start/end dates (inclusive) using precomputed occurred_date."""
    if "occurred_date" not in df.columns:
        df = df.assign(occurred_date=df["occurred_ts"].dt.date)
    mask = (df["occurred_date"] >= start_date) & (df["occurred_date"] <= end_date)
    return df.loc[mask]


def compute_compstat(
    df: pd.DataFrame,
    windows: Iterable[int] = WINDOWS,
    as_of: Optional[datetime] = None,
    group_by: Optional[str] = None,
) -> Dict[str, List[Dict[str, Optional[float]]]]:
    if as_of is None:
        as_of = df["occurred_ts"].max()
    df = df[df["occurred_ts"] <= as_of]
    as_of_date = as_of.date()
    results: Dict[str, List[Dict[str, Optional[float]]]] = {}
    groups = [("All", df)]
    if group_by and group_by in df.columns:
        groups = [(str(name), group) for name, group in df.groupby(group_by)]

    for group_name, group_df in groups:
        group_results: List[Dict[str, Optional[float]]] = []
        for window in windows:
            window_days = max(window, 1)
            end_date = as_of_date
            start_date = as_of_date - timedelta(days=window_days - 1)
            current_df = _filter_by_range(group_df, start_date, end_date)

            previous_end = start_date - timedelta(days=1)
            previous_start = previous_end - timedelta(days=window_days - 1)
            previous_df = _filter_by_range(group_df, previous_start, previous_end)

            yoy_start = start_date - timedelta(days=365)
            yoy_end = end_date - timedelta(days=365)
            yoy_df = _filter_by_range(group_df, yoy_start, yoy_end)

            result = WindowComparison(
                label=group_name,
                window_days=window_days,
                start_date=start_date,
                end_date=end_date,
                current_count=int(current_df.shape[0]),
                previous_period_count=int(previous_df.shape[0]),
                yoy_count=int(yoy_df.shape[0]),
            )
            group_results.append(result.as_dict())
        results[group_name] = group_results
    return results


def build_time_series(
    df: pd.DataFrame,
    freq: str = "D",
    as_of: Optional[datetime] = None,
    periods: Optional[int] = None,
    group_by: Optional[str] = None,
) -> pd.DataFrame:
    if as_of is None:
        as_of = df["occurred_ts"].max()
    data = df[df["occurred_ts"] <= as_of].copy()
    if group_by and group_by in data.columns:
        grouped = (
            data.groupby([group_by, pd.Grouper(key="occurred_ts", freq=freq)])
            ["Case Number"]
            .count()
            .reset_index()
            .rename(columns={"Case Number": "count"})
        )
        if periods:
            grouped = (
                grouped.sort_values("occurred_ts")
                .groupby(group_by, group_keys=False)
                .tail(periods)
            )
        grouped["period"] = grouped["occurred_ts"].dt.strftime("%Y-%m-%d")
        grouped = grouped.drop(columns=["occurred_ts"])
        grouped = grouped.rename(columns={group_by: "group"})
        return grouped

    data.set_index("occurred_ts", inplace=True)
    series = data.resample(freq)["Case Number"].count().rename("count")
    if periods:
        series = series.iloc[-periods:]
    result = series.reset_index().rename(columns={"occurred_ts": "period"})
    result["period"] = result["period"].dt.strftime("%Y-%m-%d")
    return result

