import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'osce_project.settings')
django.setup()

from core.models import Station

deleted = Station.objects.filter(is_deleted=True).count()
total = Station.objects.all().count()

print(f'Total stations: {total}')
print(f'Soft-deleted stations: {deleted}')
print()

if deleted > 0:
    deleted_stations = Station.objects.filter(is_deleted=True).values('id', 'name', 'station_number', 'deleted_at')
    for s in deleted_stations:
        print(f"ID: {s['id']}, Name: {s['name']}, Number: {s['station_number']}, Deleted: {s['deleted_at']}")
