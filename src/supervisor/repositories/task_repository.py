from typing import List, Optional
from supervisor.database.connection import get_connection
from supervisor.models.task import Task

def save_task(task: Task) -> int:
    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute(
        """
        INSERT INTO tasks (title, description, status, scheduled_time, scheduled_date, task_type, tag, goal_id, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            task.title,
            task.description,
            task.status,
            task.scheduled_time,
            task.scheduled_date,
            task.task_type,
            task.tag,
            task.goal_id,
            task.created_at,
        ),
    )

    connection.commit()
    task_id = cursor.lastrowid
    connection.close()
    return task_id

def get_all_tasks() -> List[Task]:
    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute("""
        SELECT id, title, description, status, scheduled_time, scheduled_date, task_type, tag, goal_id, created_at
        FROM tasks
        ORDER BY 
            CASE status WHEN 'pendiente' THEN 0 ELSE 1 END,
            id DESC
    """)
    rows = cursor.fetchall()
    connection.close()

    tasks = []
    for row in rows:
        tasks.append(
            Task(
                id=row[0],
                title=row[1],
                description=row[2] or "",
                status=row[3],
                scheduled_time=row[4],
                scheduled_date=row[5],
                task_type=row[6] or "quick",
                tag=row[7] or "Hoy",
                goal_id=row[8],
                created_at=row[9] or "",
            )
        )
    return tasks

def toggle_task_status(task_id: int) -> Optional[str]:
    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute("SELECT status FROM tasks WHERE id = ?", (task_id,))
    row = cursor.fetchone()
    if not row:
        connection.close()
        return None

    current_status = row[0]
    new_status = "completada" if current_status == "pendiente" else "pendiente"

    cursor.execute("UPDATE tasks SET status = ? WHERE id = ?", (new_status, task_id))
    connection.commit()
    connection.close()
    return new_status

def delete_task(task_id: int) -> bool:
    connection = get_connection()
    cursor = connection.cursor()
    cursor.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
    connection.commit()
    affected = cursor.rowcount > 0
    connection.close()
    return affected
