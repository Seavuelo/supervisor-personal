from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

@dataclass
class Goal:
    title: str
    description: str = ""
    status: str = "activa"  # "activa" | "completada" | "pausada"
    category: str = "estudio"  # "estudio" | "proyecto" | "hábito"
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    id: Optional[int] = None
    total_steps: int = 0
    completed_steps: int = 0

    @property
    def progress_percentage(self) -> int:
        if self.total_steps == 0:
            return 0
        return int((self.completed_steps / self.total_steps) * 100)
