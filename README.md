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

The API is then available at `http://localhost:8000`. Static files can be served separately (e.g., `python -m http.server` from `frontend/`).

## Render deployment

1. Push this repo to GitHub (`https://github.com/mcmanusandmcmanus/arlingtontx_crime_odp`).
2. In Render, create a _Web Service_ using the repo and point to `render.yaml`. This provisions both:
   - `arlington-compstat-api`: FastAPI + Uvicorn (Python runtime).
   - `arlington-compstat-frontend`: Static site that serves `frontend/`.
3. After deployment, update `frontend/js/app.js` (set `window.API_BASE_URL`) or configure via environment injection to point to the public API URL.

## Data science workflow

- Run `python analysis/generate_eda_report.py` to refresh compstat metrics + `analysis/eda_summary.json` for downstream tooling.
- The FastAPI service exposes:
  - `/compstat` – 7/28/365 day windows, YoY + previous period deltas.
  - `/timeseries` – resampled counts for graphing.
  - `/eda/distributions` – hour-of-day, beats, category breakdowns.
  - `/ml/random-forest` – scikit-learn random forest regression + 7 day forecasts.
  - `/ml/sarimax` – statsmodels SARIMAX 14 day forecast + summary.
  - `/cache/refresh` – reload CSV + clear model caches.

The D3 dashboard pulls from these endpoints to visualize trends, compstat tables, and forecasts.

