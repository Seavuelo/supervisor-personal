from typing import List, Optional, Dict, Any
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
    connection = get_connection()
    cursor = connection.cursor()

    # Obtener metas junto con el conteo de pasos totales y completados
    cursor.execute("""
        SELECT 
            g.id, 
            g.title, 
            g.description, 
            g.status, 
            g.category, 
            g.created_at,
            COUNT(t.id) as total_steps,
            SUM(CASE WHEN t.status = 'completada' THEN 1 ELSE 0 END) as completed_steps
        FROM goals g
        LEFT JOIN tasks t ON t.goal_id = g.id
        GROUP BY g.id
        ORDER BY g.id DESC
    """)
    rows = cursor.fetchall()

    goals = []
    for row in rows:
        total = row[6] or 0
        completed = row[7] or 0
        percentage = int((completed / total) * 100) if total > 0 else 0

        # Obtener los micro-pasos asociados a esta meta
        cursor.execute("""
            SELECT id, title, status, tag
            FROM tasks
            WHERE goal_id = ?
            ORDER BY id ASC
        """, (row[0],))
        steps = [{"id": s[0], "title": s[1], "status": s[2], "tag": s[3]} for s in cursor.fetchall()]

        goals.append({
            "id": row[0],
            "title": row[1],
            "description": row[2] or "",
            "status": row[3],
            "category": row[4] or "estudio",
            "created_at": row[5] or "",
            "total_steps": total,
            "completed_steps": completed,
            "progress_percentage": percentage,
            "steps": steps
        })

    connection.close()
    return goals

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
