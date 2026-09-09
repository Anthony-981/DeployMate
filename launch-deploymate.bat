@echo off
setlocal
cd /d "%~dp0"

set "PY=C:\Users\Tom\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"
if exist "%~dp0build-env-68\Scripts\python.exe" set "PY=%~dp0build-env-68\Scripts\python.exe"

rem Development launcher: always run source code with the development database.
set "DEPLOYMATE_DB_MODE=dev"

if exist "%PY%" (
    "%PY%" src\main.py
) else (
    python src\main.py
)

pause
