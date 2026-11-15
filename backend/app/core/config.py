import os
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[3]
load_dotenv(ROOT / "backend" / ".env")
PRODUCTION = os.getenv("APP_ENV", "development") == "production"
DATABASE_URL = os.getenv("DATABASE_URL") or f"sqlite:///{(ROOT / 'backend' / 'eventsphere.sqlite3').as_posix()}"
if DATABASE_URL.startswith(("postgres://", "postgresql://")):
    DATABASE_URL = "postgresql+psycopg://" + DATABASE_URL.split("://", 1)[1]
if PRODUCTION and not DATABASE_URL.startswith("postgresql+psycopg://"):
    raise RuntimeError("Production requires a PostgreSQL DATABASE_URL.")

DEMO_ENABLED = os.getenv("DEMO_ENABLED", "0" if PRODUCTION else "1") == "1"
DEMO_DATA_ENABLED = os.getenv("DEMO_DATA_ENABLED", "0" if PRODUCTION else "1") == "1"
SESSION_SECONDS = 8 * 60 * 60
SWEEP_SECONDS = 5
