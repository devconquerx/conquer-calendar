import environ
import os
from pathlib import Path

env = environ.Env()

BASE_DIR = Path(__file__).resolve().parent.parent
ROOT_DIR = environ.Path(__file__) - 3
APPS_DIR = ROOT_DIR.path("calendario")

SECRET_KEY = env.str('CALENDARIO_DJANGO_SECRET_KEY', default='dev-insecure-please-change')
DEBUG = env.bool('CALENDARIO_DJANGO_DEBUG', default=True)

TIME_ZONE = "Europe/Madrid"
LANGUAGE_CODE = 'es'
USE_L10N = True
USE_I18N = True
USE_TZ = True

DJANGO_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django.contrib.sites',
]

THIRD_PARTY_APPS = [
    'crispy_forms',
    'ckeditor',
    'django_extensions',
    'django_json_widget',
    'django_vite',
    'rest_framework',
    'corsheaders',
    'allauth',
    'allauth.account',
    'allauth.socialaccount',
    'allauth.socialaccount.providers.google',
    'taggit',
    'django_celery_beat',
]

LOCAL_APPS = [
    # Tema Metronic (mismo que conquer-crm)
    'metronic',
    'layout',

    'calendario.core',
    'calendario.users',
    'calendario.permisos',
    'calendario.event_types',
    'calendario.availability',
    'calendario.bookings',
    'calendario.google_calendar',
    'calendario.grupos',
    'calendario.funnels',
    'calendario.leads',
    'calendario.monitoring',
]

INSTALLED_APPS = DJANGO_APPS + THIRD_PARTY_APPS + LOCAL_APPS
AUTH_USER_MODEL = 'users.User'
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'
SITE_ID = 1

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'calendario.users.middleware.StripTrailingDotHostMiddleware',
    'calendario.funnels.middleware.AppBasePathMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.locale.LocaleMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'allauth.account.middleware.AccountMiddleware',
]

ROOT_URLCONF = 'config.urls'
WSGI_APPLICATION = 'config.wsgi.application'

DATABASES = {
    "default": env.db("DATABASE_URL"),
}

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

STATICFILES_FINDERS = [
    "django.contrib.staticfiles.finders.FileSystemFinder",
    "django.contrib.staticfiles.finders.AppDirectoriesFinder",
]

STATIC_ROOT = str(ROOT_DIR("staticfiles"))
STATIC_URL = '/static/'

_FRONTEND_DIST = str(ROOT_DIR.path("frontend").path("dist"))
STATICFILES_DIRS = [
    str(ROOT_DIR.path("calendario").path("static")),
    _FRONTEND_DIST,  # populated by `npm run build`; Django 4.2 won't error if empty/missing files
]

DJANGO_VITE = {
    "default": {
        # dev_mode is overridden to True in local.py; prod defaults to False
        "dev_mode": env.bool("DJANGO_VITE_DEV_MODE", default=False),
        "dev_server_protocol": "http",
        "dev_server_host": "localhost",
        "dev_server_port": 5173,
        "manifest_path": os.path.join(_FRONTEND_DIST, ".vite", "manifest.json"),
    }
}

MEDIA_ROOT = "/calendario-media"
MEDIA_URL = "/media/"

CRISPY_TEMPLATE_PACK = 'bootstrap4'

from django.contrib.messages import constants as message_constants
MESSAGE_TAGS = {
    message_constants.DEBUG:   'secondary',
    message_constants.INFO:    'info',
    message_constants.SUCCESS: 'success',
    message_constants.WARNING: 'warning',
    message_constants.ERROR:   'danger',
}

TEMPLATES_DIR = str(APPS_DIR.path("_templates"))
TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [TEMPLATES_DIR],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'calendario.users.context_processors.calendario_context',
                'calendario.funnels.context_processors.pixel_ids',
            ],
            'libraries': {
                'theme': 'metronic.templatetags.theme',
            },
            'builtins': [
                'django.templatetags.static',
                'metronic.templatetags.theme',
            ],
        },
    },
]

# Email
EMAIL_BACKEND = env.str(
    'CALENDARIO_DJANGO_EMAIL_BACKEND',
    default='django.core.mail.backends.console.EmailBackend',
)
DEFAULT_FROM_EMAIL = env.str('CALENDARIO_DEFAULT_FROM_EMAIL', default='noreply@mg.conquerx.com')
SITE_URL = env.str('CALENDARIO_SITE_URL', default='http://localhost:8000')

MAILGUN_API_KEY = env.str('MAILGUN_API_KEY', default='')
ANYMAIL = {
    'MAILGUN_API_KEY': MAILGUN_API_KEY,
    'MAILGUN_SENDER_DOMAIN': env.str('MAILGUN_SENDER_DOMAIN', default='mg.conquerx.com'),
}

ADMIN_URL = "admin/"

AUTHENTICATION_BACKENDS = [
    'django.contrib.auth.backends.ModelBackend',
    'allauth.account.auth_backends.AuthenticationBackend',
]

ACCOUNT_LOGIN_METHODS = {"email"}
ACCOUNT_SIGNUP_FIELDS = ["email*", "password1*", "password2*"]
ACCOUNT_EMAIL_VERIFICATION = 'none'
SOCIALACCOUNT_EMAIL_VERIFICATION = 'none'

REST_FRAMEWORK = {
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 50,
    'DEFAULT_FILTER_BACKENDS': ['django_filters.rest_framework.DjangoFilterBackend'],
    'DEFAULT_RENDERER_CLASSES': (
        'rest_framework.renderers.JSONRenderer',
    ),
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework.authentication.SessionAuthentication',
        'rest_framework.authentication.BasicAuthentication',
    ],
}

CORS_ALLOW_ALL_ORIGINS = True
CORS_ALLOW_CREDENTIALS = True

# Origen público canónico del calendario (p.ej. https://calendar.conquerx.com).
# Cuando el funnel/booking se sirve embebido en un dominio de marca
# (conquerlegal.com, conquerblocks.com, …), el frontend antepone este origen a
# sus requests de API/slots para que vayan al backend del calendario en lugar de
# al dominio de marca (donde esas rutas no existen). Vacío = mismo origen (dev).
CALENDAR_PUBLIC_ORIGIN = env.str('CALENDARIO_PUBLIC_ORIGIN', default='')

SESSION_COOKIE_NAME = 'calendario_sessionid'

LOGIN_REDIRECT_URL = "/panel/"
LOGIN_URL = "/accounts/login/"
ACCOUNT_LOGOUT_REDIRECT_URL = "/accounts/login/"

# Google integration placeholders
GOOGLE_AUTH_CLIENT_ID = env.str('GOOGLE_AUTH_CLIENT_ID', default='')
GOOGLE_AUTH_CLIENT_SECRET = env.str('GOOGLE_AUTH_CLIENT_SECRET', default='')

# Google Calendar — Service Account + Domain-Wide Delegation
GOOGLE_SERVICE_ACCOUNT_FILE = env.str('GOOGLE_SERVICE_ACCOUNT_FILE', default='')
GOOGLE_CALENDAR_SCOPES = [
    'https://www.googleapis.com/auth/calendar',
    'https://www.googleapis.com/auth/meetings.space.created',
]
GOOGLE_CALENDAR_TIMEOUT_SECONDS = env.int('GOOGLE_CALENDAR_TIMEOUT_SECONDS', default=8)
GCAL_WEBHOOK_URL = env.str('GCAL_WEBHOOK_URL', default='')

CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.db.DatabaseCache',
        'LOCATION': 'cache_disponibilidad',
    }
}

# Mapa Host (dominio) → escuela, para resolver las rutas públicas raíz
# /clase-online-gratuita-<region>/ de languages y finance (que comparten path).
# Override por env: CALENDARIO_FUNNEL_HOST_ESCUELA="dominio=escuela,dominio2=escuela2"
FUNNEL_HOST_ESCUELA = env.dict('CALENDARIO_FUNNEL_HOST_ESCUELA', default={
    'conquerblocks.com': 'conquer-blocks',
    'www.conquerblocks.com': 'conquer-blocks',
    'conquerlanguages.com': 'conquer-languages',
    'www.conquerlanguages.com': 'conquer-languages',
    'conquerfinance.com': 'conquer-finance',
    'www.conquerfinance.com': 'conquer-finance',
})

# Prefijos de path bajo los que el funnel público también puede servirse,
# además de en la raíz (p.ej. /preview para pruebas detrás de Cloudflare ante
# Webflow en conquerblocks.com). AppBasePathMiddleware los detecta, los retira
# de PATH_INFO y los expone en request.app_base_path; las vistas anteponen ese
# prefijo a sus URLs de navegación. Vacío = el funnel solo se sirve en la raíz.
FUNNEL_BASE_PATHS = env.list('CALENDARIO_FUNNEL_BASE_PATHS', default=['/preview'])

# CRM webhook (Make)
CRM_WEBHOOK_URL = env.str('CRM_WEBHOOK_URL', default='')
CRM_WEBHOOK_API_KEY = env.str('CRM_WEBHOOK_API_KEY', default='')
CRM_WEBHOOK_TIMEOUT_SECONDS = env.int('CRM_WEBHOOK_TIMEOUT_SECONDS', default=8)

# ──────────────────────────────────────────────────────────────────────
# Tracking / conversiones (lead + schedule). Todas las claves tienen
# default '' → si faltan, cada integración hace no-op y loguea (igual que
# notificar_crm). El flujo de lead/booking nunca se rompe por falta de claves.
# ──────────────────────────────────────────────────────────────────────
META_ACCESS_TOKEN = env.str('META_ACCESS_TOKEN', default='')
ACTIVECAMPAIGN_API_URL = env.str('ACTIVECAMPAIGN_API_URL', default='')
ACTIVECAMPAIGN_API_KEY = env.str('ACTIVECAMPAIGN_API_KEY', default='')
NEVERBOUNCE_API_KEY = env.str('NEVERBOUNCE_API_KEY', default='')
RESPONDIO_API_KEY = env.str('RESPONDIO_API_KEY', default='')
GOOGLE_ADS_DEVELOPER_TOKEN = env.str('GOOGLE_ADS_DEVELOPER_TOKEN', default='')
GOOGLE_ADS_CLIENT_ID = env.str('GOOGLE_ADS_CLIENT_ID', default='')
GOOGLE_ADS_CLIENT_SECRET = env.str('GOOGLE_ADS_CLIENT_SECRET', default='')
GOOGLE_ADS_REFRESH_TOKEN = env.str('GOOGLE_ADS_REFRESH_TOKEN', default='')
GOOGLE_ADS_LOGIN_CUSTOMER_ID = env.str('GOOGLE_ADS_LOGIN_CUSTOMER_ID', default='')
# CRM ingest (distinto del webhook de Make de arriba)
CRM_BASE_URL = env.str('CRM_BASE_URL', default='https://crm.conquerx.com')
CRM_API_KEY = env.str('CRM_API_KEY', default='')
# Envío de la Prellamada al CRM ingest. Mientras esté en False, la task hace
# no-op y el sweep no la reintenta (evita loop). Ponlo en True cuando el CRM esté
# listo para recibir pre-schedules.
FUNNELS_PRESCHEDULE_CRM_ENABLED = env.bool('FUNNELS_PRESCHEDULE_CRM_ENABLED', default=False)

# ──────────────────────────────────────────────────────────────────────
# Supabase — respaldo rodante de lo que se envía al CRM (lead/preschedule/
# schedule), vía la REST API (PostgREST) con la secret key del lado servidor.
# Fail-safe: si SUPABASE_ENABLED=False o falta URL/secret, cada push hace no-op
# y loguea (el flujo de lead/booking nunca se rompe). Retención corta: una task
# periódica borra las filas con más de SUPABASE_RETENTION_DAYS días.
# ──────────────────────────────────────────────────────────────────────
SUPABASE_ENABLED = env.bool('SUPABASE_ENABLED', default=False)
SUPABASE_URL = env.str('SUPABASE_URL', default='')  # https://<ref>.supabase.co
SUPABASE_SECRET_KEY = env.str('SUPABASE_SECRET_KEY', default='')
SUPABASE_TIMEOUT_SECONDS = env.int('SUPABASE_TIMEOUT_SECONDS', default=15)
SUPABASE_RETENTION_DAYS = env.int('SUPABASE_RETENTION_DAYS', default=7)
SUPABASE_TABLE_LEADS = env.str('SUPABASE_TABLE_LEADS', default='leads_backup')
SUPABASE_TABLE_PRE_SCHEDULES = env.str('SUPABASE_TABLE_PRE_SCHEDULES', default='preschedules_backup')
SUPABASE_TABLE_SCHEDULES = env.str('SUPABASE_TABLE_SCHEDULES', default='schedules_backup')

# Monitoring / alertas de tasks
MONITORING_ENABLED = env.bool('MONITORING_ENABLED', default=False)
MONITORING_MAILGUN_DOMAIN = env.str('MONITORING_MAILGUN_DOMAIN', default='conquerblocks.com')
MONITORING_ALERT_RECIPIENTS = [
    r.strip() for r in env.str('MONITORING_ALERT_RECIPIENTS', default='').split(',') if r.strip()
]
SENTRY_ORG_URL = env.str('SENTRY_ORG_URL', default='')

# Celery
CELERY_BROKER_URL = env.str('CELERY_BROKER_URL', default='redis://redis:6379/0')
CELERY_RESULT_BACKEND = env.str('CELERY_RESULT_BACKEND', default='redis://redis:6379/0')
CELERY_ACCEPT_CONTENT = ['json']
CELERY_TASK_SERIALIZER = 'json'
CELERY_RESULT_SERIALIZER = 'json'
CELERY_TIMEZONE = 'UTC'
CELERY_TASK_TRACK_STARTED = True
CELERY_TASK_TIME_LIMIT = 120
CELERY_TASK_SOFT_TIME_LIMIT = 90
CELERY_BROKER_CONNECTION_RETRY_ON_STARTUP = True

CELERY_BEAT_SCHEDULE = {
    'sweep-incomplete-leads': {
        'task': 'calendario.leads.tasks.sweep_incomplete_leads',
        'schedule': 60.0,
    },
    'sweep-incomplete-reservas': {
        'task': 'calendario.bookings.tasks.sweep_incomplete_reservas',
        'schedule': 60.0,
    },
    'sweep-incomplete-prellamadas': {
        'task': 'calendario.funnels.tasks.sweep_incomplete_prellamadas',
        'schedule': 120.0,
    },
    'check-funnel-health': {
        'task': 'calendario.monitoring.tasks.check_funnel_health',
        'schedule': 300.0,
    },
    'purge-old-supabase-backups': {
        'task': 'calendario.core.tasks.purge_old_supabase_backups',
        'schedule': 3600.0,  # cada hora; borra lo más viejo que SUPABASE_RETENTION_DAYS
    },
}

SOCIALACCOUNT_ADAPTER = 'calendario.users.adapters.ConquerSocialAccountAdapter'
SOCIALACCOUNT_AUTO_SIGNUP = False
SOCIALACCOUNT_LOGIN_ON_GET = True

SOCIALACCOUNT_PROVIDERS = {
    "google": {
        'APP': {
            'client_id': GOOGLE_AUTH_CLIENT_ID,
            'secret': GOOGLE_AUTH_CLIENT_SECRET,
        },
        'EMAIL_AUTHENTICATION': True,
        'VERIFIED_EMAIL': True,
    }
}


######################
# Keenthemes / Metronic
######################

KT_THEME_DIR = 'layout'
KT_THEME_MODE_DEFAULT = 'light'
KT_THEME_MODE_SWITCH_ENABLED = True
KT_THEME_DIRECTION = 'ltr'

KT_THEME_ASSETS = {
    "favicon": "media/logos/favicon.ico",
    "fonts": [
        '/static/css/fonts.css',
    ],
    "css": [
        "plugins/global/plugins.bundle.css",
        "css/style.bundle.css",
    ],
    "js": [
        "plugins/global/plugins.bundle.js",
        "js/scripts.bundle.js",
    ],
}

KT_THEME_VENDORS = {
    "datatables": {
        "css": ["plugins/custom/datatables/datatables.bundle.css"],
        "js": ["plugins/custom/datatables/datatables.bundle.js"],
    },
    "fullcalendar": {
        "css": ["plugins/custom/fullcalendar/fullcalendar.bundle.css"],
        "js": ["plugins/custom/fullcalendar/fullcalendar.bundle.js"],
    },
    "formrepeater": {
        "js": ["plugins/custom/formrepeater/formrepeater.bundle.js"],
    },
    "bootstrap-select": {
        "css": ["plugins/custom/bootstrap-select/bootstrap-select.bundle.css"],
        "js": ["plugins/custom/bootstrap-select/bootstrap-select.bundle.js"],
    },
}

CKEDITOR_CONFIGS = {
    'default': {
        'toolbar': 'Custom',
        'toolbar_Custom': [
            ['Format'],
            ['Bold', 'Italic', 'Link', 'Unlink', 'BulletedList', 'NumberedList', 'RemoveFormat'],
            ['Undo', 'Redo', 'Source'],
        ],
    },
}
