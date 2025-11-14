from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Optional

import pandas as pd

from .config import settings


def _preprocess(df: pd.DataFrame) -> pd.DataFrame:
    processed = df.copy()
    processed.columns = [col.strip() for col in processed.columns]
    processed["occurred_ts"] = pd.to_datetime(
        processed["Date/Time Occurred"], errors="coerce", format="%m/%d/%Y %H:%M"
    )
    processed = processed.dropna(subset=["occurred_ts"])
    processed["occurred_date"] = processed["occurred_ts"].dt.date
    processed["week_start"] = processed["occurred_ts"].dt.to_period("W").apply(
        lambda p: p.start_time.date()
    )
    processed["year"] = processed["occurred_ts"].dt.year
    processed["month"] = processed["occurred_ts"].dt.month
    processed["day_of_week"] = processed["occurred_ts"].dt.day_name()
    processed["hour_of_day"] = processed["occurred_ts"].dt.hour
    processed["is_weekend"] = processed["occurred_ts"].dt.weekday >= 5
    processed["violent_flag"] = (
        processed.get("Violent_Crime_excl09A", "").fillna("").astype(str).str.lower()
        == "violent"
    )
    processed["crime_category"] = processed["Crime_Category"].fillna("Unknown")
    processed = processed.sort_values("occurred_ts").reset_index(drop=True)
    return processed


@dataclass
class CrimeDataRepository:
    csv_path: str = str(settings.DATA_FILE)
    cache_ttl_seconds: int = int(settings.CACHE_TTL.total_seconds())

    def __post_init__(self) -> None:
        self._cache: Optional[pd.DataFrame] = None
        self._cache_timestamp: Optional[datetime] = None

    def load(self, force: bool = False) -> pd.DataFrame:
        now = datetime.utcnow()
        if (
            not force
            and self._cache is not None
            and self._cache_timestamp is not None
            and (now - self._cache_timestamp).total_seconds() < self.cache_ttl_seconds
        ):
            return self._cache

        df = pd.read_csv(self.csv_path)
        df = _preprocess(df)
        self._cache = df
        self._cache_timestamp = now
        return df

    def refresh(self) -> pd.DataFrame:
        return self.load(force=True)

