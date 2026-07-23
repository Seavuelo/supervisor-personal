from supervisor.database.connection import get_connection


def create_tables():
    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            description TEXT NOT NULL,
            status TEXT NOT NULL
        )
    """)

    connection.commit()
    connection.close()