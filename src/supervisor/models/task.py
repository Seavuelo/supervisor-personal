from dataclasses import dataclass, field
from calendar import monthrange
from datetime import date, datetime, timedelta
from typing import Optional

RECURRING = ("daily", "weekly", "monthly")


def occurrence_on_or_after(recurrence: str, anchor: str, start: date) -> Optional[date]:
    try:
        first = date.fromisoformat(anchor[:10])
    except ValueError:
        return None
    if first >= start:
        return first
    if recurrence == "daily":
        return start
    if recurrence == "weekly":
        return start + timedelta(days=(first.weekday() - start.weekday()) % 7)
    if recurrence == "monthly":
        day = min(first.day, monthrange(start.year, start.month)[1])
        if start.day <= day:
            return start.replace(day=day)
        next_month = start.replace(day=28) + timedelta(days=4)
        day = min(first.day, monthrange(next_month.year, next_month.month)[1])
        return next_month.replace(day=day)
    return None

@dataclass
class Task:
    title: str
    description: str = ""
    status: str = "pendiente"  # "pendiente" | "completada" | "no_lograda"
    scheduled_time: Optional[str] = None
    scheduled_date: Optional[str] = None
    task_type: str = "quick"  # "quick" | "appointment" | "micro_step" | "daily"
    tag: str = "Hoy"
    goal_id: Optional[int] = None
    recurrence: str = "none"
    is_priority: bool = False
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    id: Optional[int] = None
