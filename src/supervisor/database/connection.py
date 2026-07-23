import sqlite3
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[3]
DATABASE_PATH = PROJECT_ROOT / "data" / "supervisor.db"

def get_connection():
    DATABASE_PATH.parent.mkdir(exist_ok=True)
    return sqlite3.connect(DATABASE_PATH)