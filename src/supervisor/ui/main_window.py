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
from supervisor.services.update_service import UpdateService
from supervisor.repositories import settings_repository

# Mutex global en Windows para que el instalador detecte si seeU está en ejecución
_app_mutex = None
if sys.platform == "win32":
    try:
        import ctypes
        _app_mutex = ctypes.windll.kernel32.CreateMutexW(None, False, "seeU_Personal_Supervisor_Mutex")
    except Exception:
        pass

def _ensure_default_desktop():
    """Garantiza que el hilo actual de Windows esté vinculado al escritorio interactivo 'Default'."""
    if sys.platform == "win32":
        try:
            import ctypes
            user32 = ctypes.windll.user32
            GENERIC_ALL = 0x10000000
            hdesk = user32.OpenDesktopW("Default", 0, False, GENERIC_ALL)
            if hdesk:
                user32.SetThreadDesktop(hdesk)
        except Exception:
            pass

_ensure_default_desktop()

def disable_window_blur(hwnd: int):
    """
    Desactiva cualquier política de desenfoque rectangular DWM a nivel de HWND en Windows.
    Esto garantiza transparencia pura por píxel (WA_TranslucentBackground) para que
    el micro-orbe sea un círculo perfecto sin recuadro y seeU no tenga bordes cuadrados
    alrededor de sus esquinas redondeadas.
    """
    if sys.platform != "win32" or not hwnd:
        return

    import ctypes
    from ctypes import c_int, c_uint, POINTER, Structure, sizeof, byref

    # 1. Desactivar AccentPolicy de Windows 10 (ACCENT_DISABLED = 0)
    try:
        class ACCENT_POLICY(Structure):
            _fields_ = [
                ('AccentState', c_int),
                ('AccentFlags', c_uint),
                ('GradientColor', c_uint),
                ('AnimationId', c_uint)
            ]

        class WINCOMPATTRDATA(Structure):
            _fields_ = [
                ('Attribute', c_int),
                ('Data', POINTER(ACCENT_POLICY)),
                ('SizeOfData', c_uint)
            ]

        policy = ACCENT_POLICY()
        policy.AccentState = 0  # ACCENT_DISABLED
        policy.AccentFlags = 0
        policy.GradientColor = 0
        policy.AnimationId = 0

        data = WINCOMPATTRDATA()
        data.Attribute = 19  # WCA_ACCENT_POLICY
        data.Data = ctypes.pointer(policy)
        data.SizeOfData = sizeof(policy)
        ctypes.windll.user32.SetWindowCompositionAttribute(hwnd, byref(data))
    except Exception:
        pass

    # 2. Desactivar DwmEnableBlurBehindWindow clásico
    try:
        class DWM_BLURBEHIND(Structure):
            _fields_ = [
                ('dwFlags', c_uint),
                ('fEnable', c_int),
                ('hRgnBlur', c_uint),
                ('fTransitionOnMaximized', c_int)
            ]

        bb = DWM_BLURBEHIND()
        bb.dwFlags = 1  # DWM_BB_ENABLE
        bb.fEnable = 0  # Desactivar para que sea transparencia alfa pura
        bb.hRgnBlur = 0
        bb.fTransitionOnMaximized = 0
        ctypes.windll.dwmapi.DwmEnableBlurBehindWindow(hwnd, byref(bb))
    except Exception:
        pass

    # 3. Desactivar DWMWA_SYSTEMBACKDROP_TYPE en Windows 11
    try:
        dwm = ctypes.windll.dwmapi
        backdrop_type = c_int(1)  # DWMSBT_NONE = 1
        dwm.DwmSetWindowAttribute(hwnd, 38, byref(backdrop_type), sizeof(backdrop_type))
    except Exception:
        pass

apply_window_blur = disable_window_blur

class seeU_API:
    def __init__(self):
        self.window = None
        self.task_service = TaskService()
        self.goal_service = GoalService()
        self.ai_service = AIService()
        self.update_service = UpdateService()

        # Coordenadas persistentes del orbe y la ventana
        saved_orb_x = settings_repository.get_setting("orb_x")
        saved_orb_y = settings_repository.get_setting("orb_y")
        self.orb_x = int(saved_orb_x) if saved_orb_x else 120
        self.orb_y = int(saved_orb_y) if saved_orb_y else 120

        saved_win_x = settings_repository.get_setting("window_x")
        saved_win_y = settings_repository.get_setting("window_y")
        self.window_x = int(saved_win_x) if saved_win_x else 300
        self.window_y = int(saved_win_y) if saved_win_y else 180

        saved_w = settings_repository.get_setting("window_width")
        saved_h = settings_repository.get_setting("window_height")
        self.full_width = int(saved_w) if saved_w else 430
        self.full_height = int(saved_h) if saved_h else 620
        self.orb_size = 44
        self.current_display_mode = "window"  # "window", "orb", "tray"

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

    def get_monthly_summary(self, month=None):
        if not month:
            from datetime import datetime
            month = datetime.now().strftime("%Y-%m")
        return self.task_service.get_monthly_summary(month)

    def get_overall_stats(self):
        return self.task_service.get_overall_stats()

    def get_data_version(self):
        return self.task_service.get_data_version()

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

    def get_connection_status(self):
        return self.ai_service.get_connection_status()

    def get_smart_reminders(self):
        tasks = self.task_service.get_all_tasks()
        return self.ai_service.get_smart_reminders(tasks)

    # --- Dimensiones y Redimensión Dinámica ---
    def resize_window(self, width: int, height: int):
        w = max(340, min(900, int(width)))
        h = max(420, min(1000, int(height)))
        self.full_width = w
        self.full_height = h
        settings_repository.set_setting("window_width", str(w))
        settings_repository.set_setting("window_height", str(h))

        if not self.window:
            return

        def _do_resize():
            try:
                from webview.platforms.qt import BrowserView
                q_win = BrowserView.instances.get(self.window.uid)
                if q_win and self.current_display_mode == "window":
                    q_win.resize(w, h)
            except Exception as e:
                print(f"[seeU] Error en resize_window: {e}")

        _run_in_gui(_do_resize)

    def get_window_dimensions(self):
        return {"width": self.full_width, "height": self.full_height}

    # --- Actualizaciones y Versión ---
    def check_for_updates(self, manual=False):
        return self.update_service.check_for_updates(manual=manual)

    def set_update_preference(self, action, version):
        return self.update_service.set_update_preference(action, version)

    def get_app_version(self):
        return self.update_service.current_version

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
            if getattr(sys, 'frozen', False):
                exe = sys.executable
                if sys.platform == "win32":
                    content = f'@echo off\nstart "" "{exe}"\n'
                else:
                    content = f"""[Desktop Entry]
Type=Application
Name=seeU
Comment=Supervisor personal de tareas y agenda
Exec="{exe}"
Terminal=false
Categories=Utility;
X-GNOME-Autostart-enabled=true
"""
            else:
                python_bin = sys.executable
                main_script = Path(__file__).resolve().parent.parent / "main.py"
                if sys.platform == "win32":
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
    def get_minimize_mode(self):
        return settings_repository.get_setting("minimize_mode") or "orb"

    def set_minimize_mode(self, mode):
        if mode in ("orb", "tray"):
            settings_repository.set_setting("minimize_mode", mode)
            return True
        return False

    def minimize_to_tray(self):
        if not self.window:
            return

        def _do_hide():
            try:
                from PyQt6.QtWidgets import QSystemTrayIcon
                from webview.platforms.qt import BrowserView
                q_win = BrowserView.instances.get(self.window.uid)
                if q_win:
                    if self.current_display_mode == "window":
                        self.window_x = q_win.x()
                        self.window_y = q_win.y()
                        settings_repository.set_setting("window_x", self.window_x)
                        settings_repository.set_setting("window_y", self.window_y)
                    self.current_display_mode = "tray"
                    q_win.hide()
                    tray = getattr(q_win, '_tray_icon', None) or getattr(self, '_tray_icon', None)
                    if tray:
                        try:
                            tray.showMessage(
                                "seeU • En segundo plano",
                                "seeU sigue activo en la bandeja del sistema. Haz clic aquí o en su icono para volver a abrirlo.",
                                QSystemTrayIcon.MessageIcon.Information,
                                3000
                            )
                        except Exception:
                            pass
            except Exception as e:
                print(f"[seeU] Error en minimize_to_tray: {e}")

        _run_in_gui(_do_hide)

    def minimize_to_orb(self):
        if not self.window:
            return

        def _do_minimize():
            try:
                from webview.platforms.qt import BrowserView
                q_win = BrowserView.instances.get(self.window.uid)
                if q_win:
                    if self.current_display_mode == "window":
                        self.window_x = q_win.x()
                        self.window_y = q_win.y()
                        settings_repository.set_setting("window_x", self.window_x)
                        settings_repository.set_setting("window_y", self.window_y)

                    self.current_display_mode = "orb"
                    if q_win.isHidden():
                        q_win.show()
                    q_win.setGeometry(self.orb_x, self.orb_y, self.orb_size, self.orb_size)
                    q_win.raise_()
                    if sys.platform == "win32":
                        try:
                            hwnd = int(q_win.winId())
                            apply_window_blur(hwnd)
                        except Exception:
                            pass
            except Exception as e:
                print(f"[seeU] Error en minimize_to_orb: {e}")

        _run_in_gui(_do_minimize)

    def restore_window(self):
        if not self.window:
            return

        def _do_restore():
            try:
                from webview.platforms.qt import BrowserView
                q_win = BrowserView.instances.get(self.window.uid)
                if q_win:
                    if self.current_display_mode == "orb":
                        self.orb_x = q_win.x()
                        self.orb_y = q_win.y()
                        settings_repository.set_setting("orb_x", self.orb_x)
                        settings_repository.set_setting("orb_y", self.orb_y)

                    self.current_display_mode = "window"
                    if q_win.isHidden():
                        q_win.show()
                    q_win.setGeometry(self.window_x, self.window_y, self.full_width, self.full_height)
                    q_win.raise_()
                    q_win.activateWindow()

                    if hasattr(q_win, 'webview') and q_win.webview:
                        q_win.webview.setFocus()

                    # Aplicar estado always_on_top configurado por el usuario y activar ventana
                    is_top = self.get_always_on_top()
                    if sys.platform == "win32":
                        try:
                            import ctypes
                            hwnd = int(q_win.winId())
                            HWND_TOPMOST = -1
                            HWND_NOTOPMOST = -2
                            SWP_NOMOVE = 0x0002
                            SWP_NOSIZE = 0x0001
                            SWP_SHOWWINDOW = 0x0040
                            ctypes.windll.user32.SetWindowPos(
                                hwnd,
                                HWND_TOPMOST if is_top else HWND_NOTOPMOST,
                                0, 0, 0, 0,
                                SWP_NOMOVE | SWP_NOSIZE | SWP_SHOWWINDOW
                            )
                            ctypes.windll.user32.SetForegroundWindow(hwnd)
                            apply_window_blur(hwnd)
                        except Exception:
                            pass
            except Exception as e:
                print(f"[seeU] Error en restore_window: {e}")

        _run_in_gui(_do_restore)

    def restore_from_tray(self):
        if not self.window:
            return

        def _do_restore():
            try:
                from webview.platforms.qt import BrowserView
                q_win = BrowserView.instances.get(self.window.uid)
                if q_win:
                    self.current_display_mode = "window"
                    if q_win.isHidden():
                        q_win.show()
                    q_win.setGeometry(self.window_x, self.window_y, self.full_width, self.full_height)
                    q_win.raise_()
                    q_win.activateWindow()

                    if hasattr(q_win, 'webview') and q_win.webview:
                        q_win.webview.setFocus()

                    if sys.platform == "win32":
                        try:
                            import ctypes
                            hwnd = int(q_win.winId())
                            is_top = self.get_always_on_top()
                            HWND_TOPMOST = -1
                            HWND_NOTOPMOST = -2
                            SWP_NOMOVE = 0x0002
                            SWP_NOSIZE = 0x0001
                            SWP_SHOWWINDOW = 0x0040
                            ctypes.windll.user32.SetWindowPos(
                                hwnd,
                                HWND_TOPMOST if is_top else HWND_NOTOPMOST,
                                0, 0, 0, 0,
                                SWP_NOMOVE | SWP_NOSIZE | SWP_SHOWWINDOW
                            )
                            ctypes.windll.user32.SetForegroundWindow(hwnd)
                            apply_window_blur(hwnd)
                        except Exception:
                            pass

                    # Notificar a la interfaz de forma asíncrona y segura sin deadlocks
                    _safe_run_js(q_win, "restoreFromTray();")
            except Exception as e:
                print(f"[seeU] Error en restore_from_tray: {e}")

        _run_in_gui(_do_restore)

    def move_orb_by(self, dx, dy):
        def _do_move():
            try:
                from webview.platforms.qt import BrowserView
                q_win = BrowserView.instances.get(self.window.uid)
                if q_win:
                    new_x = q_win.x() + int(dx)
                    new_y = q_win.y() + int(dy)
                    q_win.move(new_x, new_y)
                    self.orb_x = new_x
                    self.orb_y = new_y
            except Exception:
                pass
        _run_in_gui(_do_move)

    def move_window_by(self, dx, dy):
        def _do_move():
            try:
                from webview.platforms.qt import BrowserView
                q_win = BrowserView.instances.get(self.window.uid)
                if q_win:
                    new_x = q_win.x() + int(dx)
                    new_y = q_win.y() + int(dy)
                    q_win.move(new_x, new_y)
                    self.window_x = new_x
                    self.window_y = new_y
            except Exception:
                pass
        _run_in_gui(_do_move)

    def save_window_position(self):
        settings_repository.set_setting("window_x", self.window_x)
        settings_repository.set_setting("window_y", self.window_y)
        return True

    def get_always_on_top(self):
        saved = settings_repository.get_setting("always_on_top")
        return saved != "false"

    def set_always_on_top(self, enable):
        val = bool(enable)
        settings_repository.set_setting("always_on_top", "true" if val else "false")

        def _apply_on_top():
            try:
                from webview.platforms.qt import BrowserView
                q_win = BrowserView.instances.get(self.window.uid)
                if not q_win:
                    return

                if sys.platform == "win32":
                    import ctypes
                    hwnd = int(q_win.winId())
                    HWND_TOPMOST = -1
                    HWND_NOTOPMOST = -2
                    SWP_NOMOVE = 0x0002
                    SWP_NOSIZE = 0x0001
                    SWP_NOACTIVATE = 0x0010
                    ctypes.windll.user32.SetWindowPos(
                        hwnd,
                        HWND_TOPMOST if val else HWND_NOTOPMOST,
                        0, 0, 0, 0,
                        SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE
                    )
                else:
                    flags = q_win.windowFlags()
                    if val:
                        q_win.setWindowFlags(flags | QtCore.Qt.WindowType.WindowStaysOnTopHint)
                    else:
                        q_win.setWindowFlags(flags & ~QtCore.Qt.WindowType.WindowStaysOnTopHint)
                    q_win.show()
            except Exception as e:
                print(f"[seeU] Error al aplicar always_on_top: {e}")

        _run_in_gui(_apply_on_top)
        return val

    def save_orb_position(self, x, y):
        self.orb_x = int(x)
        self.orb_y = int(y)
        settings_repository.set_setting("orb_x", self.orb_x)
        settings_repository.set_setting("orb_y", self.orb_y)

    def close_app(self):
        def _do_close():
            try:
                from webview.platforms.qt import BrowserView
                q_win = BrowserView.instances.get(self.window.uid) if self.window else None
                if q_win and hasattr(q_win, '_tray_icon') and q_win._tray_icon:
                    q_win._tray_icon.hide()
            except Exception:
                pass
            if self.window:
                self.window.destroy()

        _run_in_gui(_do_close)

class _QtInvoker(QtCore.QObject):
    def customEvent(self, event):
        if hasattr(event, 'fn') and callable(event.fn):
            try:
                event.fn()
            except Exception as e:
                print(f"[seeU] Excepcion en ejecucion GUI: {e}")

class _QtFnEvent(QtCore.QEvent):
    TYPE = QtCore.QEvent.Type(QtCore.QEvent.registerEventType())
    def __init__(self, fn):
        super().__init__(self.TYPE)
        self.fn = fn

_qt_invoker = None

def _run_in_gui(fn):
    global _qt_invoker
    _ensure_default_desktop()
    app = QtCore.QCoreApplication.instance()
    if not app:
        return
    if _qt_invoker is None:
        _qt_invoker = _QtInvoker()
        _qt_invoker.moveToThread(app.thread())
    QtCore.QCoreApplication.postEvent(_qt_invoker, _QtFnEvent(fn))

def _safe_run_js(q_win, script: str):
    """Ejecuta JavaScript de forma asíncrona en el hilo GUI de Qt evitando bloqueos y deadlocks."""
    try:
        if q_win and hasattr(q_win, 'webview') and q_win.webview and hasattr(q_win.webview, 'page'):
            page = q_win.webview.page()
            if page:
                page.runJavaScript(script)
    except Exception as e:
        print(f"[seeU] Error ejecutando JS seguro: {e}")

def _setup_system_tray_and_tool_window(window, api):
    """Configura el icono en la bandeja del sistema y garantiza la transparencia real y desenfoque en Windows y Linux."""
    def _apply_in_gui():
        try:
            _ensure_default_desktop()
            from PyQt6 import QtCore
            from PyQt6.QtWidgets import QApplication, QSystemTrayIcon, QMenu
            from PyQt6.QtGui import QIcon, QPixmap, QPainter, QColor, QPen
            from webview.platforms.qt import BrowserView

            q_win = BrowserView.instances.get(window.uid)
            q_app = QApplication.instance()
            if q_app:
                q_app.setQuitOnLastWindowClosed(False)

            icon_ico = Path(__file__).resolve().parent / "assets" / "icon.ico"
            icon_png = Path(__file__).resolve().parent / "assets" / "icon.png"

            if q_win:
                # Transparencia real por pixel
                q_win.setAttribute(QtCore.Qt.WidgetAttribute.WA_TranslucentBackground, True)
                q_win.setStyleSheet("background: transparent;")
                if hasattr(q_win, 'webview') and q_win.webview:
                    q_win.webview.setAttribute(QtCore.Qt.WidgetAttribute.WA_TranslucentBackground, True)
                    q_win.webview.setStyleSheet("background: transparent;")
                    if hasattr(q_win.webview, 'page') and q_win.webview.page():
                        q_win.webview.page().setBackgroundColor(QtCore.Qt.GlobalColor.transparent)

                # Icono de la aplicación
                best_icon_file = icon_ico if icon_ico.exists() else icon_png
                if best_icon_file.exists():
                    app_icon = QIcon(str(best_icon_file))
                    q_win.setWindowIcon(app_icon)
                    if q_app:
                        q_app.setWindowIcon(app_icon)

                # Aplicar desenfoque real (blur / acrylic) en Windows
                if sys.platform == "win32":
                    try:
                        hwnd = int(q_win.winId())
                        apply_window_blur(hwnd)
                    except Exception as e:
                        print(f"[seeU] Error aplicando blur inicial: {e}")

                q_win.show()

            if q_app and QSystemTrayIcon.isSystemTrayAvailable():
                # Obtener la resolución exacta de iconos de la bandeja del sistema de Windows (SM_CXSMICON)
                sm_w, sm_h = 16, 16
                if sys.platform == "win32":
                    try:
                        import ctypes
                        sm_w = ctypes.windll.user32.GetSystemMetrics(49) or 16  # SM_CXSMICON
                        sm_h = ctypes.windll.user32.GetSystemMetrics(50) or 16  # SM_CYSMICON
                    except Exception:
                        pass

                # Cargar el icono escalado con precisión milimétrica al tamaño de la bandeja
                if icon_ico.exists():
                    tray_qicon = QIcon(str(icon_ico))
                    tray_pix = tray_qicon.pixmap(sm_w, sm_h)
                    tray_icon = QSystemTrayIcon(QIcon(tray_pix), q_app)
                elif icon_png.exists():
                    tray_pix = QPixmap(str(icon_png)).scaled(sm_w, sm_h, QtCore.Qt.AspectRatioMode.KeepAspectRatio, QtCore.Qt.TransformationMode.SmoothTransformation)
                    tray_icon = QSystemTrayIcon(QIcon(tray_pix), q_app)
                else:
                    pix = QPixmap(sm_w, sm_h)
                    pix.fill(QtCore.Qt.GlobalColor.transparent)
                    painter = QPainter(pix)
                    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
                    painter.setBrush(QColor(16, 19, 28))
                    painter.setPen(QPen(QColor(255, 255, 255, 200), 1.5))
                    painter.drawEllipse(1, 1, sm_w - 2, sm_h - 2)
                    painter.setBrush(QColor(255, 255, 255))
                    painter.drawEllipse(sm_w // 2 - 2, sm_h // 2 - 2, 4, 4)
                    painter.end()
                    tray_icon = QSystemTrayIcon(QIcon(pix), q_app)

                tray_icon.setToolTip("seeU • Supervisor Personal")

                # Menú contextual
                menu = QMenu()
                action_open = menu.addAction("Abrir seeU")
                action_orb = menu.addAction("Minimizar a Micro-Orbe")
                action_tray = menu.addAction("Ocultar en la Bandeja")
                menu.addSeparator()
                action_quit = menu.addAction("Salir de seeU")

                # Conexiones sin evaluate_js directo (evita deadlocks)
                action_open.triggered.connect(lambda: api.restore_from_tray())
                action_orb.triggered.connect(lambda: _safe_run_js(q_win, "minimizeToOrb();"))
                action_tray.triggered.connect(lambda: _safe_run_js(q_win, "minimizeToTray();"))
                action_quit.triggered.connect(lambda: api.close_app())

                def on_tray_activated(reason):
                    if reason in (QSystemTrayIcon.ActivationReason.Trigger, QSystemTrayIcon.ActivationReason.DoubleClick):
                        if not q_win or q_win.isHidden() or not q_win.isVisible() or api.current_display_mode in ("tray", "orb"):
                            api.restore_from_tray()
                        else:
                            _safe_run_js(q_win, "requestMinimize();")

                tray_icon.activated.connect(on_tray_activated)
                tray_icon.messageClicked.connect(lambda: api.restore_from_tray())
                tray_icon.setContextMenu(menu)
                tray_icon.setVisible(True)
                tray_icon.show()
                if q_win:
                    q_win._tray_icon = tray_icon
                    q_win._tray_menu = menu
                api._tray_icon = tray_icon
                api._tray_menu = menu
        except Exception as e:
            print(f"[seeU] System Tray no disponible: {e}")

    _run_in_gui(_apply_in_gui)

def start_ui():
    _ensure_default_desktop()
    # Optimizar arranque de QtWebEngine / Chromium para evitar micro-congelamientos de GPU
    if "QTWEBENGINE_CHROMIUM_FLAGS" not in os.environ:
        os.environ["QTWEBENGINE_CHROMIUM_FLAGS"] = "--disable-logging --disable-gpu-shader-disk-cache"

    current_dir = Path(__file__).resolve().parent
    html_file = current_dir / "index.html"

    api = seeU_API()
    is_on_top = api.get_always_on_top()

    window = webview.create_window(
        title="seeU",
        url=str(html_file),
        js_api=api,
        width=api.full_width,
        height=api.full_height,
        min_size=(44, 44),
        x=api.window_x,
        y=api.window_y,
        resizable=True,
        frameless=True,
        easy_drag=False,
        transparent=True,
        on_top=is_on_top,
        background_color='#000000'
    )

    api.set_window(window)

    def on_app_started():
        _ensure_default_desktop()
        from webview.platforms.qt import BrowserView
        for _ in range(30):
            if BrowserView.instances.get(window.uid):
                break
            time.sleep(0.1)
        _setup_system_tray_and_tool_window(window, api)

    webview.start(on_app_started, gui="qt", debug=False)
