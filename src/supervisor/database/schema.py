from supervisor.database.connection import get_connection
from contextlib import closing

def create_tables():
    with closing(get_connection()) as connection, connection:
        connection.execute("PRAGMA journal_mode = WAL")
        connection.execute("BEGIN IMMEDIATE")
        _create_tables(connection)


def _create_tables(connection):
    cursor = connection.cursor()

    # Tabla de metas / proyectos
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS goals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            description TEXT DEFAULT '',
            status TEXT NOT NULL DEFAULT 'activa',
            category TEXT DEFAULT 'estudio',
            created_at TEXT
        )
    """)

    # Tabla de tareas
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            description TEXT DEFAULT '',
            status TEXT NOT NULL DEFAULT 'pendiente',
            scheduled_time TEXT,
            scheduled_date TEXT,
            task_type TEXT DEFAULT 'quick',
            tag TEXT DEFAULT 'Hoy',
            goal_id INTEGER,
            recurrence TEXT DEFAULT 'none',
            is_priority INTEGER DEFAULT 0,
            created_at TEXT,
            FOREIGN KEY (goal_id) REFERENCES goals(id) ON DELETE CASCADE
        )
    """)

    # Tabla de configuraciones
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT
        )
    """)

    # Migración de columnas de tasks
    cursor.execute("PRAGMA table_info(tasks)")
    existing_columns = [row[1] for row in cursor.fetchall()]

    new_columns = [
        ("scheduled_time", "TEXT"),
        ("scheduled_date", "TEXT"),
        ("task_type", "TEXT DEFAULT 'quick'"),
        ("tag", "TEXT DEFAULT 'Hoy'"),
        ("goal_id", "INTEGER"),
        ("recurrence", "TEXT DEFAULT 'none'"),
        ("is_priority", "INTEGER DEFAULT 0"),
        ("created_at", "TEXT")
    ]

    for col_name, col_type in new_columns:
        if col_name not in existing_columns:
            cursor.execute(f"ALTER TABLE tasks ADD COLUMN {col_name} {col_type}")

    # Las versiones antiguas solo guardaban un tick por serie.
    if not cursor.execute("SELECT 1 FROM sqlite_master WHERE name = 'task_ticks'").fetchone():
        cursor.execute("""
            CREATE TABLE task_ticks (
                task_id INTEGER NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
                due_date TEXT NOT NULL,
                PRIMARY KEY (task_id, due_date)
            )
        """)
        cursor.execute("""
            INSERT INTO task_ticks (task_id, due_date)
            SELECT id, substr(COALESCE(NULLIF(scheduled_date, ''), created_at), 1, 10)
            FROM tasks
            WHERE recurrence IN ('daily', 'weekly', 'monthly') AND status = 'completada'
              AND date(COALESCE(NULLIF(scheduled_date, ''), created_at)) IS NOT NULL
        """)
        cursor.execute("""
            UPDATE tasks SET status = 'pendiente'
            WHERE id IN (SELECT task_id FROM task_ticks)
        """)

    cursor.execute("CREATE INDEX IF NOT EXISTS tasks_by_goal ON tasks(goal_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS ticks_by_date ON task_ticks(due_date)")
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS tasks_by_date
        ON tasks(COALESCE(NULLIF(scheduled_date, ''), substr(created_at, 1, 10)))
    """)
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS active_series
        ON tasks(recurrence) WHERE status != 'no_lograda'
    """)

    # Valores predeterminados en settings
    cursor.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('show_weekly_calendar', 'true')")
    cursor.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('hide_completed_tasks', 'false')")
    cursor.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('auto_rotate_tabs', 'true')")
    cursor.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('autostart', 'false')")
