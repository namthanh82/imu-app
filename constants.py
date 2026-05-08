import os
from pathlib import Path

from chromadb.config import Settings
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")

DATA_DIR = Path(os.environ.get("IMU_WEB_DATA_DIR", str(Path.home() / ".imu-web-min"))).expanduser()
if not DATA_DIR.is_absolute():
    DATA_DIR = BASE_DIR / DATA_DIR
DATA_DIR.mkdir(parents=True, exist_ok=True)

PERSIST_DIRECTORY = os.environ.get("PERSIST_DIRECTORY", str(DATA_DIR / "db"))
PERSIST_PATH = Path(PERSIST_DIRECTORY).expanduser()
if not PERSIST_PATH.is_absolute():
    PERSIST_PATH = BASE_DIR / PERSIST_PATH
PERSIST_PATH.mkdir(parents=True, exist_ok=True)

CHROMA_SETTINGS = Settings(
    chroma_db_impl="duckdb+parquet",
    persist_directory=str(PERSIST_PATH),
    anonymized_telemetry=False,
)
