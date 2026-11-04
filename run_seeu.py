#!/usr/bin/env python3
"""
Punto de entrada universal para seeU.
Permite iniciar la aplicacion de escritorio directamente desde cualquier sistema operativo.
"""
import sys
from pathlib import Path

# Inyectar el directorio src en sys.path
SRC_DIR = Path(__file__).resolve().parent / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from supervisor.main import main

if __name__ == "__main__":
    main()
