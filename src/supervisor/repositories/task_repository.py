import calendar
import time
from datetime import datetime, date
from typing import List, Optional, Dict, Any
from supervisor.database.connection import get_connection
from supervisor.models.task import Task

def touch_data_version():
    """Actualiza la version de datos para que clientes externos y la GUI sincronicen."""
    try:
        connection = get_connection()
        cursor = connection.cursor()
        now_ts = str(int(time.time() * 1000))
        cursor.execute("INSERT OR REPLACE INTO settings (key, value) VALUES ('data_version', ?)", (now_ts,))
        connection.commit()
        connection.close()
    except Exception:
        pass

def get_data_version() -> str:
    try:
        connection = get_connection()
        cursor = connection.cursor()
        cursor.execute("SELECT value FROM settings WHERE key = 'data_version'")
        row = cursor.fetchone()
        connection.close()
        return row[0] if row else "0"
    except Exception:
        return "0"

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
    touch_data_version()
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
    touch_data_version()
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
    if affected:
        touch_data_version()
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
    if affected:
        touch_data_version()
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
    touch_data_version()
    return new_status

def set_task_status(task_id: int, status: str) -> bool:
    connection = get_connection()
    cursor = connection.cursor()
    cursor.execute("UPDATE tasks SET status = ? WHERE id = ?", (status, task_id))
    connection.commit()
    affected = cursor.rowcount > 0
    connection.close()
    if affected:
        touch_data_version()
    return affected

def delete_task(task_id: int) -> bool:
    connection = get_connection()
    cursor = connection.cursor()
    cursor.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
    connection.commit()
    affected = cursor.rowcount > 0
    connection.close()
    if affected:
        touch_data_version()
    return affected

def get_tasks_by_month(year_month: str) -> List[Task]:
    """
    Retorna todas las tareas vinculadas a un mes determinado (formato YYYY-MM).
    Incluye tareas con fecha programada en el mes, tareas creadas en el mes sin fecha,
    y tareas recurrentes diarias.
    """
    connection = get_connection()
    cursor = connection.cursor()

    pattern = f"{year_month}%"
    cursor.execute("""
        SELECT id, title, description, status, scheduled_time, scheduled_date, task_type, tag, goal_id, recurrence, is_priority, created_at
        FROM tasks
        WHERE scheduled_date LIKE ?
           OR (scheduled_date IS NULL AND created_at LIKE ?)
           OR recurrence = 'daily'
        ORDER BY 
            CASE status WHEN 'pendiente' THEN 0 ELSE 1 END,
            scheduled_date ASC,
            scheduled_time ASC,
            is_priority DESC
    """, (pattern, pattern))
    rows = cursor.fetchall()
    connection.close()

    return [
        Task(
            id=r[0],
            title=r[1],
            description=r[2] or "",
            status=r[3],
            scheduled_time=r[4],
            scheduled_date=r[5],
            task_type=r[6] or "quick",
            tag=r[7] or "Hoy",
            goal_id=r[8],
            recurrence=r[9] or "none",
            is_priority=bool(r[10]),
            created_at=r[11] or "",
        )
        for r in rows
    ]

def get_monthly_summary(year_month: str) -> Dict[str, Any]:
    """
    Genera un resumen analitico del mes con distribucion por dias,
    conteo de 'ticks' completados, actividades pendientes y tasa de exito.
    """
    try:
        parts = year_month.split("-")
        year = int(parts[0])
        month = int(parts[1])
    except Exception:
        now = datetime.now()
        year = now.year
        month = now.month
        year_month = f"{year:04d}-{month:02d}"

    num_days = calendar.monthrange(year, month)[1]
    day_names = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"]

    connection = get_connection()
    cursor = connection.cursor()

    # Tareas del mes
    pattern = f"{year_month}%"
    cursor.execute("""
        SELECT id, scheduled_date, status, recurrence, is_priority, title
        FROM tasks
        WHERE scheduled_date LIKE ? 
           OR (scheduled_date IS NULL AND created_at LIKE ?)
           OR recurrence = 'daily'
    """, (pattern, pattern))
    rows = cursor.fetchall()
    connection.close()

    total_tasks = len(rows)
    total_completed = sum(1 for r in rows if r[2] == "completada")
    total_pending = sum(1 for r in rows if r[2] == "pendiente")
    total_dismissed = sum(1 for r in rows if r[2] == "no_lograda")

    completion_rate = round((total_completed / total_tasks * 100), 1) if total_tasks > 0 else 0.0

    # Desglose diario
    days_data = []
    for day_num in range(1, num_days + 1):
        d_str = f"{year_month}-{day_num:02d}"
        weekday_idx = calendar.weekday(year, month, day_num)
        
        day_tasks = [
            r for r in rows 
            if r[1] == d_str or (r[1] is None and r[3] != 'daily') or r[3] == 'daily'
        ]
        completed = sum(1 for r in day_tasks if r[2] == "completada")
        pending = sum(1 for r in day_tasks if r[2] == "pendiente")

        days_data.append({
            "date": d_str,
            "day": day_num,
            "weekday": day_names[weekday_idx],
            "weekday_short": day_names[weekday_idx][:2],
            "total": len(day_tasks),
            "completed_ticks": completed,
            "pending": pending,
            "has_activity": len(day_tasks) > 0,
        })

    month_name = calendar.month_name[month]
    return {
        "year_month": year_month,
        "year": year,
        "month": month,
        "month_name": month_name,
        "total_tasks": total_tasks,
        "completed_ticks": total_completed,
        "pending_tasks": total_pending,
        "dismissed_tasks": total_dismissed,
        "completion_rate_percent": completion_rate,
        "days": days_data,
    }

def get_overall_stats() -> Dict[str, Any]:
    """Retorna estadisticas globales del supervisor personal."""
    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute("SELECT COUNT(*) FROM tasks")
    total_tasks = cursor.fetchone()[0] or 0

    cursor.execute("SELECT COUNT(*) FROM tasks WHERE status = 'completada'")
    total_ticks = cursor.fetchone()[0] or 0

    cursor.execute("SELECT COUNT(*) FROM tasks WHERE status = 'pendiente'")
    total_pending = cursor.fetchone()[0] or 0

    cursor.execute("SELECT COUNT(*) FROM tasks WHERE is_priority = 1 AND status = 'pendiente'")
    priority_pending = cursor.fetchone()[0] or 0

    cursor.execute("SELECT COUNT(*) FROM goals WHERE status = 'activa'")
    active_goals = cursor.fetchone()[0] or 0

    cursor.execute("SELECT COUNT(*) FROM goals WHERE status = 'completada'")
    completed_goals = cursor.fetchone()[0] or 0

    connection.close()

    rate = round((total_ticks / total_tasks * 100), 1) if total_tasks > 0 else 0.0

    return {
        "total_tasks": total_tasks,
        "completed_ticks": total_ticks,
        "pending_tasks": total_pending,
        "priority_pending": priority_pending,
        "active_goals": active_goals,
        "completed_goals": completed_goals,
        "completion_rate_percent": rate,
    }
