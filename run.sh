#!/bin/bash
# Run Django development server on all interfaces (localhost + LAN)
# Usage: ./run.sh
# Access: http://localhost:8000 or http://<your-ip>:8000 from LAN devices

echo "Starting Django development server..."
echo "Local: http://localhost:8000"
echo "To find your IP, run: ipconfig (Windows) or ifconfig (Linux/Mac)"
echo "Then access from LAN: http://<your-ip>:8000"
echo "Press Ctrl+C to stop the server"

source venv/Scripts/activate
python manage.py runserver 0.0.0.0:8000
