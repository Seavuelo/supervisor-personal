from supervisor.database.connection import get_connection

def create_tables():
    connection = get_connection()
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
        ("created_at", "TEXT")
    ]

    for col_name, col_type in new_columns:
        if col_name not in existing_columns:
            cursor.execute(f"ALTER TABLE tasks ADD COLUMN {col_name} {col_type}")

    # Valores predeterminados en settings si no están
    cursor.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('show_weekly_calendar', 'true')")
    cursor.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('hide_completed_tasks', 'false')")

    connection.commit()
    connection.close()
