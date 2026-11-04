from typing import Optional, Dict
from supervisor.database.connection import get_connection

def get_setting(key: str, default: Optional[str] = None) -> Optional[str]:
    connection = get_connection()
    cursor = connection.cursor()
    cursor.execute("SELECT value FROM settings WHERE key = ?", (key,))
    row = cursor.fetchone()
    connection.close()
    if row:
        return row[0]
    return default

def set_setting(key: str, value: str):
    connection = get_connection()
    cursor = connection.cursor()
    cursor.execute("""
        INSERT INTO settings (key, value)
        VALUES (?, ?)
        ON CONFLICT(key) DO UPDATE SET value = excluded.value
    """, (key, str(value)))
    connection.commit()
    connection.close()

def get_all_settings() -> Dict[str, str]:
    connection = get_connection()
    cursor = connection.cursor()
    cursor.execute("SELECT key, value FROM settings")
    rows = cursor.fetchall()
    connection.close()
    return {row[0]: row[1] for row in rows}
