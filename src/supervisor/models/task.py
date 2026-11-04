from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

@dataclass
class Task:
    title: str
    description: str = ""
    status: str = "pendiente"  # "pendiente" | "completada"
    scheduled_time: Optional[str] = None
    scheduled_date: Optional[str] = None
    task_type: str = "quick"  # "quick" | "appointment" | "micro_step"
    tag: str = "Hoy"
    goal_id: Optional[int] = None
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    id: Optional[int] = None
