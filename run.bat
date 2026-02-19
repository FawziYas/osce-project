@echo off
REM Run Django development server on localhost:8000
cd /d "%~dp0"
call venv\Scripts\activate.bat
python manage.py runserver localhost:8000
pause
