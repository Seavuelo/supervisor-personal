@echo off
cd /d "%~dp0"

REM Iniciar seeU en segundo plano sin ventana de consola (modo silencioso)
if exist ".venv\Scripts\pythonw.exe" (
    start "" ".venv\Scripts\pythonw.exe" run_seeu.py
) else (
    start "" pythonw run_seeu.py
)

exit
