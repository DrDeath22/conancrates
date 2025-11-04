from django.apps import AppConfig


class PackagesConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'packages'

    def ready(self):
        """Import signal handlers when Django starts"""
        import packages.signals  # noqa
