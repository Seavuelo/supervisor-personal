import sys
from supervisor.database.schema import create_tables
from supervisor.ui.main_window import start_ui

def main():
    # Inicializar tablas de SQLite si no existen
    create_tables()

    # Iniciar la interfaz gráfica transparente de seeU
    start_ui()

if __name__ == "__main__":
    main()
