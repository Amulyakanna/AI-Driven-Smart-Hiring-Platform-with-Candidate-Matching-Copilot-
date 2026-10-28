@echo off
setlocal
cd /d "%~dp0"
if not exist "venv\Scripts\python.exe" (
  echo Creating Python virtual environment...
  python -m venv venv
  if errorlevel 1 goto error
)
call "venv\Scripts\activate.bat"
python -m pip install --upgrade pip
if errorlevel 1 goto error
pip install -r requirements.txt
if errorlevel 1 goto error
echo.
echo Starting AI Recruitment Copilot at http://127.0.0.1:5000
python app.py
goto end
:error
echo.
echo Setup failed. Check that Python is installed and available as "python".
:end
pause
endlocal
