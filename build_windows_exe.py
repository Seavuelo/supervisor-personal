#!/usr/bin/env python3
"""
Script de compilacion automatica de seeU para Windows (.exe) utilizando PyInstaller.
"""
import subprocess
import sys
from pathlib import Path

def main():
    print("=======================================================")
    print("       seeU - Compilador de Ejecutable (.exe)")
    print("=======================================================")

    project_root = Path(__file__).resolve().parent
    spec_file = project_root / "seeU.spec"

    print("[1/3] Verificando instalacion de PyInstaller...")
    try:
        import PyInstaller
    except ImportError:
        print("Instalando PyInstaller en el entorno...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "pyinstaller"])

    print("[2/3] Compilando seeU.exe con PyInstaller...")
    cmd = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--clean",
        "--noconfirm",
        str(spec_file)
    ]
    subprocess.check_call(cmd, cwd=str(project_root))

    dist_dir = project_root / "dist" / "seeU"
    exe_path = dist_dir / "seeU.exe"
    print("\n=======================================================")
    if exe_path.exists():
        print(f"   [EXITO] Ejecutable generado correctamente en:")
        print(f"   {exe_path}")
        print("=======================================================")
    else:
        print(f"   [LISTO] Paquete generado en: {dist_dir}")
        print("=======================================================")

if __name__ == "__main__":
    main()
