import os
import threading
import time
from pathlib import Path
import webview
from supervisor.services.task_service import TaskService
from supervisor.services.goal_service import GoalService
from supervisor.services.ai_service import AIService
from supervisor.repositories import settings_repository

class seeU_API:
    def __init__(self):
        self.window = None
        self.task_service = TaskService()
        self.goal_service = GoalService()
        self.ai_service = AIService()

        # Coordenadas persistentes del orbe y la ventana
        saved_orb_x = settings_repository.get_setting("orb_x")
        saved_orb_y = settings_repository.get_setting("orb_y")
        self.orb_x = int(saved_orb_x) if saved_orb_x else 120
        self.orb_y = int(saved_orb_y) if saved_orb_y else 120

        saved_win_x = settings_repository.get_setting("window_x")
        saved_win_y = settings_repository.get_setting("window_y")
        self.window_x = int(saved_win_x) if saved_win_x else 300
        self.window_y = int(saved_win_y) if saved_win_y else 180

        self.full_width = 430
        self.full_height = 620
        self.orb_size = 42

    def set_window(self, window):
        self.window = window

    # --- Tareas ---
    def get_tasks(self):
        return self.task_service.get_all_tasks()

    def create_task(self, title, tag="Hoy", scheduled_time=None, scheduled_date=None, task_type="quick", goal_id=None):
        return self.task_service.create_task(
            title=title,
            tag=tag,
            scheduled_time=scheduled_time,
            scheduled_date=scheduled_date,
            task_type=task_type,
            goal_id=goal_id
        )

    def toggle_task(self, task_id):
        return self.task_service.toggle_task(task_id)

    def delete_task(self, task_id):
        return self.task_service.delete_task(task_id)

    # --- Metas y Hábitos ---
    def get_goals(self):
        return self.goal_service.get_all_goals()

    def create_goal(self, title, description="", category="estudio"):
        return self.goal_service.create_goal(title, description, category)

    def add_step_to_goal(self, goal_id, step_title, duration_tag="25 min"):
        return self.goal_service.add_step_to_goal(goal_id, step_title, duration_tag)

    def delete_goal(self, goal_id):
        return self.goal_service.delete_goal(goal_id)

    # --- Agente Inteligente seeU ---
    def process_ai(self, text):
        return self.ai_service.process_input(text)

    def process_ai_followup(self, original_text, user_answer, context_type, extra_data=None):
        return self.ai_service.process_followup(original_text, user_answer, context_type, extra_data)

    def triage_focus(self):
        tasks = self.task_service.get_all_tasks()
        pending = [t for t in tasks if t.get("status") == "pendiente"]
        return self.ai_service.triage_focus(pending)

    def get_api_key_masked(self):
        return self.ai_service.get_api_key_masked()

    def save_api_key(self, key):
        return self.ai_service.set_api_key(key)

    def test_connection(self):
        return self.ai_service.test_connection()

    def open_external_url(self, url):
        import webbrowser
        webbrowser.open(url)

    # --- Geometría y Control de Ventana ---
    def minimize_to_orb(self):
        if not self.window:
            return

        # Guardar coordenadas de la ventana previa
        self.window_x = self.window.x
        self.window_y = self.window.y
        settings_repository.set_setting("window_x", self.window_x)
        settings_repository.set_setting("window_y", self.window_y)

        # 1. Redimensionar inmediatamente a 42x42 (evita la caja grande difusa)
        self.window.resize(self.orb_size, self.orb_size)

        # 2. Desplazamiento suave hacia la posición guardada del orbe
        start_x, start_y = self.window_x, self.window_y
        target_x, target_y = self.orb_x, self.orb_y

        def glide_to_orb():
            steps = 7
            for i in range(1, steps + 1):
                t = i / steps
                factor = 1.0 - (1.0 - t) ** 3
                cx = int(start_x + (target_x - start_x) * factor)
                cy = int(start_y + (target_y - start_y) * factor)
                if self.window:
                    self.window.move(cx, cy)
                time.sleep(0.016)
            if self.window:
                self.window.move(target_x, target_y)

        threading.Thread(target=glide_to_orb, daemon=True).start()

    def restore_window(self):
        if not self.window:
            return

        # Guardar coordenadas actuales del orbe
        self.orb_x = self.window.x
        self.orb_y = self.window.y
        settings_repository.set_setting("orb_x", self.orb_x)
        settings_repository.set_setting("orb_y", self.orb_y)

        # Redimensionar a ventana completa y posicionar
        self.window.resize(self.full_width, self.full_height)
        self.window.move(self.window_x, self.window_y)

    def save_orb_position(self, x, y):
        self.orb_x = int(x)
        self.orb_y = int(y)
        settings_repository.set_setting("orb_x", self.orb_x)
        settings_repository.set_setting("orb_y", self.orb_y)

    def close_app(self):
        if self.window:
            self.window.destroy()

def start_ui():
    current_dir = Path(__file__).resolve().parent
    html_file = current_dir / "index.html"

    api = seeU_API()

    window = webview.create_window(
        title="seeU",
        url=str(html_file),
        js_api=api,
        width=api.full_width,
        height=api.full_height,
        min_size=(36, 36),
        x=api.window_x,
        y=api.window_y,
        resizable=True,
        frameless=True,
        easy_drag=True,
        transparent=True,
        on_top=True,
        background_color="#12141c"
    )

    api.set_window(window)
    webview.start(gui="qt", debug=False)
