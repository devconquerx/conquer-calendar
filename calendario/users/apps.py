from django.apps import AppConfig


class UsersConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'calendario.users'
    label = 'users'
    verbose_name = 'Usuarios'

    def ready(self):
        import calendario.users.signals  # noqa: F401
