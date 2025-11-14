from __future__ import annotations

from datetime import timedelta
from pathlib import Path


class Settings:
    """Central location for configuration constants."""

    PROJECT_ROOT = Path(__file__).resolve().parents[2]
    DATA_DIR = PROJECT_ROOT / "data"
    DATA_FILE = DATA_DIR / "East District Arlingtontx odp crime - PROD.csv"
    CACHE_TTL = timedelta(minutes=15)


settings = Settings()

