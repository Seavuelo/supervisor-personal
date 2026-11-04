from typing import List, Dict, Any, Optional
from supervisor.models.goal import Goal
from supervisor.models.task import Task
from supervisor.repositories import goal_repository, task_repository

class GoalService:
    @staticmethod
    def get_all_goals() -> List[Dict[str, Any]]:
        return goal_repository.get_all_goals()

    @staticmethod
    def create_goal(title: str, description: str = "", category: str = "estudio") -> Dict[str, Any]:
        goal = Goal(
            title=title.strip(),
            description=description.strip(),
            category=category,
        )
        goal_id = goal_repository.save_goal(goal)
        goal.id = goal_id
        return {
            "id": goal.id,
            "title": goal.title,
            "description": goal.description,
            "status": goal.status,
            "category": goal.category,
            "created_at": goal.created_at,
            "total_steps": 0,
            "completed_steps": 0,
            "progress_percentage": 0,
            "steps": [],
        }

    @staticmethod
    def add_step_to_goal(goal_id: int, step_title: str, duration_tag: str = "25 min") -> Dict[str, Any]:
        task = Task(
            title=step_title.strip(),
            task_type="micro_step",
            tag=duration_tag,
            goal_id=goal_id,
        )
        task_id = task_repository.save_task(task)
        task.id = task_id
        return {
            "id": task.id,
            "title": task.title,
            "status": task.status,
            "tag": task.tag,
            "goal_id": task.goal_id,
        }

    @staticmethod
    def delete_goal(goal_id: int) -> bool:
        return goal_repository.delete_goal(goal_id)
