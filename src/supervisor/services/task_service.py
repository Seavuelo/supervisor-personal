from typing import List, Optional, Dict, Any
from supervisor.models.task import Task
from supervisor.repositories import task_repository

class TaskService:
    @staticmethod
    def get_all_tasks() -> List[Dict[str, Any]]:
        tasks = task_repository.get_all_tasks()
        return [
            {
                "id": t.id,
                "title": t.title,
                "description": t.description,
                "status": t.status,
                "scheduled_time": t.scheduled_time,
                "scheduled_date": t.scheduled_date,
                "task_type": t.task_type,
                "tag": t.tag,
                "goal_id": t.goal_id,
                "created_at": t.created_at,
            }
            for t in tasks
        ]

    @staticmethod
    def create_task(
        title: str,
        description: str = "",
        scheduled_time: Optional[str] = None,
        scheduled_date: Optional[str] = None,
        task_type: str = "quick",
        tag: str = "Hoy",
        goal_id: Optional[int] = None,
    ) -> Dict[str, Any]:
        task = Task(
            title=title.strip(),
            description=description.strip(),
            scheduled_time=scheduled_time,
            scheduled_date=scheduled_date,
            task_type=task_type,
            tag=tag,
            goal_id=goal_id,
        )
        task_id = task_repository.save_task(task)
        task.id = task_id
        return {
            "id": task.id,
            "title": task.title,
            "description": task.description,
            "status": task.status,
            "scheduled_time": task.scheduled_time,
            "scheduled_date": task.scheduled_date,
            "task_type": task.task_type,
            "tag": task.tag,
            "goal_id": task.goal_id,
            "created_at": task.created_at,
        }

    @staticmethod
    def toggle_task(task_id: int) -> Optional[str]:
        return task_repository.toggle_task_status(task_id)

    @staticmethod
    def delete_task(task_id: int) -> bool:
        return task_repository.delete_task(task_id)
