"""Production settings."""

import sentry_sdk

from .base import *  # NOQA
from .base import env

DEBUG = False

# ---------------------------------------------------------------------------
# Sentry — error tracking + performance monitoring
# ---------------------------------------------------------------------------
sentry_sdk.init(
    dsn=env.str('SENTRY_DSN', default=''),
    send_default_pii=False,
    traces_sample_rate=0.2,
    profiles_sample_rate=0.1,
    environment=env.str('SENTRY_ENVIRONMENT', default='production'),
)

ALLOWED_HOSTS = env.list(
    'CALENDARIO_ALLOWED_HOSTS',
    default=['calendar.conquerx.com'],
)
CSRF_TRUSTED_ORIGINS = env.list(
    'CALENDARIO_CSRF_TRUSTED_ORIGINS',
    default=['https://calendar.conquerx.com'],
)

SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
USE_X_FORWARDED_HOST = True

SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_BROWSER_XSS_FILTER = True

SECURE_HSTS_INCLUDE_SUBDOMAINS = env.bool(
    'CALENDARIO_SECURE_HSTS_INCLUDE_SUBDOMAINS',
    default=False,
)
SECURE_HSTS_PRELOAD = env.bool('CALENDARIO_SECURE_HSTS_PRELOAD', default=False)
SECURE_HSTS_SECONDS = env.int('CALENDARIO_SECURE_HSTS_SECONDS', default=3600)

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    *MIDDLEWARE[1:],
]

STATICFILES_STORAGE = 'whitenoise.storage.CompressedStaticFilesStorage'

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
        },
    },
    'root': {'handlers': ['console'], 'level': 'INFO'},
    'loggers': {
        'django': {'handlers': ['console'], 'level': 'INFO', 'propagate': False},
        'calendario': {'handlers': ['console'], 'level': 'INFO', 'propagate': False},
    },
}
