from django.apps import AppConfig


class EventTypesConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'calendario.event_types'
    label = 'event_types'
    verbose_name = 'Tipos de evento'
