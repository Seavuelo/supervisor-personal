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
    set_settings({key: value})

def set_settings(values: Dict[str, str]):
    connection = get_connection()
    cursor = connection.cursor()
    cursor.executemany("""
        INSERT INTO settings (key, value)
        VALUES (?, ?)
        ON CONFLICT(key) DO UPDATE SET value = excluded.value
    """, [(key, str(value)) for key, value in values.items()])
    connection.commit()
    connection.close()

def delete_setting(key: str):
    connection = get_connection()
    try:
        connection.execute("PRAGMA secure_delete = ON")
        removed = connection.execute("DELETE FROM settings WHERE key = ?", (key,)).rowcount
        connection.commit()
        if removed:
            connection.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    finally:
        connection.close()

def get_all_settings() -> Dict[str, str]:
    connection = get_connection()
    cursor = connection.cursor()
    cursor.execute("SELECT key, value FROM settings")
    rows = cursor.fetchall()
    connection.close()
    return {row[0]: row[1] for row in rows}
