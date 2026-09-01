import environ
import os
import sys
from pathlib import Path

env = environ.Env()

# True solo cuando la suite está corriendo (`manage.py test`). Sirve para que el
# código que sale a la red no lo haga en los tests: cada llamada real a Google
# cuesta segundos y acaba en un error de credenciales que no prueba nada. Lo
# consultan sitios muy concretos —el post_save que sincroniza un host nuevo y
# obtener_servicio_calendar—, no es un interruptor para saltarse lógica de
# negocio.
#
# Se mira SOLO el subcomando, no `'test' in sys.argv`: así ningún comando de
# management que reciba "test" como argumento puede encenderla por accidente.
# Encendida en producción, la app dejaría de ver la ocupación real del
# calendario y aceptaría reservas encima de eventos que ya existen, sin ruido
# ninguno. Vale la pena que la condición sea estrecha.
TESTING = sys.argv[1:2] == ['test']

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
    'calendario.funnels.middleware.FunnelPublicCoopMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    # Antes del CsrfViewMiddleware: marca la petición como exenta cuando trae un
    # token válido del LMS (el iframe cross-site no manda la cookie csrftoken).
    'calendario.bookings.middleware.EmbedCsrfMiddleware',
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

# Conexiones persistentes. Sin esto Django abre un TCP+TLS nuevo contra el Postgres
# gestionado en cada request: ~25 ms de handshake que Sentry venía marcando como
# "N+1 Query" sobre el span `connect`, y un churn de conexiones que llegó a agotar
# los slots del servidor. El pool queda acotado por el número de procesos
# (3 gunicorn + 4 celery + beat), muy por debajo del max_connections=50.
DATABASES["default"]["CONN_MAX_AGE"] = env.int("CALENDARIO_DB_CONN_MAX_AGE", default=60)
DATABASES["default"]["CONN_HEALTH_CHECKS"] = True

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

# SSR del funnel (servicio Node). FUNNEL_SSR_ENABLED es el switch maestro; el
# allowlist (set de "escuela:stage", o "*" para todas) controla el rollout
# gradual. Si está off / no allowlisted / el servicio falla, Django sirve
# #funnel-root vacío → CSR (el comportamiento de hoy). Reversible sin redeploy.
FUNNEL_SSR_ENABLED = env.bool("FUNNEL_SSR_ENABLED", default=False)
FUNNEL_SSR_URL = env("FUNNEL_SSR_URL", default="http://node-ssr:3000/render")
FUNNEL_SSR_TIMEOUT = env.float("FUNNEL_SSR_TIMEOUT", default=0.4)
FUNNEL_SSR_ALLOWLIST = set(
    env.list("FUNNEL_SSR_ALLOWLIST", default=["conquer-legal:landing"])
)

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
# Las API keys de Mailgun están atadas a una región: la key de EEUU lee los
# dominios europeos pero al enviar por ellos devuelve 401 Forbidden. Cada región
# necesita la suya, y los dominios de envío (DominioRemitente) declaran en cuál
# viven. Vacío = se usa MAILGUN_API_KEY, que es el comportamiento de siempre.
MAILGUN_API_KEY_POR_REGION = {
    'us': env.str('MAILGUN_API_KEY_US', default=''),
    'eu': env.str('MAILGUN_API_KEY_EU', default=''),
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

# Base pública desde la que se sirve cada escuela, para los enlaces del panel
# /funnels/. Es la URL COMPLETA, prefijo incluido: unas marcas ya están cortadas
# en la raíz de su dominio y otras siguen bajo /preview mientras dura el corte
# en Cloudflare, así que el prefijo va aquí y no se calcula. Sin entrada para una
# escuela, sus enlaces salen relativos (mismo dominio que el panel), que es lo
# que hace falta en local: por eso el default va vacío y los dominios reales se
# fijan en prod.py — si no, el panel de local abriría producción.
# Override por env: CALENDARIO_FUNNEL_PUBLIC_BASE="escuela=https://dominio,…"
FUNNEL_PUBLIC_BASE = env.dict('CALENDARIO_FUNNEL_PUBLIC_BASE', default={})


# ──────────────────────────────────────────────────────────────────────
# Tracking / conversiones (lead + schedule). Todas las claves tienen
# default '' → si faltan, cada integración hace no-op y loguea. El flujo de
# lead/booking nunca se rompe por falta de claves.
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
# CRM ingest (crm.conquerx.com/api/v1/ingest/...)
CRM_BASE_URL = env.str('CRM_BASE_URL', default='https://crm.conquerx.com')
CRM_API_KEY = env.str('CRM_API_KEY', default='')
# Interruptor global y hardcodeado del envío al CRM ingest. Del que beben los TRES
# procesos: lead (process_crm_send), prellamada (process_pre_schedule_crm) y
# llamada/reserva (process_schedule_crm). Mientras esté en False las tasks hacen
# no-op y los sweeps no las reintentan (evita loop). Cámbialo aquí para
# prender/apagar los tres a la vez.
CRM_INGEST_ENABLED = True

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

# Desde cuándo el sync puede cancelar una reserva porque el host rechazó la
# invitación en Google Calendar. Solo se tocan reservas CREADAS después de esta
# fecha: el sync incremental trae cualquier evento modificado, no solo los
# rechazos recientes, así que sin este corte se cancelaría el histórico entero
# de golpe (pasó el 20/08/2026). Vacío = el sync no cancela nada.
CANCELAR_RECHAZOS_DESDE = env.str('CANCELAR_RECHAZOS_DESDE', default='')

# Lo mismo para el rechazo del INVITADO, que se añadió después y tiene su propio
# interruptor a propósito. Dos razones: los "No" de invitados acumulados son
# muchos más que los de hosts, y el corte del host ya lleva tiempo puesto y
# funcionando —moverlo para estrenar esto apagaría cancelaciones de host que hoy
# salen bien—. Vacío = el rechazo del invitado no cancela nada, que es como debe
# llegar a producción: se enciende poniendo la fecha del despliegue, y así solo
# actúa sobre lo que se reserve a partir de ese momento.
CANCELAR_RECHAZOS_INVITADO_DESDE = env.str('CANCELAR_RECHAZOS_INVITADO_DESDE', default='')

# Quién puede ver el registro de cancelaciones en el panel.
CANCELACIONES_EMAILS_AUTORIZADOS = [
    e.strip().lower()
    for e in env.str(
        'CANCELACIONES_EMAILS_AUTORIZADOS',
        default='santiago.tovar@conquerx.com,bienvenido.saez@conquerx.com',
    ).split(',')
    if e.strip()
]

# ---------------------------------------------------------------------------
# Embebido del calendario en el LMS de la academia (iframe)
# ---------------------------------------------------------------------------
# Los tipos de evento marcados como «solo alumnos» únicamente se pueden reservar
# desde dentro de la academia. El LMS firma un token con estos mismos parámetros
# (django.core.signing) y lo pasa en la URL del iframe; aquí solo se verifica la
# firma. No hay copia de los alumnos ni sincronización entre las dos apps: la
# decisión de quién puede reservar vive en el LMS, que sencillamente no emite
# token a quien no tiene el acceso al día.
#
# SECRET y SALT tienen que coincidir EXACTAMENTE con los del LMS o la firma no
# valida. Sin secreto configurado, ningún token se da por bueno: los tipos de
# evento «solo alumnos» quedan cerrados en vez de abiertos, que es como debe
# fallar esto si alguien despliega sin la variable.
EMBED_LMS_SECRET = env.str('CALENDARIO_EMBED_LMS_SECRET', default='')
EMBED_LMS_SALT = env.str('CALENDARIO_EMBED_LMS_SALT', default='lms-embed')

# Secretos ADICIONALES que también se dan por buenos al verificar. El LMS tiene
# un entorno de pruebas con su propia clave, y sin esto habría que elegir: o
# Daniel prueba, o reservan los alumnos.
#
# Se aceptan todos, sin mirar de dónde viene la petición, porque el origen de un
# iframe no es comprobable en el servidor: `frame-ancestors` lo aplica el
# navegador y el `Referer` se falsifica trivialmente fuera de uno. Atar cada
# clave a su dominio parecería más seguro y no lo sería —bastaría con omitir la
# cabecera—, así que la única frontera real es quién tiene cada secreto.
#
# La consecuencia hay que tenerla presente: quien tenga la clave de pruebas
# puede firmar un token bueno contra producción. Se queda aquí mientras el LMS
# esté en despliegue; cuando deje de hacer falta, se vacía la variable.
EMBED_LMS_SECRETS_EXTRA = env.list('CALENDARIO_EMBED_LMS_SECRETS_EXTRA', default=[])

# Cuánto vale un token desde que el LMS lo emite. Es la ventana entera para
# elegir hueco y confirmar, no solo para abrir la página: si se queda corta, a
# quien deje la pestaña abierta un rato le falla el envío del formulario. Una
# hora es holgada y apenas cuesta nada en seguridad, porque el nombre y el email
# de la reserva salen del token y no se pueden tocar desde el formulario.
EMBED_LMS_MAX_AGE = env.int('CALENDARIO_EMBED_LMS_MAX_AGE', default=3600)

# Orígenes desde los que se permite embeber la página de reserva (cabecera
# `frame-ancestors`). Sin esto Django manda `X-Frame-Options: DENY` y el iframe
# sale en blanco aunque el token sea perfecto. Van con esquema y sin barra
# final, p. ej. 'https://academia.conquerx.com'.
EMBED_LMS_ORIGENES = env.list('CALENDARIO_EMBED_LMS_ORIGENES', default=[])
