@echo off
REM Run Django development server on all interfaces (localhost + LAN)
REM Usage: run.bat
REM Access: http://localhost:8000 or http://<your-ip>:8000 from LAN devices

cd /d "%~dp0"
echo Starting Django development server...
echo Local: http://localhost:8000
echo To find your IP, run: ipconfig (Windows)
echo Then access from LAN: http://^<your-ip^>:8000
echo Press Ctrl+C to stop the server
echo.
call venv\Scripts\activate.bat
python manage.py runserver 0.0.0.0:8000
pause
