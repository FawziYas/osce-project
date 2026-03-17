import django, os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'osce_project.settings.production')
django.setup()
from django.core.files.storage import default_storage
print('BACKEND:', type(default_storage).__name__)
try:
    print('URL:', default_storage.url('test.jpg'))
except Exception as e:
    print('URL_ERROR:', e)
