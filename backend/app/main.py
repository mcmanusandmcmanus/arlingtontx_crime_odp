from __future__ import annotations

from functools import lru_cache
from typing import Dict, Optional

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

from .aggregations import count_by as agg_count_by, heatmap as agg_heatmap
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
    group_by: Optional[str] = Query(None, description="Optional column for grouping."),
):
    df = repository.load()
    frame = build_time_series(df, freq=freq, periods=periods, group_by=group_by)
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


@app.get("/aggregates/count-by")
def aggregates_count_by(
    dimension: str = Query(..., description="Column name to aggregate by."),
    limit: Optional[int] = Query(None, ge=1, le=100, description="Optional number of rows to return."),
) -> Dict[str, object]:
    df = repository.load()
    try:
        result = agg_count_by(df, dimension, limit)
    except KeyError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return {"dimension": dimension, "values": result.to_dict(orient="records")}


@app.get("/aggregates/heatmap")
def aggregates_heatmap(
    dim_x: str = Query(..., description="Column name for the X axis."),
    dim_y: str = Query(..., description="Column name for the Y axis."),
) -> Dict[str, object]:
    df = repository.load()
    try:
        result = agg_heatmap(df, dim_x, dim_y)
    except KeyError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    payload = [
        {"x": row[dim_x], "y": row[dim_y], "count": int(row["count"])}
        for _, row in result.iterrows()
    ]
    return {"dim_x": dim_x, "dim_y": dim_y, "values": payload}


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


@app.get("/cases/search")
def case_search(
    q: str = Query(..., min_length=2, description="Case number or keyword to search."),
    limit: int = Query(25, ge=1, le=100),
) -> Dict[str, object]:
    df = repository.load()
    q_lower = q.lower()
    case_matches = df["Case Number"].astype(str).str.contains(q_lower, case=False, na=False)
    description_matches = df["Description"].fillna("").str.contains(q_lower, case=False, na=False)
    matches = df.loc[case_matches | description_matches].copy()
    matches = matches.sort_values("occurred_ts", ascending=False).head(limit)
    matches["occurred_ts"] = matches["occurred_ts"].dt.strftime("%Y-%m-%d %H:%M")
    return {
        "query": q,
        "results": matches[
            ["Case Number", "occurred_ts", "crime_category", "Beats", "violent_flag", "Description"]
        ]
        .rename(
            columns={
                "Case Number": "case_number",
                "Beats": "beat",
                "Description": "description",
                "crime_category": "crime_category",
                "violent_flag": "violent",
            }
        )
        .to_dict(orient="records"),
    }
