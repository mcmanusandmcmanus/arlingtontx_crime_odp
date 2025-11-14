from __future__ import annotations

from functools import lru_cache
from typing import Dict, Optional

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

from .analytics import build_time_series, compute_compstat
from .data_loader import CrimeDataRepository
from .modeling import RandomForestForecast, SarimaxForecast, train_random_forest, train_sarimax

app = FastAPI(
    title="Arlington Crime CompStat API",
    version="1.0.0",
    description="High-frequency analytics and forecasting for Arlington East District open data.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

repository = CrimeDataRepository()


@lru_cache(maxsize=1)
def _random_forest_cache() -> RandomForestForecast:
    df = repository.load()
    return train_random_forest(df)


@lru_cache(maxsize=1)
def _sarimax_cache() -> SarimaxForecast:
    df = repository.load()
    return train_sarimax(df)


@app.get("/health")
def healthcheck() -> Dict[str, str]:
    df = repository.load()
    latest = df["occurred_ts"].max()
    earliest = df["occurred_ts"].min()
    return {
        "status": "ok",
        "records": len(df),
        "earliest": earliest.isoformat() if earliest is not None else None,
        "latest": latest.isoformat() if latest is not None else None,
    }


@app.get("/compstat")
def compstat(
    group_by: Optional[str] = Query(None, description="Optional column to group results by.")
) -> Dict[str, object]:
    df = repository.load()
    return compute_compstat(df, group_by=group_by)


@app.get("/timeseries")
def timeseries(
    freq: str = Query("D", description="Pandas frequency code. D=day, W=week, M=month."),
    periods: Optional[int] = Query(90, description="Number of trailing periods to include."),
):
    df = repository.load()
    frame = build_time_series(df, freq=freq, periods=periods)
    return frame.to_dict(orient="records")


@app.get("/eda/distributions")
def eda_distributions() -> Dict[str, object]:
    df = repository.load()
    hour_distribution = (
        df.groupby("hour_of_day").size().reset_index(name="count").sort_values("hour_of_day")
    )
    day_distribution = (
        df.groupby("day_of_week").size().reset_index(name="count").sort_values("count", ascending=False)
    )
    beats_distribution = (
        df.groupby("Beats").size().reset_index(name="count").sort_values("count", ascending=False)
    )
    category_distribution = (
        df.groupby("crime_category").size().reset_index(name="count").sort_values("count", ascending=False)
    )
    return {
        "hour_of_day": hour_distribution.to_dict(orient="records"),
        "day_of_week": day_distribution.to_dict(orient="records"),
        "beats": beats_distribution.to_dict(orient="records"),
        "crime_category": category_distribution.to_dict(orient="records"),
    }


@app.get("/ml/random-forest")
def random_forest_forecast() -> Dict[str, object]:
    result = _random_forest_cache()
    return {
        "metrics": result.metrics,
        "next_week_forecast": result.next_week,
    }


@app.get("/ml/sarimax")
def sarimax_forecast() -> Dict[str, object]:
    result = _sarimax_cache()
    summary_lines = result.model_summary.splitlines()
    trimmed_summary = "\n".join(summary_lines[:20])
    return {
        "metrics": result.metrics,
        "forecast": result.forecast,
        "model_summary": trimmed_summary,
    }


@app.post("/cache/refresh")
def refresh_cache() -> Dict[str, str]:
    repository.refresh()
    _random_forest_cache.cache_clear()
    _sarimax_cache.cache_clear()
    return {"status": "refreshed"}
