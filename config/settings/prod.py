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

# Enlaces del panel /funnels/ hacia el dominio real de cada marca. Se usa el
# subdominio www porque las rutas del worker en Cloudflare están dadas de alta
# como `*.dominio/...` y ese comodín NO cubre el ápice. Blocks, Legal y Finance
# ya se sirven en la raíz de su dominio; Languages sigue detrás de /preview
# hasta que se le den de alta las rutas definitivas — cuando pase, basta con
# quitarle el sufijo aquí. Especialización y Kids no tienen dominio propio:
# viven bajo el de su marca madre.
if not FUNNEL_PUBLIC_BASE:  # NOQA: F405 — viene de base.py, vacío salvo override por env
    FUNNEL_PUBLIC_BASE = {
        'conquer-blocks': 'https://www.conquerblocks.com',
        'conquer-blocks-esp': 'https://www.conquerblocks.com',
        'conquer-finance': 'https://www.conquerfinance.com',
        'conquer-legal': 'https://www.conquerlegal.com',
        'conquer-languages': 'https://www.conquerlanguages.com/preview',
        'conquer-languages-kids': 'https://www.conquerlanguages.com/preview',
    }

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

# Nombres versionados por hash: al cambiar un estático cambia su URL, así que el
# navegador (y cualquier CDN por delante) sirve la versión nueva sin recarga forzada.
STATICFILES_STORAGE = 'config.storage.TolerantManifestStaticFilesStorage'

# Ya identificados por su hash, los estáticos se pueden cachear indefinidamente.
WHITENOISE_MAX_AGE = 31536000

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
