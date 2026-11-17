import unittest
import os
import json
import tempfile
import sqlite3
from contextlib import closing
from datetime import datetime, date, timedelta
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

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
        store = {}
        self.save_credential = Mock(side_effect=lambda service, account, key: store.update({(service, account): key}))
        for credential_patch in (
            patch.dict(os.environ, {"GEMINI_API_KEY": ""}),
            patch("keyring.get_password", side_effect=lambda service, account: store.get((service, account))),
            patch("keyring.set_password", self.save_credential),
        ):
            credential_patch.start()
            self.addCleanup(credential_patch.stop)
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
        path = Path(self.temp_db.name).with_suffix(".lnk")
        with patch.object(seeU_API, "_get_autostart_file_path", return_value=path):
            self._check_autostart()

    def _check_autostart(self):
        api = seeU_API()
        autostart_file = api._get_autostart_file_path()

        try:
            # Activar autostart
            status_on = api.set_autostart(True)
            self.assertTrue(status_on)
            self.assertTrue(autostart_file.exists())
            self.assertTrue(api.get_autostart_status())

            # Desactivar autostart
            status_off = api.set_autostart(False)
            self.assertFalse(status_off)
            self.assertFalse(autostart_file.exists())
            self.assertFalse(api.get_autostart_status())
        finally:
            if autostart_file.exists():
                try:
                    autostart_file.unlink()
                except Exception:
                    pass

    def test_minimize_mode_setting(self):
        api = seeU_API()
        # Por defecto debe ser orb
        self.assertEqual(api.get_minimize_mode(), "orb")

        # Cambiar a modo bandeja
        res = api.set_minimize_mode("tray")
        self.assertTrue(res)
        self.assertEqual(api.get_minimize_mode(), "tray")

        # Cambiar de vuelta a orb
        res2 = api.set_minimize_mode("orb")
        self.assertTrue(res2)
        self.assertEqual(api.get_minimize_mode(), "orb")

        # Validar rechazo de modos inválidos
        invalid_res = api.set_minimize_mode("invalid_mode")
        self.assertFalse(invalid_res)
        self.assertEqual(api.get_minimize_mode(), "orb")

    def test_update_service_and_version_comparison(self):
        from supervisor.services.update_service import parse_version, is_newer_version, UpdateService

        # 1. Comparación de versiones
        self.assertEqual(parse_version("v1.0.3"), (1, 0, 3))
        self.assertEqual(parse_version("1.10.2"), (1, 10, 2))
        self.assertTrue(is_newer_version("v1.0.7", "1.0.6"))
        self.assertTrue(is_newer_version("v2.0.0", "1.9.9"))
        self.assertFalse(is_newer_version("v1.0.5", "1.0.6"))
        self.assertFalse(is_newer_version("v1.0.6", "1.0.6"))

        # 2. Preferencias de actualización
        service = UpdateService(current_version="1.0.6")
        self.assertTrue(service.set_update_preference("ignore", "v1.0.7"))
        self.assertEqual(settings_repository.get_setting("update_ignored_version"), "v1.0.7")

        self.assertTrue(service.set_update_preference("remind_later", "v1.0.7"))
        self.assertIsNotNone(settings_repository.get_setting("update_remind_later_until"))

        # 3. Métodos en ver de la API
        api = seeU_API()
        self.assertEqual(api.get_app_version(), "1.1.1")

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

    def test_month_summary_and_listing_for_an_undated_task(self):
        from supervisor.mcp_server import execute_tool

        task_id = task_repository.save_task(Task(title="Sin fecha", created_at="2026-11-03T09:00:00"))
        summary = TaskService.get_monthly_summary("2026-11")
        self.assertEqual([day["day"] for day in summary["days"] if day["has_activity"]], [3])
        month = json.loads(execute_tool("seeu_list_tasks", {"month": "2026-11"}))
        self.assertEqual([task["id"] for task in month["tasks"]], [task_id])

    def test_overdue_actions_only_modify_focus(self):
        from supervisor.services.goal_service import GoalService

        yesterday = (date.today() - timedelta(days=1)).isoformat()
        goal = GoalService.create_goal("Meta")
        step = task_repository.save_task(Task(title="Paso", goal_id=goal["id"], created_at=yesterday))
        appointment = TaskService.create_task("Consulta", scheduled_date=yesterday, task_type="appointment")
        recurring = TaskService.create_task("Pago", scheduled_date=yesterday, recurrence="monthly")
        focus = TaskService.create_task("Pendiente", scheduled_date=yesterday)
        self.assertEqual([task["id"] for task in TaskService.get_overdue_tasks()], [focus["id"]])
        self.assertEqual(TaskService.postpone_all_overdue(), 1)
        second = TaskService.create_task("Otra tarea", scheduled_date=yesterday)
        self.assertEqual(TaskService.dismiss_all_overdue(), 1)
        tasks = {task["id"]: task for task in TaskService.get_all_tasks()}
        self.assertEqual(tasks[focus["id"]]["scheduled_date"], date.today().isoformat())
        self.assertEqual(tasks[second["id"]]["status"], "no_lograda")
        self.assertTrue(all(tasks[task_id]["status"] == "pendiente" for task_id in (step, appointment["id"], recurring["id"])))

    def test_monthly_occurrences_keep_original_day_and_separate_ticks(self):
        from supervisor.services.ai_service import AIService

        task = TaskService.create_task("Pago", scheduled_date="2026-01-31", task_type="appointment", recurrence="monthly")
        with patch.object(task_repository, "date", wraps=date) as clock:
            clock.today.return_value = date(2026, 2, 28)
            self.assertEqual(TaskService.get_all_tasks()[0]["scheduled_date"], "2026-02-28")
            self.assertTrue(TaskService.set_task_status(task["id"], "completada"))
            self.assertTrue(TaskService.set_task_status(task["id"], "completada"))
            self.assertEqual(TaskService.get_all_tasks()[0]["status"], "completada")
            clock.today.return_value = date(2026, 3, 30)
            upcoming = TaskService.get_all_tasks()[0]
            self.assertEqual((upcoming["scheduled_date"], upcoming["status"]), ("2026-03-31", "pendiente"))
        with patch("supervisor.services.ai_service.datetime", wraps=datetime) as clock:
            clock.now.return_value = datetime(2026, 3, 30, 12)
            self.assertEqual(AIService().get_smart_reminders([task])[0]["days_left"], 1)
        self.assertEqual(TaskService.get_monthly_summary("2026-02")["completed_ticks"], 1)
        self.assertEqual(TaskService.get_monthly_summary("2026-03")["completed_ticks"], 0)

    def test_legacy_recurrence_migrates_once(self):
        with closing(connection.get_connection()) as db, db:
            db.execute("DROP TABLE task_ticks")
        old_task = task_repository.save_task(Task(
            title="Mensual anterior", scheduled_date="2026-01-19",
            recurrence="monthly", status="completada",
        ))
        schema.create_tables()
        schema.create_tables()
        self.assertEqual(TaskService.get_monthly_summary("2026-01")["completed_ticks"], 1)
        self.assertEqual(TaskService.get_all_tasks()[0]["status"], "pendiente")
        self.assertTrue(TaskService.delete_task(old_task))
        self.assertEqual(TaskService.get_monthly_summary("2026-01")["completed_ticks"], 0)

    def test_gemini_keeps_verified_key_and_distinguishes_failures(self):
        from google.genai.errors import APIError
        from httpx import ConnectError
        from supervisor.services.ai_service import AIService

        ai = AIService()
        client = Mock()
        response = client.models.generate_content
        with patch.object(ai, "_new_client", return_value=client):
            response.side_effect = [APIError(429, {}), APIError(404, {})]
            self.assertIn("429", ai.set_api_key("candidate")["message"])
            self.save_credential.assert_not_called()
            response.side_effect = ConnectError("offline")
            self.assertIn("conexión", ai.set_api_key("candidate")["message"])
            response.side_effect = [APIError(404, {}), SimpleNamespace(text="OK")]
            self.assertEqual(ai.set_api_key("verified-key")["status"], "ok")
        self.assertEqual(AIService().api_key, "verified-key")
        failing_client = Mock()
        failing_client.models.generate_content.side_effect = APIError(403, {})
        with patch.object(ai, "_new_client", return_value=failing_client):
            self.assertIn("403", ai.set_api_key("new-key")["message"])
        self.assertEqual(ai.api_key, "verified-key")
        self.assertEqual(failing_client.models.generate_content.call_count, 1)

    def test_gemini_moves_legacy_key_out_of_sqlite(self):
        from supervisor.services.ai_service import AIService

        settings_repository.set_setting("gemini_api_key", "old-placeholder")
        self.assertEqual(AIService().api_key, "old-placeholder")
        self.assertIsNone(settings_repository.get_setting("gemini_api_key"))
        self.assertEqual(AIService().get_connection_status()["status"], "configured")

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

    def test_orb_geometry_and_api(self):
        api = seeU_API()
        self.assertEqual(api.orb_size, 34)
        api.save_orb_position(150, 220)
        self.assertEqual(api.orb_x, 150)
        self.assertEqual(api.orb_y, 220)
        self.assertEqual(settings_repository.get_setting("orb_x"), "150")
        self.assertEqual(settings_repository.get_setting("orb_y"), "220")

        # Verificar que llamadas seguras no lanzan excepción sin ventana
        self.assertEqual(api.current_display_mode, "window")
        api.minimize_to_orb()
        api.restore_window()
        api.minimize_to_tray()
        api.restore_from_tray()
        api.move_orb_by(10, 10)

    def test_ui_detects_changes_from_other_database_connections(self):
        api = seeU_API()
        try:
            initial = api.get_data_version()
            self.assertEqual(api.get_data_version(), initial)
            TaskService.create_task("Desde CLI o MCP")
            self.assertNotEqual(api.get_data_version(), initial)
        finally:
            api._close_version_connection()

    def test_always_on_top_and_window_drag(self):
        api = seeU_API()
        # 1. Always on top por defecto
        self.assertTrue(api.get_always_on_top())

        # 2. Alternar a modo fondo de escritorio
        api.set_always_on_top(False)
        self.assertFalse(api.get_always_on_top())
        self.assertEqual(settings_repository.get_setting("always_on_top"), "false")

        # 3. Volver a siempre sobrepuesto
        api.set_always_on_top(True)
        self.assertTrue(api.get_always_on_top())
        self.assertEqual(settings_repository.get_setting("always_on_top"), "true")

        # 4. Mover ventana completa y guardar posición
        api.window_x = 400
        api.window_y = 250
        api.save_window_position()
        self.assertEqual(settings_repository.get_setting("window_x"), "400")
        self.assertEqual(settings_repository.get_setting("window_y"), "250")
        api.move_window_by(20, -10)

    def test_window_dimensions_and_resizing(self):
        api = seeU_API()
        # Dimensiones por defecto
        dims = api.get_window_dimensions()
        self.assertEqual(dims["width"], 430)
        self.assertEqual(dims["height"], 620)
        api.resize_window(450, 650, persist=False)
        self.assertEqual(api.get_window_dimensions(), {"width": 450, "height": 650})
        self.assertIsNone(settings_repository.get_setting("window_width"))

        # Redimensionar dentro de límites permitidos
        api.resize_window(500, 750)
        self.assertEqual(settings_repository.get_setting("window_width"), "500")
        self.assertEqual(settings_repository.get_setting("window_height"), "750")

        # Cargar de nuevo en otra instancia
        api2 = seeU_API()
        self.assertEqual(api2.full_width, 500)
        self.assertEqual(api2.full_height, 750)

    def test_smart_date_detection_and_reminders(self):
        from supervisor.services.ai_service import AIService
        ai = AIService()

        # 1. Probar parsing de "dentista a las 8 am un martes"
        res_dentista = ai.process_input("dentista a las 8 am un martes")
        self.assertIn("tasks", res_dentista)
        task_dent = res_dentista["tasks"][0]
        self.assertIn("dentista", task_dent["title"].lower())
        self.assertEqual(task_dent["scheduled_time"], "08:00")
        self.assertIsNotNone(task_dent["scheduled_date"])

        # 2. Probar parsing de "el 19 estoy de cumplemes con mi novia"
        res_cumple = ai.process_input("el 19 estoy de cumplemes con mi novia")
        self.assertIn("tasks", res_cumple)
        task_c = res_cumple["tasks"][0]
        self.assertIn("cumplemes", task_c["title"].lower())
        self.assertTrue(task_c["scheduled_date"].endswith("-19"))

        # 3. Probar generación de recordatorios inteligentes
        today = date.today()
        test_tasks = [
            {
                "id": 1,
                "title": "Dentista",
                "scheduled_date": today.strftime("%Y-%m-%d"),
                "scheduled_time": "08:00",
                "status": "pendiente"
            },
            {
                "id": 2,
                "title": "Cumplemes con mi novia",
                "scheduled_date": (today + timedelta(days=2)).strftime("%Y-%m-%d"),
                "scheduled_time": None,
                "status": "pendiente"
            },
            {
                "id": 3,
                "title": "Tarea completada",
                "scheduled_date": today.strftime("%Y-%m-%d"),
                "status": "completada"
            }
        ]

        reminders = ai.get_smart_reminders(test_tasks)
        self.assertEqual(len(reminders), 2)
        # Dentista hoy
        self.assertEqual(reminders[0]["icon"], "calendar")
        self.assertEqual(reminders[0]["days_left"], 0)
        self.assertIn("asistir", reminders[0]["message"].lower())

        # Cumplemes en 2 días
        self.assertEqual(reminders[1]["icon"], "heart")
        self.assertEqual(reminders[1]["days_left"], 2)
        self.assertIn("celebrarlo", reminders[1]["message"].lower())

    def test_connection_status_fast_check(self):
        api = seeU_API()
        status = api.get_connection_status()
        self.assertIn("status", status)
        self.assertIn(status["status"], ["ok", "offline"])

    def test_smart_destination_classification(self):
        from supervisor.services.ai_service import AIService
        ai = AIService()
        ai.client = None # Probar motor autónomo local

        # 1. Metas: Estudio, Finanzas, Salud y Proyectos
        res_ingles = ai.process_input("aprender inglés este año")
        self.assertEqual(res_ingles["action"], "create_goal")
        self.assertEqual(res_ingles["destination"], "goals")
        self.assertEqual(res_ingles["category"], "estudio")
        self.assertEqual(len(res_ingles["tasks"]), 3)
        self.assertTrue(res_ingles["is_goal"])

        res_ahorro = ai.process_input("meta: ahorrar 1 millon")
        self.assertEqual(res_ahorro["action"], "create_goal")
        self.assertEqual(res_ahorro["destination"], "goals")
        self.assertEqual(res_ahorro["category"], "finanzas")
        self.assertEqual(len(res_ahorro["tasks"]), 3)

        res_salud = ai.process_input("bajar 5 kilos")
        self.assertEqual(res_salud["action"], "create_goal")
        self.assertEqual(res_salud["destination"], "goals")
        self.assertEqual(res_salud["category"], "salud")

        res_startup = ai.process_input("lanzar mi startup")
        self.assertEqual(res_startup["action"], "create_goal")
        self.assertEqual(res_startup["destination"], "goals")
        self.assertEqual(res_startup["category"], "trabajo")

        # 2. Agenda: Citas con hora, fechas y preguntas aclaratorias
        res_dentista = ai.process_input("dentista martes a las 8 am")
        self.assertEqual(res_dentista["action"], "scheduled_task")
        self.assertEqual(res_dentista["destination"], "agenda")
        self.assertEqual(res_dentista["tasks"][0]["scheduled_time"], "08:00")

        res_cumple = ai.process_input("el 19 estoy de cumplemes con mi novia")
        self.assertEqual(res_cumple["action"], "scheduled_task")
        self.assertEqual(res_cumple["destination"], "agenda")

        res_cumple_mensual = ai.process_input("Mira, guarda la fecha 19 de cada mes, que cumplo un mes mas con mi novia todos los 19, asi como recordatorio")
        self.assertEqual(res_cumple_mensual["action"], "scheduled_task")
        self.assertEqual(res_cumple_mensual["destination"], "agenda")
        self.assertEqual(res_cumple_mensual["tasks"][0]["recurrence"], "monthly")
        self.assertEqual(res_cumple_mensual["tasks"][0]["task_type"], "appointment")
        self.assertIn("cumplemes", res_cumple_mensual["tasks"][0]["title"].lower())

        res_doc = ai.process_input("mañana tengo doctor")
        self.assertEqual(res_doc["action"], "question")
        self.assertEqual(res_doc["destination"], "agenda")

        # 3. Foco: Tareas cotidianas y hábitos diarios
        res_pan = ai.process_input("comprar pan")
        self.assertEqual(res_pan["action"], "quick_task")
        self.assertEqual(res_pan["destination"], "focus")
        self.assertEqual(res_pan["tasks"][0]["recurrence"], "none")

        res_ejercicio = ai.process_input("hacer ejercicio todos los días")
        self.assertEqual(res_ejercicio["action"], "quick_task")
        self.assertEqual(res_ejercicio["destination"], "focus")
        self.assertEqual(res_ejercicio["tasks"][0]["recurrence"], "daily")

if __name__ == "__main__":
    unittest.main()
