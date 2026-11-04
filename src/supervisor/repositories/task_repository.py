from typing import List, Optional, Dict, Any
from supervisor.database.connection import get_connection
from supervisor.models.task import Task

def save_task(task: Task) -> int:
    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute(
        """
        INSERT INTO tasks (title, description, status, scheduled_time, scheduled_date, task_type, tag, goal_id, recurrence, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
            task.recurrence,
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
        SELECT id, title, description, status, scheduled_time, scheduled_date, task_type, tag, goal_id, recurrence, created_at
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
                recurrence=row[9] or "none",
                created_at=row[10] or "",
            )
        )
    return tasks

def get_task_counts_per_date(dates: List[str]) -> Dict[str, int]:
    """Retorna un diccionario {fecha_iso: cantidad_tareas} para las fechas dadas, incluyendo tareas recurrentes diarias."""
    connection = get_connection()
    cursor = connection.cursor()

    counts = {d: 0 for d in dates}

    # Contar tareas diarias generales (cuentan para todos los días de la semana)
    cursor.execute("SELECT COUNT(*) FROM tasks WHERE recurrence = 'daily' AND status = 'pendiente'")
    daily_count = cursor.fetchone()[0] or 0

    for d in dates:
        cursor.execute("SELECT COUNT(*) FROM tasks WHERE scheduled_date = ? AND recurrence != 'daily'", (d,))
        specific_count = cursor.fetchone()[0] or 0
        counts[d] = specific_count + daily_count

    connection.close()
    return counts

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
