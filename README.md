# Arlington East District Crime CompStat

End-to-end open data project that ingests Arlington TX crime incidents, produces CompStat-style analytics, runs classical + machine learning forecasts, and powers a D3.js situational-awareness dashboard.

## Project layout

- `data/` raw CSV extracted from the Open Data Portal.
- `analysis/` reproducible EDA + summary JSON (`python analysis/generate_eda_report.py`).
- `backend/` FastAPI app exposing analytics + model endpoints (`uvicorn backend.app.main:app --reload`).
- `frontend/` static dashboard (open `frontend/index.html` or host on any static site, e.g., Render).

## Local setup

```bash
python -m venv .venv
.venv\Scripts\activate  # or source .venv/bin/activate on macOS/Linux
pip install -r backend/requirements.txt
uvicorn backend.app.main:app --reload
```

The API is then available at `http://localhost:8000`. Static files can be served separately (for example `python -m http.server` from `frontend/`).

## Render deployment

1. Push this repo to GitHub (`https://github.com/mcmanusandmcmanus/arlingtontx_crime_odp`).
2. In Render, create a _Web Service_ using the repo and point to `render.yaml`. This provisions both:
   - `arlington-compstat-api`: FastAPI + Uvicorn (Python runtime).
   - `arlington-compstat-frontend`: Static site that serves `frontend/`.
3. After deployment, set the dashboard’s API endpoint (see below) so it talks to the Render FastAPI URL.

## Data science workflow

- Run `python analysis/generate_eda_report.py` to refresh CompStat metrics and `analysis/eda_summary.json`.
- The FastAPI service exposes:
  - `/compstat` - 7/28/365 day windows with period-over-period and YoY deltas.
  - `/timeseries` - resampled counts for graphing (supports `group_by`).
  - `/eda/distributions` - hour-of-day, beats, and category breakdowns.
  - `/aggregates/count-by` & `/aggregates/heatmap` - generic rollups for any column pair.
  - `/ml/random-forest` - scikit-learn regression forecast + metrics.
  - `/ml/sarimax` - statsmodels SARIMAX forecast + metrics.
  - `/cases/search` - search case numbers or descriptions.
  - `/cache/refresh` - reload CSV + clear model caches.

## Frontend API endpoint

Use the **API Endpoint** card near the top of `frontend/index.html` to paste your Render FastAPI URL (for example, `https://arlington-compstat-api.onrender.com`) and click **Update & Reload**. The value is stored in the browser’s `localStorage`, so you only need to set it once per device—no rebuild is required to point the frontend at a different API.
