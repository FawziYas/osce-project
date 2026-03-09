# Import the Celery app so it is always loaded when Django starts,
# enabling the @shared_task decorator in app task modules.
from .celery import app as celery_app

__all__ = ('celery_app',)
