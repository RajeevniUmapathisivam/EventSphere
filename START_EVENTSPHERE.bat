@echo off
setlocal
cd /d "%~dp0backend" || exit /b 1
if exist ".venv\Scripts\python.exe" goto dependencies

where py >nul 2>&1
if errorlevel 1 goto fallback
py -3 -c "import sys; raise SystemExit(sys.version_info < (3, 11))" >nul 2>&1
if errorlevel 1 goto fallback
py -3 -m venv .venv || goto failed
goto dependencies

:fallback
python -c "import sys; raise SystemExit(sys.version_info < (3, 11))" >nul 2>&1
if errorlevel 1 (
    echo Install Python 3.11 or later and select Add Python to PATH, then run this file again.
    pause
    exit /b 1
)
python -m venv .venv || goto failed

:dependencies
".venv\Scripts\python.exe" -c "import fastapi, uvicorn, sqlalchemy, dotenv, email_validator, qrcode, PIL, psycopg, pytest, httpx" >nul 2>&1
if errorlevel 1 (
    echo Installing EventSphere dependencies. The first setup needs internet access.
    ".venv\Scripts\python.exe" -m pip install --disable-pip-version-check -r requirements.txt || goto failed
)

echo Open http://127.0.0.1:8000 in your browser.
echo Keep this window open while you use EventSphere. Press Ctrl+C to stop.
".venv\Scripts\python.exe" -m uvicorn app.main:app --host 127.0.0.1 --port 8000
if errorlevel 1 goto failed
exit /b 0

:failed
echo EventSphere could not start. See the error above and the setup steps in README.md.
pause
exit /b 1
