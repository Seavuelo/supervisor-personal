from supervisor.models.task import Task 
from supervisor.database.schema import create_tables
from supervisor.repositories.task_repository import save_task

create_tables()

title = input("Escribe el titulo de la tarea: ").strip()

if title == "":
    print("El titulo no puede estar vacio")
else:
    description = input("Escribe la descripcion: ").strip()

my_task = Task(
    title=title,
    description=description
)



print("\nTarea creada")
print("Título:", my_task.title)
print("Descripcion:", my_task.description)
print("Estado:", my_task.status)

task_id = save_task(my_task)

print("\nTarea guardada correctamente")
print("Identificador: ", task_id)