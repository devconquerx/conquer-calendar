"""Respaldo en Supabase: requests en crudo + objetos completos.

La idea es no perder nunca nada de lo que manda el frontend, aunque mañana cambie
lo que manda:

- **Requests en crudo** (tablas `requests` y `video_progress`): cada petición de
  escritura que llega de fuera (método, ruta, query, TODOS los headers, body, IP,
  país) tal cual, más la respuesta que dimos y qué objetos creó o tocó. No
  depende de ninguna columna: si el frontend añade un campo, queda guardado.
- **Objetos completos** (tablas `leads`, `prellamadas`, `reservas`): todos los
  campos del modelo en un jsonb `datos`, no una lista fija de columnas. Se
  reescriben en cada cambio.

Aquí no se guarda nada en la base de datos de calendar: la captura viaja en la
tarea de Celery hasta Supabase (con la protección de calendario/core/resiliencia.py).

Aquí se mandan siempre las filas completas. Que nada se guarde dos veces (los
mismos headers en cada petición, el lead repitiendo el body que lo creó...) lo
resuelven los triggers de Supabase; para leer las filas enteras están las vistas
*_completo. Ver docs/supabase_backup_schema.sql.
"""
import base64
import contextvars
import json
import logging
import uuid

from django.core.serializers.json import DjangoJSONEncoder
from django.utils import timezone

logger = logging.getLogger(__name__)

# Rutas que NO son del frontend público: panel, admin, login, webhooks de Google.
RUTAS_EXCLUIDAS = (
    '/panel/', '/admin/', '/accounts/', '/acceder-como/', '/webhooks/', '/health/',
    '/static/', '/media/', '/__debug__/',
)
RUTA_VIDEO_PROGRESS = '/f/api/video-progress/'
METODOS = {'POST', 'PUT', 'PATCH', 'DELETE'}

# Un body mayor no se guarda entero (uploads): se deja constancia del tamaño.
MAX_BODY = 1024 * 1024

_captura = contextvars.ContextVar('respaldo_captura', default=None)


# ---------------------------------------------------------------------------
# Captura del request
# ---------------------------------------------------------------------------
def debe_capturarse(request):
    ruta = request.path
    return request.method in METODOS and not ruta.startswith(RUTAS_EXCLUIDAS)


def _ip(request):
    for cabecera in ('HTTP_CF_CONNECTING_IP', 'HTTP_X_REAL_IP'):
        if request.META.get(cabecera):
            return request.META[cabecera]
    xff = request.META.get('HTTP_X_FORWARDED_FOR', '')
    return xff.split(',')[0].strip() if xff else request.META.get('REMOTE_ADDR')


def capturar(request):
    """Todo lo que trae la petición, sin interpretar nada."""
    fila = {
        'id': str(uuid.uuid4()),
        'recibido_en': timezone.now().isoformat(),
        'metodo': request.method,
        # Tal cual llegó: get_host() lanza DisallowedHost con hosts no permitidos
        # (bots que atacan la IP), y esas peticiones también se guardan.
        'host': request.META.get('HTTP_HOST'),
        'ruta': request.path,
        'query': {k: request.GET.getlist(k) for k in request.GET},
        'headers': dict(request.headers),
        'ip': _ip(request),
        'pais': request.META.get('HTTP_CF_IPCOUNTRY'),
        'body': None,
        'body_texto': None,
    }
    try:
        largo = int(request.META.get('CONTENT_LENGTH') or 0)
    except ValueError:
        largo = 0
    if largo > MAX_BODY:
        fila['body_texto'] = f'<body de {largo} bytes: no se guarda>'
        return _sin_nulos(fila)
    crudo = request.body
    try:
        fila['body'] = json.loads(crudo) if crudo else None
    except (ValueError, UnicodeDecodeError):
        try:
            fila['body_texto'] = crudo.decode('utf-8')
        except UnicodeDecodeError:
            fila['body_texto'] = 'base64:' + base64.b64encode(crudo).decode()
    if b'\x00' in crudo or b'\\u0000' in crudo:
        # Postgres no admite el carácter nulo ni en text ni en jsonb (Supabase
        # responde 400 y la fila se pierde). Se guarda el body exacto en base64
        # y, en el resto, el nulo queda escrito como el texto "\u0000".
        fila['body_texto'] = 'base64:' + base64.b64encode(crudo).decode()
    return _sin_nulos(fila)


def _sin_nulos(valor):
    if isinstance(valor, str):
        return valor.replace('\x00', '\\u0000')
    if isinstance(valor, dict):
        return {_sin_nulos(k): _sin_nulos(v) for k, v in valor.items()}
    if isinstance(valor, list):
        return [_sin_nulos(v) for v in valor]
    return valor


# Tareas de respaldo de objetos → tipo con el que se anotan en la captura.
TIPO_DE_TAREA = {
    'calendario.leads.tasks.process_supabase': 'lead',
    'calendario.funnels.tasks.process_pre_schedule_supabase': 'prellamada',
    'calendario.bookings.tasks.process_schedule_supabase': 'reserva',
}


def al_encolar(nombre_tarea, args):
    """Lo llama TareaResiliente.apply_async: si dentro de una petición se encola
    el respaldo de un objeto, esa petición lo generó o lo tocó."""
    tipo = TIPO_DE_TAREA.get(nombre_tarea)
    if tipo and args:
        registrar_objeto(tipo, args[0])


def registrar_objeto(tipo, pk):
    """Lo llaman los despachos de Supabase: qué objeto generó o tocó esta petición."""
    captura = _captura.get()
    if captura is not None and pk is not None:
        par = [tipo, pk]
        if par not in captura['objetos']:
            captura['objetos'].append(par)


class RespaldoRequestsMiddleware:
    """Captura en crudo las peticiones de escritura del frontend y, al terminar,
    encola su subida a Supabase. Nunca rompe la petición: cualquier fallo aquí se
    loguea y la petición sigue como si el middleware no existiera."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        fila = None
        try:
            if debe_capturarse(request):
                fila = capturar(request)
                fila['objetos'] = []
        except Exception:
            logger.exception('[Respaldo] No se pudo capturar %s %s', request.method, request.path)
            fila = None

        token = _captura.set(fila)
        try:
            response = self.get_response(request)
        finally:
            _captura.reset(token)

        if fila is not None:
            try:
                fila['status'] = response.status_code
                tabla = 'video_progress' if request.path == RUTA_VIDEO_PROGRESS else 'requests'
                from calendario.core.tasks import process_request_supabase
                process_request_supabase.delay(tabla, fila)
            except Exception:
                logger.exception('[Respaldo] No se pudo encolar el respaldo de %s', request.path)
        return response


# ---------------------------------------------------------------------------
# Objetos completos
# ---------------------------------------------------------------------------
def serializar(obj):
    """Todos los campos del modelo (los que tenga hoy y los que se le añadan)."""
    datos = {}
    for campo in obj._meta.concrete_fields:
        datos[campo.attname] = getattr(obj, campo.attname)
    if hasattr(obj, 'tags'):
        try:
            # .all() aprovecha el prefetch_related si lo hay (respaldar_supabase).
            datos['tags'] = sorted(t.name for t in obj.tags.all())
        except Exception:
            pass
    return json.loads(json.dumps(datos, cls=DjangoJSONEncoder))


def fila_de_objeto(obj, creado):
    return {
        'source_id': obj.pk,
        'created_at': creado.isoformat() if creado else timezone.now().isoformat(),
        'updated_at': timezone.now().isoformat(),
        'datos': serializar(obj),
        # `datos` va entero: lo que ya está en el body de un request lo quita el
        # trigger de Supabase y lo anota en estas columnas. Se mandan vacías para
        # que el upsert las reescriba junto con `datos` y nunca queden desparejas.
        'request_id': None,
        'fuera_del_request': None,
        'renombradas': None,
    }
