import os
import sys
import threading
import time
from pathlib import Path
import webview
from PyQt6 import QtCore
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

    # --- Tareas y Prioridades ---
    def get_tasks(self):
        return self.task_service.get_all_tasks()

    def get_weekly_heatmap(self):
        return self.task_service.get_weekly_heatmap()

    def create_task(self, title, tag="Hoy", scheduled_time=None, scheduled_date=None, task_type="quick", goal_id=None, recurrence="none", is_priority=False):
        return self.task_service.create_task(
            title=title,
            tag=tag,
            scheduled_time=scheduled_time,
            scheduled_date=scheduled_date,
            task_type=task_type,
            goal_id=goal_id,
            recurrence=recurrence,
            is_priority=is_priority
        )

    def toggle_task(self, task_id):
        return self.task_service.toggle_task(task_id)

    def toggle_priority(self, task_id):
        return self.task_service.toggle_priority(task_id)

    def delete_task(self, task_id):
        return self.task_service.delete_task(task_id)

    # --- Tareas Atrasadas de Días Anteriores ---
    def get_overdue_tasks(self):
        return self.task_service.get_overdue_tasks()

    def postpone_all_overdue(self):
        return self.task_service.postpone_all_overdue()

    def dismiss_all_overdue(self):
        return self.task_service.dismiss_all_overdue()

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

    # --- Configuraciones y Autostart ---
    def get_setting(self, key, default=""):
        val = settings_repository.get_setting(key)
        return val if val is not None else default

    def set_setting(self, key, value):
        settings_repository.set_setting(key, value)
        return True

    def _get_autostart_file_path(self):
        if sys.platform == "win32":
            appdata = os.environ.get("APPDATA")
            if appdata:
                return Path(appdata) / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "Startup" / "seeU.bat"
            return Path.home() / "AppData" / "Roaming" / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "Startup" / "seeU.bat"
        return Path.home() / ".config" / "autostart" / "seeU.desktop"

    def get_autostart_status(self):
        target = self._get_autostart_file_path()
        return target.exists()

    def set_autostart(self, enable):
        target = self._get_autostart_file_path()
        if enable:
            target.parent.mkdir(parents=True, exist_ok=True)
            python_bin = sys.executable
            main_script = Path(__file__).resolve().parent.parent / "main.py"
            if sys.platform == "win32":
                # En Windows usamos pythonw si está disponible para evitar la consola negra
                pythonw_bin = python_bin.replace("python.exe", "pythonw.exe")
                exe = pythonw_bin if os.path.exists(pythonw_bin) else python_bin
                content = f'@echo off\nstart "" "{exe}" "{main_script}"\n'
            else:
                content = f"""[Desktop Entry]
Type=Application
Name=seeU
Comment=Supervisor personal de tareas y agenda
Exec={python_bin} {main_script}
Terminal=false
Categories=Utility;
X-GNOME-Autostart-enabled=true
"""
            target.write_text(content, encoding="utf-8")
            settings_repository.set_setting("autostart", "true")
            return True
        else:
            if target.exists():
                try:
                    target.unlink()
                except Exception:
                    pass
            settings_repository.set_setting("autostart", "false")
            return False

    def open_external_url(self, url):
        import webbrowser
        webbrowser.open(url)

    # --- Geometría y Control de Ventana ---
    def minimize_to_orb(self):
        if not self.window:
            return

        self.window_x = self.window.x
        self.window_y = self.window.y
        settings_repository.set_setting("window_x", self.window_x)
        settings_repository.set_setting("window_y", self.window_y)

        # Redimensionar a micro-orbe
        self.window.resize(self.orb_size, self.orb_size)

        # Desplazamiento suave hacia la posición del orbe
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

        self.orb_x = self.window.x
        self.orb_y = self.window.y
        settings_repository.set_setting("orb_x", self.orb_x)
        settings_repository.set_setting("orb_y", self.orb_y)

        self.window.resize(self.full_width, self.full_height)
        self.window.move(self.window_x, self.window_y)

        # Al restaurar, forzar al frontend a ubicarse en el día actual
        try:
            self.window.evaluate_js("if(typeof resetToToday === 'function') resetToToday();")
        except Exception:
            pass

    def save_orb_position(self, x, y):
        self.orb_x = int(x)
        self.orb_y = int(y)
        settings_repository.set_setting("orb_x", self.orb_x)
        settings_repository.set_setting("orb_y", self.orb_y)

    def close_app(self):
        if self.window:
            self.window.destroy()

class _QtInvoker(QtCore.QObject):
    def customEvent(self, event):
        if hasattr(event, 'fn') and callable(event.fn):
            event.fn()

class _QtFnEvent(QtCore.QEvent):
    TYPE = QtCore.QEvent.Type(QtCore.QEvent.registerEventType())
    def __init__(self, fn):
        super().__init__(self.TYPE)
        self.fn = fn

_qt_invoker = _QtInvoker()

def _run_in_gui(fn):
    QtCore.QCoreApplication.postEvent(_qt_invoker, _QtFnEvent(fn))

def _setup_system_tray_and_tool_window(window, api):
    """Configura el icono en la bandeja del sistema y remueve la app de la barra de tareas tradicional."""
    def _apply_in_gui():
        try:
            from PyQt6 import QtCore
            from PyQt6.QtWidgets import QApplication, QSystemTrayIcon, QMenu
            from PyQt6.QtGui import QIcon, QPixmap, QPainter, QColor, QPen
            from webview.platforms.qt import BrowserView

            q_win = BrowserView.instances.get(window.uid)
            q_app = QApplication.instance()

            if q_win:
                # Ocultar de la barra de tareas principal (tint2 / taskbar tradicional)
                q_win.setWindowFlag(QtCore.Qt.WindowType.Tool, True)
                q_win.show()

            if q_app and QSystemTrayIcon.isSystemTrayAvailable():
                # Crear icono vectorizado de seeU para la bandeja
                pix = QPixmap(24, 24)
                pix.fill(QtCore.Qt.GlobalColor.transparent)
                painter = QPainter(pix)
                painter.setRenderHint(QPainter.RenderHint.Antialiasing)
                painter.setBrush(QColor(16, 19, 28))
                painter.setPen(QPen(QColor(255, 255, 255, 200), 1.5))
                painter.drawEllipse(2, 2, 20, 20)
                painter.setBrush(QColor(255, 255, 255))
                painter.drawEllipse(9, 9, 6, 6)
                painter.end()

                tray_icon = QSystemTrayIcon(QIcon(pix), q_app)
                tray_icon.setToolTip("seeU • Supervisor Personal")

                # Menú contextual
                menu = QMenu()
                action_open = menu.addAction("Abrir seeU")
                action_orb = menu.addAction("Minimizar a Micro-Orbe")
                menu.addSeparator()
                action_quit = menu.addAction("Salir de seeU")

                action_open.triggered.connect(lambda: window.evaluate_js("restoreFromOrb();"))
                action_orb.triggered.connect(lambda: window.evaluate_js("minimizeToOrb();"))
                action_quit.triggered.connect(lambda: api.close_app())

                def on_tray_activated(reason):
                    if reason == QSystemTrayIcon.ActivationReason.Trigger:
                        window.evaluate_js("if(document.body.classList.contains('orb-mode')){ restoreFromOrb(); } else { minimizeToOrb(); }")

                tray_icon.activated.connect(on_tray_activated)
                tray_icon.setContextMenu(menu)
                tray_icon.show()
                # Mantener referencia viva para evitar recolección de basura
                q_win._tray_icon = tray_icon
        except Exception as e:
            print(f"[seeU] System Tray no disponible: {e}")

    _run_in_gui(_apply_in_gui)

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

    def on_app_started():
        _setup_system_tray_and_tool_window(window, api)

    webview.start(on_app_started, gui="qt", debug=False)
