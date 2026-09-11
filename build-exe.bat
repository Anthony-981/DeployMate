@echo off
setlocal
cd /d "%~dp0"

set "PY=C:\Users\Tom\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"
if not exist "%PY%" set "PY=python"
if exist "%~dp0build-env-68\Scripts\python.exe" set "PY=%~dp0build-env-68\Scripts\python.exe"
set "DEPLOYMATE_DB_MODE=prod"
set "DEPLOYMATE_DATA_DIR=%TEMP%\DeployMate-build-empty-%RANDOM%-%RANDOM%"
if exist "%DEPLOYMATE_DATA_DIR%" rmdir /s /q "%DEPLOYMATE_DATA_DIR%"

echo [1/3] Checking PyInstaller...
"%PY%" -m PyInstaller --version >nul 2>&1
if errorlevel 1 (
    echo PyInstaller is not installed.
    echo Run: "%PY%" -m pip install pyinstaller pillow
    pause
    exit /b 1
)

echo [2/3] Creating logo.ico from logo.png...
"%PY%" -c "from PIL import Image; Image.open('logo.png').convert('RGBA').save('logo.ico', sizes=[(256,256),(128,128),(64,64),(32,32),(16,16)])"
if errorlevel 1 (
    echo Failed to create logo.ico. Install Pillow first.
    pause
    exit /b 1
)

echo [3/3] Building portable DeployMate.exe...
echo Database mode: production (packaged application)
if exist "dist-portable" rmdir /s /q "dist-portable"
if exist "build-portable" rmdir /s /q "build-portable"
"%PY%" -m PyInstaller --noconfirm --clean --distpath dist-portable --workpath build-portable deploymate.spec
if errorlevel 1 (
    echo Build failed.
    pause
    exit /b 1
)

copy /y "dist-portable\DeployMate.exe" "DeployMate.exe" >nul
for /r "dist-portable" %%F in (*.db *.db-wal *.db-shm *.db-journal) do (
    echo Build contains forbidden database file: %%F
    exit /b 1
)
if exist "%DEPLOYMATE_DATA_DIR%" rmdir /s /q "%DEPLOYMATE_DATA_DIR%"
echo Build complete: %CD%\dist-portable\DeployMate.exe
echo Latest portable file: %CD%\DeployMate.exe
pause
