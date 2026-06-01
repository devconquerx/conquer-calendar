import environ
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
    'rest_framework',
    'corsheaders',
    'allauth',
    'allauth.account',
    'allauth.socialaccount',
    'allauth.socialaccount.providers.google',
]

LOCAL_APPS = [
    # Tema Metronic (mismo que conquer-crm)
    'metronic',
    'layout',

    'calendario.users',
    'calendario.permisos',
    'calendario.event_types',
    'calendario.availability',
    'calendario.bookings',
    'calendario.google_calendar',
]

INSTALLED_APPS = DJANGO_APPS + THIRD_PARTY_APPS + LOCAL_APPS
AUTH_USER_MODEL = 'users.User'
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'
SITE_ID = 1

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'calendario.users.middleware.StripTrailingDotHostMiddleware',
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
STATICFILES_DIRS = [
    str(ROOT_DIR.path("calendario").path('static')),
]

MEDIA_ROOT = "/calendario-media"
MEDIA_URL = "/media/"

CRISPY_TEMPLATE_PACK = 'bootstrap4'

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

# Email (placeholder; se configurará con un proveedor real en fases posteriores)
EMAIL_BACKEND = env.str(
    'CALENDARIO_DJANGO_EMAIL_BACKEND',
    default='django.core.mail.backends.console.EmailBackend',
)

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

# CRM webhook (Make)
CRM_WEBHOOK_URL = env.str('CRM_WEBHOOK_URL', default='')
CRM_WEBHOOK_API_KEY = env.str('CRM_WEBHOOK_API_KEY', default='')
CRM_WEBHOOK_TIMEOUT_SECONDS = env.int('CRM_WEBHOOK_TIMEOUT_SECONDS', default=8)

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
        'https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap',
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
