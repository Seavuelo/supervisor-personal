from supervisor.database.connection import get_connection
from supervisor.models.task import Task

def save_task(task: Task) -> int:
    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute(
        """
        INSERT INTO tasks (title, description, status)
        VALUES (?, ?, ?)
        """,
        (task.title, task.description, task.status)
    )

    connection.commit()
    task_id = cursor.lastrowid
    connection.close()

    return task_id