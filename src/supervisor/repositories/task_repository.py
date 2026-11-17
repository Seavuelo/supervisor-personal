import calendar
from contextlib import closing
from dataclasses import replace
from datetime import date, timedelta
from typing import List, Optional, Dict, Any
from supervisor.database.connection import get_connection
from supervisor.models.task import RECURRING, Task, occurrence_on_or_after

TASK_COLUMNS = "id, title, description, status, scheduled_time, scheduled_date, task_type, tag, goal_id, recurrence, is_priority, created_at"
ACTIVE_SERIES = "recurrence IN ('daily', 'weekly', 'monthly') AND status != 'no_lograda'"
OVERDUE_FOCUS = """
    status = 'pendiente' AND goal_id IS NULL AND COALESCE(recurrence, 'none') = 'none'
    AND COALESCE(task_type, 'quick') != 'appointment' AND COALESCE(scheduled_time, '') = ''
    AND COALESCE(NULLIF(scheduled_date, ''), substr(created_at, 1, 10)) < ?
"""


def _task_from_row(row) -> Task:
    return Task(
        id=row[0], title=row[1], description=row[2] or "", status=row[3],
        scheduled_time=row[4], scheduled_date=row[5], task_type=row[6] or "quick",
        tag=row[7] or "Hoy", goal_id=row[8], recurrence=row[9] or "none",
        is_priority=bool(row[10]), created_at=row[11] or "",
    )


def _occurrence(task: Task, start: date) -> Optional[date]:
    return occurrence_on_or_after(task.recurrence, task.scheduled_date or task.created_at, start)


def _project_task(task: Task, due: date, ticks) -> Task:
    due_date = due.isoformat()
    return replace(
        task,
        scheduled_date=due_date if task.recurrence != "daily" or task.scheduled_date else None,
        status="completada" if (task.id, due_date) in ticks else "pendiente",
    )

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
    today = date.today()
    with closing(get_connection()) as connection:
        rows = connection.execute(f"SELECT {TASK_COLUMNS} FROM tasks").fetchall()
        ticks = set(connection.execute(
            "SELECT task_id, due_date FROM task_ticks WHERE due_date >= ?", (today.isoformat(),)
        ))
    tasks = []
    for row in rows:
        task = _task_from_row(row)
        if task.recurrence in RECURRING and task.status != "no_lograda":
            due = _occurrence(task, today)
            if due:
                task = _project_task(task, due, ticks)
        tasks.append(task)
    tasks.sort(key=lambda task: (task.status != "pendiente", not task.is_priority, -task.id))
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

    cursor.execute(f"""
        SELECT id, title, scheduled_date, created_at, tag, is_priority
        FROM tasks
        WHERE {OVERDUE_FOCUS}
        ORDER BY id ASC
    """, (current_date,))
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
    cursor.execute(f"""
        UPDATE tasks
        SET scheduled_date = ?, tag = 'Hoy'
        WHERE {OVERDUE_FOCUS}
    """, (target_date, current_date))
    connection.commit()
    affected = cursor.rowcount
    connection.close()
    return affected

def dismiss_all_overdue(current_date: str) -> int:
    """Marca como no logradas / descartadas las tareas de días anteriores."""
    connection = get_connection()
    cursor = connection.cursor()
    cursor.execute(f"""
        UPDATE tasks
        SET status = 'no_lograda'
        WHERE {OVERDUE_FOCUS}
    """, (current_date,))
    connection.commit()
    affected = cursor.rowcount
    connection.close()
    return affected

def get_task_counts_per_date(dates: List[str]) -> Dict[str, int]:
    counts = {d: 0 for d in dates}
    if counts:
        for _, due in _tasks_in_range(date.fromisoformat(min(counts)), date.fromisoformat(max(counts))):
            if due in counts:
                counts[due] += 1
    return counts

def toggle_task_status(task_id: int) -> Optional[str]:
    return _write_task_status(task_id)

def set_task_status(task_id: int, status: str) -> bool:
    return _write_task_status(task_id, status) is not None


def _write_task_status(task_id: int, status: Optional[str] = None) -> Optional[str]:
    with closing(get_connection()) as connection, connection:
        connection.execute("BEGIN IMMEDIATE")
        row = connection.execute(f"SELECT {TASK_COLUMNS} FROM tasks WHERE id = ?", (task_id,)).fetchone()
        if not row:
            return None
        task = _task_from_row(row)
        due = _occurrence(task, date.today()) if task.recurrence in RECURRING else None
        if due:
            tick = (task_id, due.isoformat())
            completed = connection.execute(
                "SELECT 1 FROM task_ticks WHERE task_id = ? AND due_date = ?", tick
            ).fetchone()
            status = status or ("pendiente" if completed or task.status == "no_lograda" else "completada")
            if status == "completada":
                connection.execute("INSERT OR IGNORE INTO task_ticks VALUES (?, ?)", tick)
            else:
                connection.execute("DELETE FROM task_ticks WHERE task_id = ? AND due_date = ?", tick)
            stored_status = "pendiente" if status == "completada" else status
        else:
            status = status or ("completada" if task.status == "pendiente" else "pendiente")
            stored_status = status
        connection.execute("UPDATE tasks SET status = ? WHERE id = ?", (stored_status, task_id))
    return status

def delete_task(task_id: int) -> bool:
    connection = get_connection()
    cursor = connection.cursor()
    cursor.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
    connection.commit()
    affected = cursor.rowcount > 0
    connection.close()
    return affected

def _tasks_in_range(start: date, end: date, first_only=False):
    limits = (start.isoformat(), end.isoformat())
    with closing(get_connection()) as connection:
        rows = connection.execute(f"""
            SELECT {TASK_COLUMNS} FROM tasks
            WHERE COALESCE(NULLIF(scheduled_date, ''), substr(created_at, 1, 10)) BETWEEN ? AND ?
               OR ({ACTIVE_SERIES})
        """, limits).fetchall()
        ticks = set(connection.execute(
            "SELECT task_id, due_date FROM task_ticks WHERE due_date BETWEEN ? AND ?", limits
        ))
    for row in rows:
        task = _task_from_row(row)
        anchor = task.scheduled_date or task.created_at[:10]
        if task.recurrence not in RECURRING or task.status == "no_lograda":
            if limits[0] <= anchor <= limits[1]:
                yield task, anchor
            continue
        due = _occurrence(task, start)
        while due and due <= end:
            yield _project_task(task, due, ticks), due.isoformat()
            if first_only or due == end:
                break
            due = _occurrence(task, due + timedelta(days=1))


def _month_range(year_month: str):
    try:
        start = date.fromisoformat(f"{year_month}-01")
    except ValueError:
        start = date.today().replace(day=1)
    return start, start.replace(day=calendar.monthrange(start.year, start.month)[1])


def get_tasks_by_month(year_month: str) -> List[Task]:
    start, end = _month_range(year_month)
    tasks = list(_tasks_in_range(start, end, first_only=True))
    tasks.sort(key=lambda item: (item[0].status != "pendiente", item[1],
                                 item[0].scheduled_time or "", not item[0].is_priority))
    return [task for task, _ in tasks]

def get_monthly_summary(year_month: str) -> Dict[str, Any]:
    """
    Genera un resumen analitico del mes con distribucion por dias,
    conteo de 'ticks' completados, actividades pendientes y tasa de exito.
    """
    start, end = _month_range(year_month)
    year, month = start.year, start.month
    year_month = start.isoformat()[:7]
    day_names = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"]

    statuses_by_day = {}
    for task, due in _tasks_in_range(start, end):
        statuses_by_day.setdefault(due, []).append(task.status)
    total_tasks = sum(map(len, statuses_by_day.values()))
    total_completed = sum(statuses.count("completada") for statuses in statuses_by_day.values())
    total_pending = sum(statuses.count("pendiente") for statuses in statuses_by_day.values())
    total_dismissed = sum(statuses.count("no_lograda") for statuses in statuses_by_day.values())

    completion_rate = round((total_completed / total_tasks * 100), 1) if total_tasks > 0 else 0.0

    # Desglose diario
    days_data = []
    for day_num in range(1, end.day + 1):
        d_str = f"{year_month}-{day_num:02d}"
        weekday_idx = calendar.weekday(year, month, day_num)
        
        day_tasks = statuses_by_day.get(d_str, [])

        days_data.append({
            "date": d_str,
            "day": day_num,
            "weekday": day_names[weekday_idx],
            "weekday_short": day_names[weekday_idx][:2],
            "total": len(day_tasks),
            "completed_ticks": day_tasks.count("completada"),
            "pending": day_tasks.count("pendiente"),
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

    tasks = get_all_tasks()
    total_tasks = len(tasks)
    total_ticks = sum(task.status == "completada" for task in tasks)
    total_pending = sum(task.status == "pendiente" for task in tasks)
    priority_pending = sum(task.is_priority and task.status == "pendiente" for task in tasks)

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
