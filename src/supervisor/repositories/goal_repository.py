from typing import List, Optional, Dict, Any
from contextlib import closing
from supervisor.database.connection import get_connection
from supervisor.models.goal import Goal

def save_goal(goal: Goal) -> int:
    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute(
        """
        INSERT INTO goals (title, description, status, category, created_at)
        VALUES (?, ?, ?, ?, ?)
        """,
        (
            goal.title,
            goal.description,
            goal.status,
            goal.category,
            goal.created_at,
        ),
    )

    connection.commit()
    goal_id = cursor.lastrowid
    connection.close()
    return goal_id

def get_all_goals() -> List[Dict[str, Any]]:
    with closing(get_connection()) as connection:
        rows = connection.execute("""
            SELECT g.id, g.title, g.description, g.status, g.category, g.created_at,
                   t.id, t.title, t.status, t.tag
            FROM goals g LEFT JOIN tasks t ON t.goal_id = g.id
            ORDER BY g.id DESC, t.id
        """).fetchall()

    goals = {}
    for goal_id, title, description, status, category, created_at, step_id, step_title, step_status, tag in rows:
        if goal_id not in goals:
            goals[goal_id] = {
                "id": goal_id, "title": title, "description": description or "",
                "status": status, "category": category or "estudio", "created_at": created_at or "",
                "total_steps": 0, "completed_steps": 0, "progress_percentage": 0, "steps": [],
            }
        goal = goals[goal_id]
        if step_id is not None:
            goal["steps"].append({"id": step_id, "title": step_title, "status": step_status, "tag": tag})
            goal["total_steps"] += 1
            goal["completed_steps"] += step_status == "completada"
    for goal in goals.values():
        if goal["total_steps"]:
            goal["progress_percentage"] = int(goal["completed_steps"] / goal["total_steps"] * 100)
    return list(goals.values())

def update_goal_status(goal_id: int, new_status: str) -> bool:
    connection = get_connection()
    cursor = connection.cursor()
    cursor.execute("UPDATE goals SET status = ? WHERE id = ?", (new_status, goal_id))
    connection.commit()
    affected = cursor.rowcount > 0
    connection.close()
    return affected

def delete_goal(goal_id: int) -> bool:
    connection = get_connection()
    cursor = connection.cursor()
    # Eliminar tareas hijas primero si no hay cascade activo
    cursor.execute("DELETE FROM tasks WHERE goal_id = ?", (goal_id,))
    cursor.execute("DELETE FROM goals WHERE id = ?", (goal_id,))
    connection.commit()
    affected = cursor.rowcount > 0
    connection.close()
    return affected
