from django.apps import AppConfig


class LeadsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'calendario.leads'
    verbose_name = 'Leads'

    def ready(self):
        from . import signals  # noqa: F401
