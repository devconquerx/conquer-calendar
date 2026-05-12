from django.apps import AppConfig


class AvailabilityConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'calendario.availability'
    label = 'availability'
    verbose_name = 'Disponibilidad'
