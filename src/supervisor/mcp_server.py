#!/usr/bin/env python3
"""
Servidor MCP (Model Context Protocol) nativo para seeU.
Permite a agentes de IA externos (Claude Desktop, Cursor, Gemini Code Assist, Codex, etc.)
interactuar de forma estandarizada con las tareas, metas, ticks y calendario de seeU.
"""
import sys
import json
import logging
from datetime import datetime, date
from pathlib import Path
from typing import Dict, Any

# Inyectar el directorio src en sys.path
SRC_DIR = Path(__file__).resolve().parents[1]
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from supervisor.database.schema import create_tables
from supervisor.services.task_service import TaskService
from supervisor.services.goal_service import GoalService

logging.basicConfig(level=logging.ERROR, stream=sys.stderr)

TOOLS_METADATA = [
    {
        "name": "seeu_add_task",
        "description": "Anade una nueva tarea o compromiso al supervisor personal seeU.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "title": {"type": "string", "description": "Titulo de la actividad o pendiente"},
                "description": {"type": "string", "description": "Descripcion o contexto adicional opcional"},
                "scheduled_date": {"type": "string", "description": "Fecha programada en formato YYYY-MM-DD. Omitir para Foco de hoy sin fecha fija."},
                "scheduled_time": {"type": "string", "description": "Hora de la cita en formato HH:MM (ej: 15:30)"},
                "tag": {"type": "string", "description": "Etiqueta visual (ej: Hoy, Agenda, Examen, Diaria)"},
                "is_priority": {"type": "boolean", "description": "Si la actividad debe marcarse con estrella prioritaria"},
                "recurrence": {"type": "string", "enum": ["none", "daily", "weekly"], "description": "Recurrencia (usar 'daily' para habitos diarios)"}
            },
            "required": ["title"]
        }
    },
    {
        "name": "seeu_create_plan",
        "description": "Crea un plan estructurado o meta en seeU con una serie de micro-pasos de baja friccion para evitar la sobrecarga cognitiva.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "title": {"type": "string", "description": "Titulo general del plan o proyecto"},
                "description": {"type": "string", "description": "Explicacion breve del objetivo"},
                "category": {"type": "string", "description": "Categoria (estudio, personal, proyecto, trabajo)", "default": "estudio"},
                "steps": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Lista secuencial de micro-pasos alcanzables (ej: ['Revisar capitulo 1 (25 min)', 'Hacer 3 ejercicios', 'Resumen'] )"
                }
            },
            "required": ["title", "steps"]
        }
    },
    {
        "name": "seeu_list_tasks",
        "description": "Consulta las tareas registradas en seeU con opciones de filtrado por estado, fecha, mes o prioridad.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "today_only": {"type": "boolean", "description": "Filtrar unicamente las tareas activas para el dia de hoy"},
                "date": {"type": "string", "description": "Filtrar por fecha exacta (YYYY-MM-DD)"},
                "month": {"type": "string", "description": "Filtrar por mes completo (YYYY-MM)"},
                "status": {"type": "string", "enum": ["todas", "pendiente", "completada"], "default": "todas"},
                "priority_only": {"type": "boolean", "description": "Filtrar unicamente tareas con estrella de prioridad"}
            }
        }
    },
    {
        "name": "seeu_toggle_tick",
        "description": "Marca o desmarca el 'tick' de una tarea (alterna entre completada y pendiente).",
        "inputSchema": {
            "type": "object",
            "properties": {
                "task_id": {"type": "integer", "description": "ID numerico de la tarea a marcar"}
            },
            "required": ["task_id"]
        }
    },
    {
        "name": "seeu_get_monthly_overview",
        "description": "Obtiene la radiografia completa del mes: dias con actividad, ticks completados, tareas pendientes y porcentaje de efectividad.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "month": {"type": "string", "description": "Mes a consultar en formato YYYY-MM (ej: '2026-11'). Si se omite se usa el mes actual."}
            }
        }
    },
    {
        "name": "seeu_get_stats",
        "description": "Obtiene las metricas globales de seeU: total de ticks conseguidos, pendientes, metas activas y consistencia acumulada.",
        "inputSchema": {
            "type": "object",
            "properties": {}
        }
    }
]

def execute_tool(name: str, arguments: Dict[str, Any]) -> str:
    create_tables()
    task_service = TaskService()
    goal_service = GoalService()

    if name == "seeu_add_task":
        title = arguments.get("title", "")
        desc = arguments.get("description", "")
        s_date = arguments.get("scheduled_date")
        s_time = arguments.get("scheduled_time")
        tag = arguments.get("tag", "Hoy" if not s_date else "Agenda")
        is_prio = bool(arguments.get("is_priority", False))
        recurrence = arguments.get("recurrence", "none")
        t_type = "daily" if recurrence == "daily" else ("appointment" if s_time else "quick")

        task = task_service.create_task(
            title=title,
            description=desc,
            scheduled_date=s_date,
            scheduled_time=s_time,
            tag=tag,
            task_type=t_type,
            is_priority=is_prio,
            recurrence=recurrence
        )
        return json.dumps({"status": "success", "message": f"Tarea #{task['id']} anadida a seeU", "task": task}, ensure_ascii=False)

    elif name == "seeu_create_plan":
        title = arguments.get("title", "")
        desc = arguments.get("description", "")
        category = arguments.get("category", "estudio")
        steps = arguments.get("steps", [])

        goal = goal_service.create_goal(title=title, description=desc, category=category)
        created_steps = []
        for st in steps:
            s_obj = goal_service.add_step_to_goal(goal["id"], st, duration_tag="25 min")
            created_steps.append(s_obj)

        goal["steps"] = created_steps
        goal["total_steps"] = len(created_steps)
        return json.dumps({"status": "success", "message": f"Plan #{goal['id']} creado con {len(created_steps)} micro-pasos", "plan": goal}, ensure_ascii=False)

    elif name == "seeu_list_tasks":
        month = arguments.get("month")
        if month:
            tasks = task_service.get_tasks_by_month(month)
        else:
            tasks = task_service.get_all_tasks()

        from datetime import date
        today_str = date.today().strftime("%Y-%m-%d")

        if arguments.get("today_only"):
            tasks = [t for t in tasks if t.get("scheduled_date") == today_str or t.get("recurrence") == "daily" or (not t.get("scheduled_date") and t.get("tag") == "Hoy")]
        elif arguments.get("date"):
            d_filter = arguments["date"]
            tasks = [t for t in tasks if t.get("scheduled_date") == d_filter or t.get("recurrence") == "daily"]

        status = arguments.get("status", "todas")
        if status in ("pendiente", "completada"):
            tasks = [t for t in tasks if t.get("status") == status]

        if arguments.get("priority_only"):
            tasks = [t for t in tasks if t.get("is_priority")]

        return json.dumps({"total": len(tasks), "tasks": tasks}, ensure_ascii=False)

    elif name == "seeu_toggle_tick":
        task_id = arguments.get("task_id")
        if not task_id:
            return json.dumps({"status": "error", "message": "Falta el parametro task_id"})
        new_status = task_service.toggle_task(int(task_id))
        if not new_status:
            return json.dumps({"status": "error", "message": f"No se encontro la tarea #{task_id}"})
        return json.dumps({"status": "success", "task_id": task_id, "new_status": new_status})

    elif name == "seeu_get_monthly_overview":
        month = arguments.get("month") or datetime.now().strftime("%Y-%m")
        summary = task_service.get_monthly_summary(month)
        return json.dumps(summary, ensure_ascii=False)

    elif name == "seeu_get_stats":
        stats = task_service.get_overall_stats()
        return json.dumps(stats, ensure_ascii=False)

    else:
        return json.dumps({"status": "error", "message": f"Herramienta desconocida: {name}"})

def start_mcp_server():
    create_tables()
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            req = json.loads(line)
        except Exception:
            continue

        req_id = req.get("id")
        method = req.get("method")

        if method == "initialize":
            res = {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "protocolVersion": "2024-11-05",
                    "serverInfo": {
                        "name": "seeU-mcp-server",
                        "version": "1.0.0"
                    },
                    "capabilities": {
                        "tools": {}
                    }
                }
            }
            sys.stdout.write(json.dumps(res) + "\n")
            sys.stdout.flush()

        elif method == "notifications/initialized":
            pass

        elif method == "tools/list":
            res = {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "tools": TOOLS_METADATA
                }
            }
            sys.stdout.write(json.dumps(res) + "\n")
            sys.stdout.flush()

        elif method == "tools/call":
            params = req.get("params", {})
            name = params.get("name")
            args = params.get("arguments", {})
            output_text = execute_tool(name, args)
            res = {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "content": [
                        {
                            "type": "text",
                            "text": output_text
                        }
                    ]
                }
            }
            sys.stdout.write(json.dumps(res) + "\n")
            sys.stdout.flush()

        elif req_id is not None:
            # Metodo no soportado
            res = {
                "jsonrpc": "2.0",
                "id": req_id,
                "error": {
                    "code": -32601,
                    "message": f"Metodo no implementado: {method}"
                }
            }
            sys.stdout.write(json.dumps(res) + "\n")
            sys.stdout.flush()

def main():
    start_mcp_server()

if __name__ == "__main__":
    main()
