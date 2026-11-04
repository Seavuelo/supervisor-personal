import unittest
import os
import json
import tempfile
import sqlite3
from datetime import datetime, date, timedelta
from pathlib import Path

# Ajustar PYTHONPATH
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from supervisor.models.task import Task
from supervisor.database import schema, connection
from supervisor.repositories import task_repository, settings_repository
from supervisor.services.task_service import TaskService
from supervisor.ui.main_window import seeU_API

class TestSeeUCore(unittest.TestCase):
    def setUp(self):
        # Crear base de datos temporal para pruebas aisladas
        self.temp_db = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.temp_db.close()
        self.original_db_path = connection.DATABASE_PATH
        connection.DATABASE_PATH = Path(self.temp_db.name)
        schema.create_tables()

    def tearDown(self):
        connection.DATABASE_PATH = self.original_db_path
        if os.path.exists(self.temp_db.name):
            os.remove(self.temp_db.name)

    def test_task_priority_and_toggle(self):
        service = TaskService()
        task = service.create_task(title="Revisar tesis de computación", tag="Hoy", is_priority=False)
        self.assertFalse(task["is_priority"])

        # Alternar a prioritario
        new_priority = service.toggle_priority(task["id"])
        self.assertTrue(new_priority)

        all_tasks = service.get_all_tasks()
        self.assertEqual(len(all_tasks), 1)
        self.assertTrue(all_tasks[0]["is_priority"])

        # Alternar de vuelta
        new_priority2 = service.toggle_priority(task["id"])
        self.assertFalse(new_priority2)

    def test_overdue_tasks_postpone_and_dismiss(self):
        service = TaskService()
        ayer = (date.today() - timedelta(days=1)).strftime("%Y-%m-%d")
        hoy = date.today().strftime("%Y-%m-%d")

        # Tarea de ayer pendiente
        service.create_task(title="Comprar insumos", scheduled_date=ayer, tag="Ayer")
        # Tarea de hoy
        service.create_task(title="Dentista", scheduled_date=hoy, tag="Hoy")

        # Verificar detección de atrasadas
        overdue = service.get_overdue_tasks()
        self.assertEqual(len(overdue), 1)
        self.assertEqual(overdue[0]["title"], "Comprar insumos")

        # Posponer todas para hoy
        service.postpone_all_overdue()
        overdue_after = service.get_overdue_tasks()
        self.assertEqual(len(overdue_after), 0)

        # Verificar que ahora está programada para hoy
        all_tasks = service.get_all_tasks()
        postponed_task = next(t for t in all_tasks if t["title"] == "Comprar insumos")
        self.assertEqual(postponed_task["scheduled_date"], hoy)
        self.assertEqual(postponed_task["tag"], "Hoy")

        # Probar descarte
        antier = (date.today() - timedelta(days=2)).strftime("%Y-%m-%d")
        service.create_task(title="Entrenamiento viejo", scheduled_date=antier, tag="Antier")
        self.assertEqual(len(service.get_overdue_tasks()), 1)

        service.dismiss_all_overdue()
        self.assertEqual(len(service.get_overdue_tasks()), 0)
        dismissed_task = next(t for t in service.get_all_tasks() if t["title"] == "Entrenamiento viejo")
        self.assertEqual(dismissed_task["status"], "no_lograda")

    def test_weekly_heatmap_calculation(self):
        service = TaskService()
        hoy = date.today().strftime("%Y-%m-%d")

        # Crear 3 tareas hoy
        service.create_task(title="Tarea 1", scheduled_date=hoy)
        service.create_task(title="Tarea 2", scheduled_date=hoy)
        service.create_task(title="Tarea 3", scheduled_date=hoy)

        heatmap = service.get_weekly_heatmap()
        self.assertEqual(len(heatmap), 7)

        today_item = next(d for d in heatmap if d["is_today"])
        self.assertEqual(today_item["count"], 3)
        self.assertEqual(today_item["intensity"], 2)  # 3 tareas -> nivel 2

    def test_ai_service_daily_habit_and_memory(self):
        from supervisor.services.ai_service import AIService
        ai = AIService()
        ai.client = None # Forzar motor autónomo para testing local sin consumir cuota

        # 1. Hábito diario
        res = ai.process_input("Hacer ejercicio todos los días")
        self.assertEqual(res["action"], "quick_task")
        self.assertEqual(len(res["tasks"]), 1)
        self.assertEqual(res["tasks"][0]["recurrence"], "daily")
        self.assertEqual(res["tasks"][0]["tag"], "Diaria")

        # 2. Memoria de conversación: "Mañana tengo doctor" -> pregunta hora
        res2 = ai.process_input("Mañana tengo doctor")
        self.assertEqual(res2["action"], "question")
        self.assertIn("hora", res2["message"].lower())

        # 3. Respuesta a la hora: "A las 15:30" -> agenda para mañana
        res3 = ai.process_input("A las 15:30")
        self.assertEqual(res3["action"], "scheduled_task")
        self.assertEqual(res3["tasks"][0]["scheduled_time"], "15:30")

    def test_autostart_toggle(self):
        api = seeU_API()
        desktop_file = Path.home() / ".config" / "autostart" / "seeU.desktop"

        try:
            # Activar autostart
            status_on = api.set_autostart(True)
            self.assertTrue(status_on)
            self.assertTrue(desktop_file.exists())
            self.assertTrue(api.get_autostart_status())

            # Desactivar autostart
            status_off = api.set_autostart(False)
            self.assertFalse(status_off)
            self.assertFalse(desktop_file.exists())
            self.assertFalse(api.get_autostart_status())
        finally:
            if desktop_file.exists():
                desktop_file.unlink()

    def test_monthly_summary_and_stats(self):
        service = TaskService()
        hoy = date.today().strftime("%Y-%m-%d")
        mes_actual = date.today().strftime("%Y-%m")

        # Crear 2 tareas pendientes y 1 completada
        t1 = service.create_task(title="Tarea 1", scheduled_date=hoy)
        t2 = service.create_task(title="Tarea 2", scheduled_date=hoy)
        t3 = service.create_task(title="Tarea 3", scheduled_date=hoy)

        # Completar t1
        service.toggle_task(t1["id"])

        summary = service.get_monthly_summary(mes_actual)
        self.assertEqual(summary["year_month"], mes_actual)
        self.assertEqual(summary["completed_ticks"], 1)
        self.assertEqual(summary["pending_tasks"], 2)
        self.assertEqual(summary["total_tasks"], 3)
        self.assertGreater(len(summary["days"]), 27)

        stats = service.get_overall_stats()
        self.assertEqual(stats["completed_ticks"], 1)
        self.assertEqual(stats["pending_tasks"], 2)

    def test_mcp_server_tools_execution(self):
        from supervisor.mcp_server import execute_tool
        
        # 1. Anadir tarea por MCP
        res_raw = execute_tool("seeu_add_task", {
            "title": "Estudiar grafos para el certamen",
            "tag": "Estudio",
            "is_priority": True
        })
        res = json.loads(res_raw)
        self.assertEqual(res["status"], "success")
        t_id = res["task"]["id"]
        self.assertTrue(res["task"]["is_priority"])

        # 2. Alternar tick por MCP
        tick_raw = execute_tool("seeu_toggle_tick", {"task_id": t_id})
        tick_res = json.loads(tick_raw)
        self.assertEqual(tick_res["status"], "success")
        self.assertEqual(tick_res["new_status"], "completada")

        # 3. Crear plan de estudio con micro-pasos
        plan_raw = execute_tool("seeu_create_plan", {
            "title": "Preparar examen de algoritmos",
            "steps": ["Repasar Dijkstra", "Resolver 3 ejercicios", "Descanso 5 min"]
        })
        plan_res = json.loads(plan_raw)
        self.assertEqual(plan_res["status"], "success")
        self.assertEqual(plan_res["plan"]["total_steps"], 3)

        # 4. Obtener resumen mensual por MCP
        month_raw = execute_tool("seeu_get_monthly_overview", {})
        month_res = json.loads(month_raw)
        self.assertIn("completed_ticks", month_res)
        self.assertGreaterEqual(month_res["completed_ticks"], 1)

if __name__ == "__main__":
    unittest.main()
