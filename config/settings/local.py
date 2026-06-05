"""Local development settings."""

from .base import *  # NOQA
from .base import env

DEBUG = env.bool('CALENDARIO_DJANGO_DEBUG', default=True)

ALLOWED_HOSTS = ["*"]

# Vite dev server (HMR) on localhost:5173
DJANGO_VITE["default"]["dev_mode"] = True  # noqa: F821

CSRF_TRUSTED_ORIGINS = [
    'http://*',
    'https://*',
]

TEMPLATES[0]['OPTIONS']['debug'] = DEBUG  # NOQA

X_FRAME_OPTIONS = 'SAMEORIGIN'

DATA_UPLOAD_MAX_MEMORY_SIZE = None

CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.db.DatabaseCache',
        'LOCATION': 'cache_disponibilidad',
    }
}

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "root": {"level": "DEBUG", "handlers": ["console", "file"]},
    "handlers": {
        "console": {
            "level": "DEBUG",
            "class": "logging.StreamHandler",
            "formatter": "app",
        },
        "file": {
            "level": "DEBUG",
            "class": "logging.FileHandler",
            "filename": "/calendario_logs/django.log",
            "formatter": "app",
        },
    },
    "loggers": {
        "django": {"handlers": ["console", "file"], "level": "INFO", "propagate": True},
        "django.db.backends": {"handlers": [], "level": "WARNING", "propagate": False},
        "calendario": {"handlers": ["console", "file"], "level": "DEBUG", "propagate": True},
    },
    "formatters": {
        "app": {
            "format": (
                u"%(asctime)s [%(levelname)-8s] "
                "(%(module)s.%(funcName)s) %(message)s"
            ),
            "datefmt": "%Y-%m-%d %H:%M:%S",
        },
    },
}
