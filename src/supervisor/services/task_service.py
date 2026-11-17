from dataclasses import asdict
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any
from supervisor.models.task import Task
from supervisor.repositories import task_repository

class TaskService:
    @staticmethod
    def get_all_tasks() -> List[Dict[str, Any]]:
        return [asdict(task) for task in task_repository.get_all_tasks()]

    @staticmethod
    def create_task(
        title: str,
        description: str = "",
        scheduled_time: Optional[str] = None,
        scheduled_date: Optional[str] = None,
        task_type: str = "quick",
        tag: str = "Hoy",
        goal_id: Optional[int] = None,
        recurrence: str = "none",
        is_priority: bool = False,
    ) -> Dict[str, Any]:
        task = Task(
            title=title.strip(),
            description=description.strip(),
            scheduled_time=scheduled_time,
            scheduled_date=scheduled_date,
            task_type=task_type,
            tag=tag,
            goal_id=goal_id,
            recurrence=recurrence,
            is_priority=is_priority,
        )
        task_id = task_repository.save_task(task)
        task.id = task_id
        return asdict(task)

    @staticmethod
    def toggle_priority(task_id: int) -> bool:
        return task_repository.toggle_task_priority(task_id)

    @staticmethod
    def get_overdue_tasks() -> List[Dict[str, Any]]:
        today_str = datetime.now().strftime("%Y-%m-%d")
        return task_repository.get_overdue_tasks(today_str)

    @staticmethod
    def postpone_all_overdue() -> int:
        today_str = datetime.now().strftime("%Y-%m-%d")
        return task_repository.postpone_all_overdue(today_str, today_str)

    @staticmethod
    def dismiss_all_overdue() -> int:
        today_str = datetime.now().strftime("%Y-%m-%d")
        return task_repository.dismiss_all_overdue(today_str)

    @staticmethod
    def get_weekly_heatmap() -> List[Dict[str, Any]]:
        now = datetime.now()
        start_of_week = now - timedelta(days=now.weekday())
        day_chars = ["L", "M", "M", "J", "V", "S", "D"]
        day_names = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"]

        dates = [(start_of_week + timedelta(days=i)).strftime("%Y-%m-%d") for i in range(7)]
        counts = task_repository.get_task_counts_per_date(dates)

        result = []
        for i in range(7):
            d_date = dates[i]
            d_dt = start_of_week + timedelta(days=i)
            c = counts.get(d_date, 0)

            if c == 0:
                intensity = 0
            elif c <= 2:
                intensity = 1
            elif c <= 5:
                intensity = 2
            else:
                intensity = 3

            result.append({
                "char": day_chars[i],
                "name": day_names[i],
                "date": d_date,
                "day_num": d_dt.day,
                "count": c,
                "intensity": intensity,
                "is_today": (d_date == now.strftime("%Y-%m-%d")),
            })

        return result

    @staticmethod
    def toggle_task(task_id: int) -> Optional[str]:
        return task_repository.toggle_task_status(task_id)

    @staticmethod
    def set_task_status(task_id: int, status: str) -> bool:
        return task_repository.set_task_status(task_id, status)

    @staticmethod
    def delete_task(task_id: int) -> bool:
        return task_repository.delete_task(task_id)

    @staticmethod
    def get_tasks_by_month(year_month: str) -> List[Dict[str, Any]]:
        tasks = task_repository.get_tasks_by_month(year_month)
        return [asdict(t) for t in tasks]

    @staticmethod
    def get_monthly_summary(year_month: str) -> Dict[str, Any]:
        return task_repository.get_monthly_summary(year_month)

    @staticmethod
    def get_overall_stats() -> Dict[str, Any]:
        return task_repository.get_overall_stats()
