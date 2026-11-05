import os
import sys
import shutil
import sqlite3
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[3]

def _resolve_database_path() -> Path:
    # 1. Variable de entorno personalizada
    env_db = os.environ.get("SEEU_DATABASE_PATH")
    if env_db:
        return Path(env_db)

    # 2. En desarrollo local (si existe local y no está congelado como binario)
    local_db = PROJECT_ROOT / "data" / "supervisor.db"
    is_frozen = getattr(sys, "frozen", False)

    if not is_frozen and local_db.exists():
        return local_db

    # 3. En entorno instalado (Windows AppData o Linux ~/.local/share)
    if sys.platform == "win32":
        appdata = os.environ.get("APPDATA")
        base = Path(appdata) / "seeU" if appdata else Path.home() / "AppData" / "Roaming" / "seeU"
    else:
        base = Path.home() / ".local" / "share" / "seeU"

    user_db = base / "data" / "supervisor.db"

    # Migración segura si existía base de datos local previa
    if not user_db.exists() and local_db.exists():
        try:
            user_db.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(local_db, user_db)
        except Exception:
            pass

    return user_db

DATABASE_PATH = _resolve_database_path()

def get_connection():
    DATABASE_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DATABASE_PATH, timeout=30.0)
    try:
        conn.execute("PRAGMA journal_mode = WAL")
        conn.execute("PRAGMA synchronous = NORMAL")
        conn.execute("PRAGMA foreign_keys = ON")
    except Exception:
        pass
    return conn
