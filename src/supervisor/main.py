import sys
from pathlib import Path

# Asegurar que el directorio src esté siempre en sys.path tanto en Windows como en Linux
SRC_DIR = Path(__file__).resolve().parents[1]
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from supervisor.database.schema import create_tables
from supervisor.ui.main_window import start_ui

def main():
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

    # Inicializar tablas de SQLite si no existen
    create_tables()

    # Iniciar la interfaz gráfica transparente de seeU
    start_ui()

if __name__ == "__main__":
    main()
