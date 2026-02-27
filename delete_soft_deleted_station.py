import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'osce_project.settings')
django.setup()

from core.models import Station

station_id = '72506016-5e3f-45b7-a654-1d8cdc3cedd1'
station = Station.objects.filter(id=station_id).first()

if station:
    print(f"Deleting station: {station.name} (ID: {station.id})")
    station.delete()
    print("✓ Station permanently deleted from database")
else:
    print("Station not found")
