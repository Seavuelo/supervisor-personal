#!/usr/bin/env python3
"""
Script de compilacion automatica de seeU para Windows (.exe e Instalador).
"""
import subprocess
import sys
import shutil
from pathlib import Path

def main():
    print("=======================================================")
    print("       seeU - Compilador de Ejecutable e Instalador")
    print("               Desarrollado por Seavuelo")
    print("=======================================================")

    project_root = Path(__file__).resolve().parent
    spec_file = project_root / "seeU.spec"
    iss_file = project_root / "seeu_installer.iss"

    print("[1/3] Verificando instalacion de PyInstaller...")
    try:
        import PyInstaller
    except ImportError:
        print("Instalando PyInstaller en el entorno...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "pyinstaller"])

    print("[2/3] Compilando seeU.exe en modo silencioso (sin consola CMD)...")
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
    if exe_path.exists():
        print(f"   [OK] seeU.exe generado en: {exe_path}")

    print("[3/3] Buscando Inno Setup (iscc) para generar el instalador visual...")
    iscc = shutil.which("iscc") or shutil.which("ISCC.exe")
    # Buscar en rutas estandar de Windows si no esta en PATH
    if not iscc and sys.platform == "win32":
        candidate_paths = [
            Path("C:/Program Files (x86)/Inno Setup 6/ISCC.exe"),
            Path("C:/Program Files/Inno Setup 6/ISCC.exe"),
            Path("C:/Users") / Path.home().name / "AppData/Local/Programs/Inno Setup 6/ISCC.exe"
        ]
        for p in candidate_paths:
            if p.exists():
                iscc = str(p)
                break

    if iscc and iss_file.exists():
        print(f"   Compilando instalador asistido con Inno Setup ({iscc})...")
        try:
            subprocess.check_call([iscc, str(iss_file)], cwd=str(project_root))
            installer_path = project_root / "dist-installer" / "seeU-Setup-x64.exe"
            if installer_path.exists():
                print("\n=======================================================")
                print("   [EXITO TOTAL] INSTALADOR DE WINDOWS GENERADO:")
                print(f"   {installer_path}")
                print("   Cualquier persona puede abrir este archivo e instalar")
                print("   seeU con un asistente visual 'Siguiente > Instalar'.")
                print("=======================================================")
                return
        except Exception as e:
            print(f"   [AVISO] No se pudo compilar con Inno Setup: {e}")

    print("\n=======================================================")
    print("   [LISTO] Paquete ejecutable generado en: dist/seeU/")
    print("   Para generar el archivo 'seeU-Setup-x64.exe':")
    print("   - Instala Inno Setup desde https://jrsoftware.org/isdl.php")
    print("   - O sube tus cambios a GitHub para que GitHub Actions")
    print("     lo compile y publique automaticamente en Releases.")
    print("=======================================================")

if __name__ == "__main__":
    main()
