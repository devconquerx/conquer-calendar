"""Production settings (placeholder — completar al desplegar)."""

from .base import *  # NOQA
from .base import env

DEBUG = False
ALLOWED_HOSTS = env.list('CALENDARIO_ALLOWED_HOSTS', default=[])
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
