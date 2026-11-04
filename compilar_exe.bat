@echo off
title Compilar seeU.exe para Windows
cd /d "%~dp0"

echo ========================================================
echo       Compilacion de seeU.exe - Por Seavuelo
echo ========================================================

REM Activar entorno virtual si existe
if exist ".venv\Scripts\activate.bat" (
    call .venv\Scripts\activate.bat
)

python build_windows_exe.py

echo.
echo Presiona cualquier tecla para cerrar esta ventana...
pause >nul
