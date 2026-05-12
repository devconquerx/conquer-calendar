from django.apps import AppConfig


class GoogleCalendarConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'calendario.google_calendar'
    label = 'google_calendar'
    verbose_name = 'Integración Google Calendar'
