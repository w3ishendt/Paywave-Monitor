@echo off
setlocal

if /i "%~1"=="__run" goto run

start "ICPS Startup Runner" /min cmd /c ""%~f0" __run"
exit /b 0

:run

set "SCRIPT_DIR=%~dp0"
set "PYTHON_EXE=%SCRIPT_DIR%venv\Scripts\python.exe"

if exist "%PYTHON_EXE%" (
    "%PYTHON_EXE%" "%SCRIPT_DIR%icps_startup_runner.py"
) else (
    python "%SCRIPT_DIR%icps_startup_runner.py"
)

exit /b %errorlevel%