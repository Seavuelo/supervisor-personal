@echo off
title seeU - Supervisor Personal
cd /d "%~dp0"

echo ========================================================
echo             Iniciando seeU - Por Seavuelo
echo ========================================================

REM Activar entorno virtual si existe
if exist ".venv\Scripts\activate.bat" (
    call .venv\Scripts\activate.bat
)

REM Lanzar aplicacion a traves del punto de entrada universal
python run_seeu.py

if %ERRORLEVEL% NEQ 0 (
    echo.
    echo ========================================================
    echo  [AVISO] seeU se cerro o encontro un error al iniciar.
    echo ========================================================
    echo  Si es la primera vez que lo abres en esta maquina:
    echo  1. Instala Python desde https://www.python.org/
    echo  2. Abre PowerShell o CMD en esta carpeta e instala las dependencias:
    echo     pip install -r requirements.txt
    echo  3. Vuelve a ejecutar este archivo.
    echo ========================================================
    echo.
    pause
)
