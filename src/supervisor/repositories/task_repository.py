from typing import List, Optional, Dict, Any
from supervisor.database.connection import get_connection
from supervisor.models.task import Task

def save_task(task: Task) -> int:
    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute(
        """
        INSERT INTO tasks (title, description, status, scheduled_time, scheduled_date, task_type, tag, goal_id, recurrence, is_priority, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
            1 if task.is_priority else 0,
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
        SELECT id, title, description, status, scheduled_time, scheduled_date, task_type, tag, goal_id, recurrence, is_priority, created_at
        FROM tasks
        ORDER BY 
            CASE status WHEN 'pendiente' THEN 0 ELSE 1 END,
            is_priority DESC,
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
                is_priority=bool(row[10]),
                created_at=row[11] or "",
            )
        )
    return tasks

def toggle_task_priority(task_id: int) -> bool:
    connection = get_connection()
    cursor = connection.cursor()
    cursor.execute("SELECT is_priority FROM tasks WHERE id = ?", (task_id,))
    row = cursor.fetchone()
    if not row:
        connection.close()
        return False

    new_val = 0 if row[0] else 1
    cursor.execute("UPDATE tasks SET is_priority = ? WHERE id = ?", (new_val, task_id))
    connection.commit()
    connection.close()
    return bool(new_val)

def get_overdue_tasks(current_date: str) -> List[Dict[str, Any]]:
    """Retorna tareas pendientes de días anteriores."""
    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute("""
        SELECT id, title, scheduled_date, created_at, tag, is_priority
        FROM tasks
        WHERE status = 'pendiente'
          AND recurrence != 'daily'
          AND (
            (scheduled_date IS NOT NULL AND scheduled_date < ?)
            OR (scheduled_date IS NULL AND substr(created_at, 1, 10) < ?)
          )
        ORDER BY id ASC
    """, (current_date, current_date))
    rows = cursor.fetchall()
    connection.close()

    return [
        {
            "id": r[0],
            "title": r[1],
            "scheduled_date": r[2] or (r[3][:10] if r[3] else ""),
            "created_at": r[3],
            "tag": r[4] or "Atrasada",
            "is_priority": bool(r[5])
        }
        for r in rows
    ]

def postpone_all_overdue(current_date: str, target_date: str) -> int:
    """Mueve todas las tareas atrasadas para el día de hoy."""
    connection = get_connection()
    cursor = connection.cursor()
    cursor.execute("""
        UPDATE tasks
        SET scheduled_date = ?, tag = 'Hoy'
        WHERE status = 'pendiente'
          AND recurrence != 'daily'
          AND (
            (scheduled_date IS NOT NULL AND scheduled_date < ?)
            OR (scheduled_date IS NULL AND substr(created_at, 1, 10) < ?)
          )
    """, (target_date, current_date, current_date))
    connection.commit()
    affected = cursor.rowcount
    connection.close()
    return affected

def dismiss_all_overdue(current_date: str) -> int:
    """Marca como no logradas / descartadas las tareas de días anteriores."""
    connection = get_connection()
    cursor = connection.cursor()
    cursor.execute("""
        UPDATE tasks
        SET status = 'no_lograda'
        WHERE status = 'pendiente'
          AND recurrence != 'daily'
          AND (
            (scheduled_date IS NOT NULL AND scheduled_date < ?)
            OR (scheduled_date IS NULL AND substr(created_at, 1, 10) < ?)
          )
    """, (current_date, current_date))
    connection.commit()
    affected = cursor.rowcount
    connection.close()
    return affected

def get_task_counts_per_date(dates: List[str]) -> Dict[str, int]:
    connection = get_connection()
    cursor = connection.cursor()

    counts = {d: 0 for d in dates}

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
