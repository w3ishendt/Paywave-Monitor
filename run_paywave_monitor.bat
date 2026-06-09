@echo off
setlocal

set "SCRIPT_DIR=%~dp0"
set "PYTHON_EXE=%SCRIPT_DIR%venv\Scripts\python.exe"
if not exist "%PYTHON_EXE%" set "PYTHON_EXE=%SCRIPT_DIR%venv\Scripts\pythonw.exe"

set "MAIN_PY=%SCRIPT_DIR%main.py"
set "LOG_DIR=%SCRIPT_DIR%logs"
set "LOG_FILE=%LOG_DIR%\paywave-monitor.log"

if not exist "%LOG_DIR%" mkdir "%LOG_DIR%"

start "PayWave Monitor" /min cmd /c ""%PYTHON_EXE%" "%MAIN_PY%" %* >> "%LOG_FILE%" 2>&1"