import os
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
        self.orb_size = 44
        self._anim = None

    def set_window(self, window):
        self.window = window

    # --- Métodos de Tareas ---
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

    # --- Métodos de Metas y Hábitos ---
    def get_goals(self):
        return self.goal_service.get_all_goals()

    def create_goal(self, title, description="", category="estudio"):
        return self.goal_service.create_goal(title, description, category)

    def add_step_to_goal(self, goal_id, step_title, duration_tag="25 min"):
        return self.goal_service.add_step_to_goal(goal_id, step_title, duration_tag)

    def delete_goal(self, goal_id):
        return self.goal_service.delete_goal(goal_id)

    # --- Métodos de Inteligencia Artificial ---
    def process_ai(self, text):
        return self.ai_service.process_input(text)

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

    # --- Ventana y Animación Qt ---
    def _get_qt_window(self):
        try:
            from webview.platforms.qt import BrowserView
            return BrowserView.instances.get(self.window.uid)
        except Exception:
            return None

    def minimize_to_orb(self):
        if not self.window:
            return

        # Recordar dónde estaba la ventana antes de minimizar
        self.window_x = self.window.x
        self.window_y = self.window.y
        settings_repository.set_setting("window_x", self.window_x)
        settings_repository.set_setting("window_y", self.window_y)

        q_win = self._get_qt_window()
        if q_win:
            try:
                from PyQt6.QtCore import QPropertyAnimation, QRect, QEasingCurve
                q_win.setMinimumSize(32, 32)
                q_win.setMaximumSize(16777215, 16777215)

                start_rect = q_win.geometry()
                end_rect = QRect(self.orb_x, self.orb_y, self.orb_size, self.orb_size)

                self._anim = QPropertyAnimation(q_win, b"geometry")
                self._anim.setDuration(220)
                self._anim.setStartValue(start_rect)
                self._anim.setEndValue(end_rect)
                self._anim.setEasingCurve(QEasingCurve.Type.OutCubic)

                def on_finish():
                    if self.window:
                        self.window.resize(self.orb_size, self.orb_size)
                        self.window.move(self.orb_x, self.orb_y)

                self._anim.finished.connect(on_finish)
                self._anim.start()
                return
            except Exception as e:
                print(f"[seeU] Animación Qt fallback: {e}")

        self.window.resize(self.orb_size, self.orb_size)
        self.window.move(self.orb_x, self.orb_y)

    def restore_window(self):
        if not self.window:
            return

        # Recordar dónde estaba el orbe antes de restaurar
        self.orb_x = self.window.x
        self.orb_y = self.window.y
        settings_repository.set_setting("orb_x", self.orb_x)
        settings_repository.set_setting("orb_y", self.orb_y)

        q_win = self._get_qt_window()
        if q_win:
            try:
                from PyQt6.QtCore import QPropertyAnimation, QRect, QEasingCurve
                q_win.setMinimumSize(32, 32)
                q_win.setMaximumSize(16777215, 16777215)

                start_rect = q_win.geometry()
                end_rect = QRect(self.window_x, self.window_y, self.full_width, self.full_height)

                self._anim = QPropertyAnimation(q_win, b"geometry")
                self._anim.setDuration(220)
                self._anim.setStartValue(start_rect)
                self._anim.setEndValue(end_rect)
                self._anim.setEasingCurve(QEasingCurve.Type.OutCubic)

                def on_finish():
                    if self.window:
                        self.window.resize(self.full_width, self.full_height)
                        self.window.move(self.window_x, self.window_y)

                self._anim.finished.connect(on_finish)
                self._anim.start()
                return
            except Exception as e:
                print(f"[seeU] Animación Qt fallback: {e}")

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
        min_size=(40, 40),
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
