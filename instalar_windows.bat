@echo off
title seeU - Instalador Asistido para Windows
cd /d "%~dp0"

echo.
echo  ============================================================
echo   .d8888b.                     888     888 
echo  d88P  Y88b                    888     888 
echo  Y88b.                         888     888 
echo   "Y888b.    .d88b.   .d88b.   888     888 
echo      "Y88b. d8P  Y8b d8P  Y8b  888     888 
echo        "888 88888888 88888888  888     888 
echo  Y88b  d88P Y8b.     Y8b.      Y88b. .d88P 
echo   "Y8888P"   "Y8888   "Y8888    "Y88888P"  
echo  ============================================================
echo               seeU ^| Supervisor Personal
echo               Desarrollado por Seavuelo
echo  ============================================================
echo.
echo  Bienvenido al instalador de seeU para Windows.
echo  Esta herramienta configurara el entorno necesario para que
echo  puedas usar tu supervisor de escritorio sin complicaciones.
echo.
pause

echo.
echo [1/4] Verificando instalacion de Python en tu sistema...
python --version >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo.
    echo [ERROR] No se detecto Python instalado en tu equipo.
    echo Para continuar, descarga e instala Python (version 3.10 o superior)
    echo desde el sitio oficial marcando la casilla "Add python.exe to PATH":
    echo https://www.python.org/downloads/
    echo.
    pause
    exit /b 1
)
python --version
echo Python detectado correctamente.

echo.
echo [2/4] Creando entorno virtual aislado (.venv)...
if not exist ".venv" (
    python -m venv .venv
    echo Entorno virtual creado con exito.
) else (
    echo El entorno virtual ya existia, procediendo a actualizarlo.
)

echo.
echo [3/4] Instalando dependencias necesarias (PyQt6, pywebview, google-genai)...
call .venv\Scripts\activate.bat
python -m pip install --upgrade pip >nul 2>&1
pip install -r requirements.txt
if %ERRORLEVEL% NEQ 0 (
    echo.
    echo [ERROR] Ocurrio un inconveniente al instalar las dependencias.
    echo Revisa tu conexion a internet e intenta nuevamente.
    pause
    exit /b 1
)

echo.
echo [4/4] Instalando comando CLI y MCP para agentes externos...
pip install -e . >nul 2>&1

echo.
echo  ============================================================
echo   [INSTALACION COMPLETADA CON EXITO]
echo  ============================================================
echo.
echo   Como usar seeU desde ahora:
echo   - Haz doble clic en "iniciar_seeU.bat" para abrir la ventana.
echo   - O ejecuta "python -m supervisor.cli --help" para interactuar
echo     desde tu terminal o conectar agentes de IA externos.
echo.
echo  ============================================================
echo.
set /p arrancar="Deseas iniciar seeU en este momento? (S/N): "
if /i "%arrancar%"=="S" (
    start "" pythonw run_seeu.py
)
echo Que tengas un dia productivo y tranquilo.
pause
