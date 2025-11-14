from __future__ import annotations

from typing import Iterable, List

import pandas as pd
from pandas.api.types import CategoricalDtype

DAY_ORDER = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]


def _validate_column(df: pd.DataFrame, column: str) -> None:
    if column not in df.columns:
        raise KeyError(f"Column '{column}' not found in dataset")


def count_by(df: pd.DataFrame, dimension: str, limit: int | None = None) -> pd.DataFrame:
    _validate_column(df, dimension)
    grouped = df.groupby(dimension).size().reset_index(name="count")

    if dimension == "day_of_week":
        dtype = CategoricalDtype(categories=DAY_ORDER, ordered=True)
        grouped[dimension] = grouped[dimension].astype(dtype)
        grouped = grouped.sort_values(dimension)
    elif dimension in {"hour", "hour_of_day"}:
        grouped[dimension] = pd.to_numeric(grouped[dimension], errors="coerce").fillna(0).astype(int)
        grouped = grouped.sort_values(dimension)
    else:
        grouped = grouped.sort_values("count", ascending=False)

    if limit:
        grouped = grouped.head(limit)
    return grouped.reset_index(drop=True)


def heatmap(df: pd.DataFrame, dim_x: str, dim_y: str) -> pd.DataFrame:
    _validate_column(df, dim_x)
    _validate_column(df, dim_y)
    grouped = df.groupby([dim_x, dim_y]).size().reset_index(name="count")

    if dim_x == "day_of_week":
        grouped[dim_x] = grouped[dim_x].astype(CategoricalDtype(categories=DAY_ORDER, ordered=True))
    if dim_y == "day_of_week":
        grouped[dim_y] = grouped[dim_y].astype(CategoricalDtype(categories=DAY_ORDER, ordered=True))
    if dim_x in {"hour", "hour_of_day"}:
        grouped[dim_x] = pd.to_numeric(grouped[dim_x], errors="coerce").fillna(0).astype(int)
    if dim_y in {"hour", "hour_of_day"}:
        grouped[dim_y] = pd.to_numeric(grouped[dim_y], errors="coerce").fillna(0).astype(int)

    grouped = grouped.sort_values([dim_y, dim_x]).reset_index(drop=True)
    return grouped
