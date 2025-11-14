from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from typing import Dict, List

import pandas as pd
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import mean_absolute_error, r2_score
from statsmodels.tsa.statespace.sarimax import SARIMAX


def _build_daily_aggregates(df: pd.DataFrame) -> pd.DataFrame:
    daily = (
        df.groupby("occurred_date")
        .size()
        .reset_index(name="count")
        .sort_values("occurred_date")
    )
    daily["date"] = pd.to_datetime(daily["occurred_date"])
    daily["day_of_week"] = daily["date"].dt.weekday
    daily["month"] = daily["date"].dt.month
    daily["is_weekend"] = daily["day_of_week"] >= 5
    daily["lag1"] = daily["count"].shift(1)
    daily["lag7"] = daily["count"].shift(7)
    daily = daily.dropna().reset_index(drop=True)
    return daily


@dataclass
class RandomForestForecast:
    model: RandomForestRegressor
    metrics: Dict[str, float]
    next_week: List[Dict[str, float]]


def train_random_forest(df: pd.DataFrame, forecast_horizon: int = 7) -> RandomForestForecast:
    daily = _build_daily_aggregates(df)
    feature_cols = ["day_of_week", "month", "is_weekend", "lag1", "lag7"]
    X = daily[feature_cols]
    y = daily["count"]
    split_idx = int(len(daily) * 0.8)
    X_train, X_test = X.iloc[:split_idx], X.iloc[split_idx:]
    y_train, y_test = y.iloc[:split_idx], y.iloc[split_idx:]

    model = RandomForestRegressor(n_estimators=300, random_state=42)
    model.fit(X_train, y_train)
    predictions = model.predict(X_test)
    metrics = {
        "mae": float(mean_absolute_error(y_test, predictions)),
        "r2": float(r2_score(y_test, predictions)),
    }

    history = daily["count"].tolist()
    last_date = daily["date"].iloc[-1]
    future_predictions: List[Dict[str, float]] = []
    for step in range(1, forecast_horizon + 1):
        next_date = last_date + timedelta(days=step)
        lag1 = history[-1]
        lag7 = history[-7] if len(history) >= 7 else history[-1]
        feature_vector = pd.DataFrame(
            [
                {
                    "day_of_week": next_date.weekday(),
                    "month": next_date.month,
                    "is_weekend": next_date.weekday() >= 5,
                    "lag1": lag1,
                    "lag7": lag7,
                }
            ]
        )
        pred = float(model.predict(feature_vector)[0])
        future_predictions.append(
            {
                "date": next_date.strftime("%Y-%m-%d"),
                "predicted_count": pred,
            }
        )
        history.append(pred)

    return RandomForestForecast(model=model, metrics=metrics, next_week=future_predictions)


@dataclass
class SarimaxForecast:
    model_summary: str
    metrics: Dict[str, float]
    forecast: List[Dict[str, float]]


def train_sarimax(df: pd.DataFrame, forecast_horizon: int = 14) -> SarimaxForecast:
    daily = (
        df.groupby("occurred_date")
        .size()
        .rename("count")
        .to_frame()
        .sort_index()
    )
    daily.index = pd.to_datetime(daily.index)
    series = daily["count"]
    split_idx = int(len(series) * 0.85)
    train_series = series.iloc[:split_idx]
    test_series = series.iloc[split_idx:]

    model = SARIMAX(train_series, order=(1, 0, 1), seasonal_order=(1, 1, 1, 7))
    fitted = model.fit(disp=False)
    preds = fitted.get_forecast(steps=len(test_series)).predicted_mean
    aligned_preds = preds[: len(test_series)]
    mae = float(mean_absolute_error(test_series, aligned_preds))
    r2 = float(r2_score(test_series, aligned_preds))

    forecast_result = fitted.get_forecast(steps=forecast_horizon)
    future_index = forecast_result.predicted_mean.index
    forecast_payload = [
        {"date": idx.strftime("%Y-%m-%d"), "predicted_count": float(value)}
        for idx, value in forecast_result.predicted_mean.items()
    ]

    return SarimaxForecast(
        model_summary=fitted.summary().as_text(),
        metrics={"mae": mae, "r2": r2},
        forecast=forecast_payload,
    )
