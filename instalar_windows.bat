@echo off
title seeU - Instalador de Escritorio para Windows
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
echo  Bienvenido al instalador guiado de seeU para Windows.
echo  Este script configurara todo tu entorno automaticamente.
echo.

echo [1/4] Verificando instalacion de Python en Windows...
python -c "import sys; sys.exit(sys.version_info[:2] < (3, 11))" >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo.
    echo  [AVISO] No se detecto una version compatible de Python.
    echo  Para que seeU funcione, por favor instala Python 3.11 o superior
    echo  desde: https://www.python.org/downloads/
    echo  (Asegurate de marcar la casilla "Add python.exe to PATH")
    echo.
    pause
    exit /b 1
)
python --version
echo [OK] Python detectado.
echo.

echo [2/4] Creando entorno virtual aislado (.venv)...
if not exist ".venv" (
    python -m venv .venv
    echo [OK] Entorno virtual creado.
) else (
    echo [OK] Entorno virtual existente detectado.
)
echo.

echo [3/4] Instalando dependencias (PyQt6, QtWebEngine, pywebview, google-genai)...
echo Por favor espera un momento mientras se descargan e instalan las librerias...
echo.
".venv\Scripts\python.exe" -m pip install --upgrade pip
".venv\Scripts\python.exe" -m pip install -r requirements.txt
if %ERRORLEVEL% NEQ 0 (
    echo.
    echo [ERROR] Hubo un inconveniente al instalar las dependencias con pip.
    echo Revisa tu conexion a internet e intenta nuevamente.
    pause
    exit /b 1
)
echo [OK] Todas las dependencias quedaron instaladas correctamente.
echo.

echo [4/4] Creando acceso directo en tu Escritorio...
powershell -Command "$s=(New-Object -COM WScript.Shell).CreateShortcut([Environment]::GetFolderPath('Desktop') + '\seeU.lnk'); $s.TargetPath='%~dp0iniciar_seeU.vbs'; $s.WorkingDirectory='%~dp0'; if(Test-Path '%~dp0assets\icon.ico'){$s.IconLocation='%~dp0assets\icon.ico'}; $s.Save()"
echo [OK] Acceso directo 'seeU' creado en tu Escritorio.
echo.

echo  ============================================================
echo   INSTALACION COMPLETADA CON EXITO
echo  ============================================================
echo.
echo   - Se creo un acceso directo de seeU en tu Escritorio.
echo   - Al abrirlo, seeU se ejecutara en segundo plano SIN ninguna
echo     ventana negra de consola y con desenfoque de cristal real.
echo.
set /p abrir="Deseas iniciar seeU ahora mismo? (S/N): "
if /i "%abrir%"=="S" (
    start "" wscript.exe "%~dp0iniciar_seeU.vbs"
)
echo.
echo Disfruta de seeU. Cerrando instalador...
timeout /t 3 >nul
exit
