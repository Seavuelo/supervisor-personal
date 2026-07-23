#Que informacion minima necesita una tarea?
#El identificador lo escribe el usuario o SQLite?
#Que estados puede tener?
#Que campos son obligatorios y cuales no?

from dataclasses import dataclass
from datetime import datetime

@dataclass
class Task:
    title: str
    description: str
    status: str = "pendiente"
  