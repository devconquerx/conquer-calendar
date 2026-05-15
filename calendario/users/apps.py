import logging

from django.apps import AppConfig


logger = logging.getLogger(__name__)


def _patch_socialaccount_error_logging():
    """Temporal: loguea la excepción real cuando allauth renderea authentication_error."""
    from allauth.socialaccount import helpers as _helpers

    original = _helpers.render_authentication_error

    def _logged(request, provider, error=None, exception=None, extra_context=None):
        logger.warning(
            "allauth authentication_error: provider=%s error=%r exception=%r",
            provider, error, exception,
            exc_info=exception if isinstance(exception, BaseException) else None,
        )
        return original(request, provider, error=error, exception=exception, extra_context=extra_context)

    _helpers.render_authentication_error = _logged


class UsersConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'calendario.users'
    label = 'users'
    verbose_name = 'Usuarios'

    def ready(self):
        import calendario.users.signals  # noqa: F401
        _patch_socialaccount_error_logging()
