from django.apps import AppConfig


class FunnelsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'calendario.funnels'
    label = 'funnels'
    verbose_name = 'Funnels'

    def ready(self):
        from . import signals  # noqa: F401
