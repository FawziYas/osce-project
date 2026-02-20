from django.apps import AppConfig


class CoreConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'core'
    verbose_name = 'OSCE Core'

    def ready(self):
        # Import signal handlers so they are connected on startup
        import core.signals  # noqa: F401
