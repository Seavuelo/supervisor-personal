#!/usr/bin/env python3
"""
CLI de seeU: Interfaz de linea de comandos para usuarios y agentes de IA externos.
Permite anadir tareas, gestionar ticks, crear planes de estudio y consultar
actividades mensuales en formato humano o JSON estructurado.
"""
import sys
import json
import argparse
from datetime import datetime, date
from pathlib import Path

# Inyectar el directorio src en sys.path
SRC_DIR = Path(__file__).resolve().parents[1]
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from supervisor.database.schema import create_tables
from supervisor.services.task_service import TaskService
from supervisor.services.goal_service import GoalService

def _ensure_db():
    create_tables()

def handle_task_add(args):
    _ensure_db()
    service = TaskService()
    
    date_val = args.date
    tag_val = args.tag
    if args.today and not date_val:
        date_val = date.today().strftime("%Y-%m-%d")
        if not tag_val:
            tag_val = "Hoy"
    elif not tag_val:
        tag_val = "Agenda" if date_val else "Hoy"

    recurrence = "daily" if args.daily else "none"
    task = service.create_task(
        title=args.title,
        description=args.desc or "",
        scheduled_date=date_val,
        scheduled_time=args.time,
        tag=tag_val,
        task_type="daily" if args.daily else ("appointment" if args.time else "quick"),
        is_priority=args.priority,
        recurrence=recurrence
    )

    if args.json:
        print(json.dumps(task, indent=2, ensure_ascii=False))
    else:
        p_badge = "[* Prioritaria] " if task.get("is_priority") else ""
        d_info = f" ({task.get('scheduled_date')})" if task.get("scheduled_date") else ""
        t_info = f" a las {task.get('scheduled_time')}" if task.get("scheduled_time") else ""
        print(f"seeU: Tarea #{task['id']} agregada: {p_badge}'{task['title']}'{d_info}{t_info}")

def handle_task_list(args):
    _ensure_db()
    service = TaskService()
    
    if args.month:
        tasks = service.get_tasks_by_month(args.month)
    else:
        tasks = service.get_all_tasks()

    today_str = date.today().strftime("%Y-%m-%d")

    # Filtros
    if args.today:
        tasks = [t for t in tasks if t.get("scheduled_date") == today_str or t.get("recurrence") == "daily" or (not t.get("scheduled_date") and t.get("tag") == "Hoy")]
    elif args.date:
        tasks = [t for t in tasks if t.get("scheduled_date") == args.date or t.get("recurrence") == "daily"]

    if args.pending:
        tasks = [t for t in tasks if t.get("status") == "pendiente"]
    elif args.completed:
        tasks = [t for t in tasks if t.get("status") == "completada"]

    if args.priority:
        tasks = [t for t in tasks if t.get("is_priority")]

    if args.json:
        print(json.dumps(tasks, indent=2, ensure_ascii=False))
        return

    if not tasks:
        print("seeU: No hay tareas que coincidan con el filtro.")
        return

    print(f"\n--- seeU: Lista de Tareas ({len(tasks)}) ---")
    for t in tasks:
        tick = "[x]" if t.get("status") == "completada" else "[ ]"
        star = "*" if t.get("is_priority") else " "
        t_id = f"#{t['id']:<3}"
        date_col = t.get("scheduled_date") or "Sin fecha"
        time_col = f" {t.get('scheduled_time')}" if t.get("scheduled_time") else ""
        tag_col = f"[{t.get('tag')}]" if t.get("tag") else ""
        print(f"{tick} {star} {t_id} {t['title']} {tag_col} ({date_col}{time_col})")
    print("------------------------------------------\n")

def handle_task_tick(args):
    _ensure_db()
    service = TaskService()
    new_status = service.toggle_task(args.id)
    if not new_status:
        print(f"seeU: No se encontro la tarea #{args.id}", file=sys.stderr)
        sys.exit(1)

    if args.json:
        print(json.dumps({"id": args.id, "status": new_status}))
    else:
        simbolo = "[x] Completada" if new_status == "completada" else "[ ] Pendiente"
        print(f"seeU: Tarea #{args.id} marcada como: {simbolo}")

def handle_task_done(args):
    _ensure_db()
    service = TaskService()
    ok = service.set_task_status(args.id, "completada")
    if not ok:
        print(f"seeU: No se encontro la tarea #{args.id}", file=sys.stderr)
        sys.exit(1)

    if args.json:
        print(json.dumps({"id": args.id, "status": "completada"}))
    else:
        print(f"seeU: Tarea #{args.id} marcada como completada [x]")

def handle_task_undone(args):
    _ensure_db()
    service = TaskService()
    ok = service.set_task_status(args.id, "pendiente")
    if not ok:
        print(f"seeU: No se encontro la tarea #{args.id}", file=sys.stderr)
        sys.exit(1)

    if args.json:
        print(json.dumps({"id": args.id, "status": "pendiente"}))
    else:
        print(f"seeU: Tarea #{args.id} marcada como pendiente [ ]")

def handle_task_delete(args):
    _ensure_db()
    service = TaskService()
    ok = service.delete_task(args.id)
    if not ok:
        print(f"seeU: No se pudo eliminar la tarea #{args.id}", file=sys.stderr)
        sys.exit(1)

    if args.json:
        print(json.dumps({"id": args.id, "deleted": True}))
    else:
        print(f"seeU: Tarea #{args.id} eliminada.")

def handle_plan_create(args):
    _ensure_db()
    goal_service = GoalService()
    
    goal = goal_service.create_goal(
        title=args.title,
        description=args.desc or "",
        category=args.category or "estudio"
    )

    steps_list = []
    if args.steps:
        # Permite separar por comas o saltos de linea
        raw_steps = [s.strip() for s in args.steps.replace(";", ",").split(",") if s.strip()]
        for idx, step_title in enumerate(raw_steps, 1):
            s = goal_service.add_step_to_goal(goal["id"], step_title, duration_tag="25 min")
            steps_list.append(s)

    goal["steps"] = steps_list
    goal["total_steps"] = len(steps_list)

    if args.json:
        print(json.dumps(goal, indent=2, ensure_ascii=False))
    else:
        print(f"\nseeU: Plan #{goal['id']} creado: '{goal['title']}'")
        if steps_list:
            print("Micro-pasos programados:")
            for idx, st in enumerate(steps_list, 1):
                print(f"  {idx}. [ ] #{st['id']} {st['title']} ({st.get('tag')})")
        print()

def handle_goal_list(args):
    _ensure_db()
    service = GoalService()
    goals = service.get_all_goals()
    if args.json:
        print(json.dumps(goals, indent=2, ensure_ascii=False))
    else:
        if not goals:
            print("seeU: No hay metas registradas.")
            return
        print(f"\n--- seeU: Metas y Proyectos ({len(goals)}) ---")
        for g in goals:
            prog = f"{g['completed_steps']}/{g['total_steps']} pasos ({g['progress_percentage']}%)"
            print(f"#{g['id']:<3} {g['title']} [{g['category']}] - {prog}")
            for st in g.get("steps", []):
                t_mark = "[x]" if st.get("status") == "completada" else "[ ]"
                print(f"     {t_mark} #{st['id']} {st['title']}")
        print("------------------------------------------\n")

def handle_month_view(args):
    _ensure_db()
    service = TaskService()
    
    target_month = args.month or datetime.now().strftime("%Y-%m")
    summary = service.get_monthly_summary(target_month)

    if args.json:
        print(json.dumps(summary, indent=2, ensure_ascii=False))
        return

    print(f"\n==================================================")
    print(f"   seeU: Resumen Mensual - {summary['month_name']} {summary['year']}")
    print(f"==================================================")
    print(f"Total actividades : {summary['total_tasks']}")
    print(f"Ticks completados : {summary['completed_ticks']} [x]")
    print(f"Pendientes        : {summary['pending_tasks']} [ ]")
    print(f"Tasa de exito     : {summary['completion_rate_percent']}%")
    print(f"--------------------------------------------------")
    print(f"Dia   Fecha        Ticks hechos   Pendientes")
    print(f"--------------------------------------------------")
    for d in summary["days"]:
        if d["has_activity"]:
            bar = "[x]" * d["completed_ticks"] + "[ ]" * d["pending"]
            print(f"{d['weekday_short']} {d['day']:02d}  {d['date']}   {d['completed_ticks']:<12}   {d['pending']:<10} {bar}")
    print(f"==================================================\n")

def handle_stats(args):
    _ensure_db()
    service = TaskService()
    stats = service.get_overall_stats()
    if args.json:
        print(json.dumps(stats, indent=2, ensure_ascii=False))
    else:
        print(f"\n--- seeU: Estadisticas Globales ---")
        print(f"Total de tareas registradas : {stats['total_tasks']}")
        print(f"Ticks completados [x]       : {stats['completed_ticks']}")
        print(f"Tareas pendientes [ ]       : {stats['pending_tasks']}")
        print(f"Prioritarias pendientes [*] : {stats['priority_pending']}")
        print(f"Metas activas               : {stats['active_goals']}")
        print(f"Metas completadas           : {stats['completed_goals']}")
        print(f"Efectividad acumulada       : {stats['completion_rate_percent']}%")
        print(f"-----------------------------------\n")

def handle_mcp(args):
    from supervisor.mcp_server import start_mcp_server
    start_mcp_server()

def handle_gui(args):
    from supervisor.main import main as start_gui_app
    start_gui_app()

def build_parser():
    parser = argparse.ArgumentParser(
        prog="seeu",
        description="seeU: Supervisor personal y asistente anti-sobrecarga cognitiva para desarrolladores y agentes de IA"
    )
    subparsers = parser.add_subparsers(dest="subcommand", help="Comandos disponibles")

    # GUI
    p_gui = subparsers.add_parser("gui", help="Iniciar la aplicacion grafica de escritorio seeU")
    p_gui.set_defaults(func=handle_gui)

    # MCP Server
    p_mcp = subparsers.add_parser("mcp", help="Iniciar el servidor Model Context Protocol (MCP) para agentes de IA")
    p_mcp.set_defaults(func=handle_mcp)

    # TASKS
    p_task = subparsers.add_parser("task", help="Gestionar tareas individuales")
    task_sub = p_task.add_subparsers(dest="task_action")

    # task add
    p_t_add = task_sub.add_parser("add", help="Anadir una nueva tarea")
    p_t_add.add_argument("title", help="Titulo de la tarea")
    p_t_add.add_argument("--desc", help="Descripcion opcional")
    p_t_add.add_argument("--date", help="Fecha programada (YYYY-MM-DD)")
    p_t_add.add_argument("--time", help="Hora programada (HH:MM)")
    p_t_add.add_argument("--today", action="store_true", help="Programar para hoy")
    p_t_add.add_argument("--tag", help="Etiqueta visual (ej: Hoy, Agenda, Examen)")
    p_t_add.add_argument("--priority", action="store_true", help="Marcar con estrella prioritaria")
    p_t_add.add_argument("--daily", action="store_true", help="Definir como habito recurrente diario")
    p_t_add.add_argument("--json", action="store_true", help="Salida en formato JSON estructurado")
    p_t_add.set_defaults(func=handle_task_add)

    # task list
    p_t_list = task_sub.add_parser("list", help="Listar tareas")
    p_t_list.add_argument("--today", action="store_true", help="Solo tareas de hoy")
    p_t_list.add_argument("--date", help="Filtrar por fecha exacta (YYYY-MM-DD)")
    p_t_list.add_argument("--month", help="Filtrar por mes (YYYY-MM)")
    p_t_list.add_argument("--pending", action="store_true", help="Solo pendientes")
    p_t_list.add_argument("--completed", action="store_true", help="Solo completadas (ticks)")
    p_t_list.add_argument("--priority", action="store_true", help="Solo prioritarias")
    p_t_list.add_argument("--json", action="store_true", help="Salida en formato JSON")
    p_t_list.set_defaults(func=handle_task_list)

    # task tick / done / undone / delete
    p_t_tick = task_sub.add_parser("tick", help="Alternar estado de tarea (pendiente/completada)")
    p_t_tick.add_argument("id", type=int, help="ID de la tarea")
    p_t_tick.add_argument("--json", action="store_true")
    p_t_tick.set_defaults(func=handle_task_tick)

    p_t_done = task_sub.add_parser("done", help="Marcar tarea como completada")
    p_t_done.add_argument("id", type=int, help="ID de la tarea")
    p_t_done.add_argument("--json", action="store_true")
    p_t_done.set_defaults(func=handle_task_done)

    p_t_undone = task_sub.add_parser("undone", help="Marcar tarea como pendiente")
    p_t_undone.add_argument("id", type=int, help="ID de la tarea")
    p_t_undone.add_argument("--json", action="store_true")
    p_t_undone.set_defaults(func=handle_task_undone)

    p_t_del = task_sub.add_parser("delete", help="Eliminar tarea")
    p_t_del.add_argument("id", type=int, help="ID de la tarea")
    p_t_del.add_argument("--json", action="store_true")
    p_t_del.set_defaults(func=handle_task_delete)

    # PLAN / GOAL
    p_plan = subparsers.add_parser("plan", help="Crear un plan de estudio o proyecto con micro-pasos")
    p_plan.add_argument("title", help="Titulo del objetivo")
    p_plan.add_argument("--steps", help="Micro-pasos separados por coma (ej: 'Paso 1, Paso 2, Paso 3')")
    p_plan.add_argument("--desc", help="Descripcion del plan")
    p_plan.add_argument("--category", default="estudio", help="Categoria (estudio, personal, proyecto)")
    p_plan.add_argument("--json", action="store_true")
    p_plan.set_defaults(func=handle_plan_create)

    p_goal = subparsers.add_parser("goal", help="Consultar o gestionar metas")
    goal_sub = p_goal.add_subparsers(dest="goal_action")
    p_g_list = goal_sub.add_parser("list", help="Listar metas con sus micro-pasos")
    p_g_list.add_argument("--json", action="store_true")
    p_g_list.set_defaults(func=handle_goal_list)

    # MONTH
    p_month = subparsers.add_parser("month", help="Ver resumen y actividades por mes")
    p_month.add_argument("month", nargs="?", help="Mes en formato YYYY-MM (por defecto el mes actual)")
    p_month.add_argument("--json", action="store_true")
    p_month.set_defaults(func=handle_month_view)

    # STATS
    p_stats = subparsers.add_parser("stats", help="Estadisticas de consistencia y ticks")
    p_stats.add_argument("--json", action="store_true")
    p_stats.set_defaults(func=handle_stats)

    return parser

def main():
    parser = build_parser()
    if len(sys.argv) == 1:
        parser.print_help()
        sys.exit(0)

    args = parser.parse_args()
    if hasattr(args, "func"):
        args.func(args)
    else:
        parser.print_help()

if __name__ == "__main__":
    main()
