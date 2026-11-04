import sys
from pathlib import Path

# Asegurar que el directorio src esté siempre en sys.path tanto en Windows como en Linux
SRC_DIR = Path(__file__).resolve().parents[1]
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from supervisor.database.schema import create_tables
from supervisor.ui.main_window import start_ui

def main():
    # Inicializar tablas de SQLite si no existen
    create_tables()

    # Iniciar la interfaz gráfica transparente de seeU
    start_ui()

if __name__ == "__main__":
    main()
