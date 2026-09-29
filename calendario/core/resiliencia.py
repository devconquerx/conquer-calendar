"""Protección de la cola de Celery: que un servicio caído nunca trabe a los demás.

Nace del incidente del 28-sep-2026. ActiveCampaign empezó a dar timeouts, sus
tareas ocuparon los 4 huecos del único worker, y en cuanto la cola pasó de 5
minutos de retraso los sweeps empezaron a reencolar cada minuto todo lo que
faltaba, sin saber que ya estaba en la cola: 115.000 tareas, prellamadas y
reservas llegando al CRM con horas de retraso y el propio monitor atascado en la
misma cola sin poder avisar.

Cada pieza de este módulo cierra una de las vías por las que eso puede volver a
pasar:

1. **Colas separadas** (`RUTAS`): lo que va al CRM y lo que vigila el sistema
   tienen su propia cola y su propio worker. Nada de marketing puede ponerse
   delante.
2. **Una sola copia pendiente por tarea** (`reservar_pendiente`): encolar dos
   veces la misma tarea con los mismos argumentos no crea dos mensajes. Los
   sweeps ya no pueden multiplicar la cola.
3. **Tope de huecos por servicio** (`ocupar_hueco`): un servicio no puede
   ocupar más de N procesos del worker a la vez. Si está lento, se come sus
   huecos y el resto sigue.
4. **Ritmo por servicio compartido entre workers** (`tomar_turno`): sustituye
   al `rate_limit` de Celery, que retiene las tareas en memoria del worker y
   bloquea su prefetch.
5. **Cortacircuitos** (`circuito_abierto`): si un servicio falla seguido o
   devuelve 429, se deja de llamarlo un rato. Sus tareas se aplazan sin
   ejecutarse, así que no gastan huecos ni reintentos (no acaban en *_failed).

6. **Carril de recuperación** (`CARRIL_RECUPERACION`): lo que reencola un
   sweep solo usa la capacidad que el tráfico en vivo deja libre. Un backlog de
   miles de tareas nunca retrasa a un lead nuevo.
7. **Marcas huérfanas** (`limpiar_pendientes_huerfanas`): si un mensaje se
   pierde o se purga a mano, su marca de pendiente no bloquea al sweep.
8. **Vigilancia** (monitoring.tasks.check_colas + /health/colas/): colas,
   circuitos, memoria de Redis y retrasos al CRM, con latido para un monitor
   externo que avise aunque se caiga el servidor entero.

Todo lo que no cabe se aplaza (se vuelve a encolar con retraso y la tarea
actual termina en el acto) en vez de esperar ocupando el worker.

Si Redis no contesta, todo esto se abre: se ejecuta y se encola como si no
existiera. Una protección que puede trabar la cola por sí misma no protege.
"""
import contextlib
import contextvars
import logging
import os
import random
import time

logger = logging.getLogger(__name__)

PREFIJO = 'resiliencia'

# ---------------------------------------------------------------------------
# Colas. Lo que no aparece aquí va a la cola por defecto `celery`
# (integraciones de marketing).
# ---------------------------------------------------------------------------
COLA_CRM = 'crm'
COLA_SISTEMA = 'sistema'

RUTAS = {
    # Envíos al CRM: lo que los setters/closers ven. Nunca detrás de marketing.
    'calendario.leads.tasks.process_crm_send': COLA_CRM,
    'calendario.leads.tasks.process_vsl_crm': COLA_CRM,
    'calendario.funnels.tasks.process_pre_schedule_crm': COLA_CRM,
    'calendario.bookings.tasks.process_schedule_crm': COLA_CRM,
    'calendario.bookings.tasks.process_onboarding_session': COLA_CRM,
    'calendario.bookings.tasks.process_academia_sesion': COLA_CRM,
    'calendario.bookings.tasks.process_academia_cancelacion': COLA_CRM,
    'calendario.bookings.tasks.process_academia_borrado': COLA_CRM,
    # La red de seguridad y el monitor: si se atascan, nadie se entera.
    'calendario.leads.tasks.sweep_incomplete_leads': COLA_SISTEMA,
    'calendario.bookings.tasks.sweep_incomplete_reservas': COLA_SISTEMA,
    'calendario.funnels.tasks.sweep_incomplete_prellamadas': COLA_SISTEMA,
    'calendario.monitoring.tasks.check_funnel_health': COLA_SISTEMA,
    'calendario.monitoring.tasks.check_colas': COLA_SISTEMA,
    'calendario.core.tasks.purge_old_supabase_backups': COLA_SISTEMA,
}

COLAS = ('celery', COLA_CRM, COLA_SISTEMA)

# ---------------------------------------------------------------------------
# Servicios externos: a qué servicio llama cada tarea y cuánto se le permite.
#   huecos:  procesos del worker que puede ocupar a la vez
#   por_min: tareas por minuto (entre todos los workers)
# ---------------------------------------------------------------------------
SERVICIO_DE_TAREA = {
    'calendario.leads.tasks.process_activecampaign': 'activecampaign',
    'calendario.leads.tasks.process_vsl_activecampaign': 'activecampaign',
    'calendario.bookings.tasks.process_schedule_activecampaign': 'activecampaign',
    'calendario.leads.tasks.process_respondio': 'respondio',
    'calendario.funnels.tasks.process_pre_schedule_respondio': 'respondio',
    'calendario.bookings.tasks.process_schedule_respondio': 'respondio',
    'calendario.leads.tasks.process_meta_capi': 'meta',
    'calendario.bookings.tasks.process_schedule_meta_capi': 'meta',
    'calendario.leads.tasks.process_tiktok_events': 'tiktok',
    'calendario.bookings.tasks.process_schedule_tiktok_events': 'tiktok',
    'calendario.leads.tasks.process_google_ads': 'google_ads',
    'calendario.bookings.tasks.process_schedule_google_ads': 'google_ads',
    'calendario.leads.tasks.process_supabase': 'supabase',
    'calendario.bookings.tasks.process_schedule_supabase': 'supabase',
    'calendario.funnels.tasks.process_pre_schedule_supabase': 'supabase',
    'calendario.leads.tasks.process_funnelchat': 'funnelchat',
    'calendario.leads.tasks.process_neverbounce': 'verificador_email',
    'calendario.leads.tasks.process_crm_send': 'crm',
    'calendario.leads.tasks.process_vsl_crm': 'crm',
    'calendario.funnels.tasks.process_pre_schedule_crm': 'crm',
    'calendario.bookings.tasks.process_schedule_crm': 'crm',
    'calendario.bookings.tasks.process_onboarding_session': 'crm',
    'calendario.bookings.tasks.process_academia_sesion': 'academia',
    'calendario.bookings.tasks.process_academia_cancelacion': 'academia',
    'calendario.bookings.tasks.process_academia_borrado': 'academia',
    'calendario.video_backup.tasks.sincronizar_bunny_r2': 'bunny',
    'calendario.core.tasks.purge_old_supabase_backups': 'supabase',
}

# Tareas que no llaman a ningún servicio externo (o que solo encolan). Toda
# tarea tiene que estar en SERVICIO_DE_TAREA o aquí: un test lo comprueba, para
# que una tarea nueva no se cuele sin tope de huecos ni ritmo.
SIN_SERVICIO = {
    'calendario.leads.tasks.sweep_incomplete_leads',
    'calendario.bookings.tasks.sweep_incomplete_reservas',
    'calendario.funnels.tasks.sweep_incomplete_prellamadas',
    'calendario.monitoring.tasks.check_funnel_health',
    'calendario.monitoring.tasks.check_colas',
}


def _por_minuto(valor, defecto):
    """'6/m', '1/s', '120/h' o un número → tareas por minuto."""
    try:
        valor = str(valor).strip()
        if '/' not in valor:
            return float(valor)
        n, unidad = valor.split('/')
        return float(n) * {'s': 60, 'm': 1, 'h': 1 / 60}[unidad.strip()[0]]
    except Exception:
        return defecto


SERVICIOS = {
    # ActiveCampaign: 5 peticiones/s por cuenta y cada tarea hace de 3 a 6.
    'activecampaign': {'huecos': 3, 'por_min': 40},
    'respondio': {'huecos': 3, 'por_min': 90},
    'meta': {'huecos': 3, 'por_min': 240},
    'tiktok': {'huecos': 2, 'por_min': 120},
    'google_ads': {'huecos': 2, 'por_min': 90},
    'supabase': {'huecos': 3, 'por_min': 600},
    'funnelchat': {'huecos': 2, 'por_min': 120},
    # Sondeo SMTP propio: Gmail corta la IP si se le pregunta seguido.
    'verificador_email': {
        'huecos': 1,
        'por_min': _por_minuto(os.environ.get('EMAIL_VERIFIER_RATE_LIMIT', '6/m'), 6),
    },
    'crm': {'huecos': 4, 'por_min': 600},
    'academia': {'huecos': 2, 'por_min': 120},
    'bunny': {'huecos': 1, 'por_min': 60},
}

# Cortacircuitos: FALLOS_PARA_ABRIR fallos de red en VENTANA_FALLOS segundos lo
# abren. Cada apertura seguida dura el doble que la anterior, hasta el máximo.
FALLOS_PARA_ABRIR = 5
VENTANA_FALLOS = 60
APERTURA_MIN = 30
APERTURA_MAX = 300

# Una tarea aplazada nunca espera más que esto: el broker Redis devuelve a la
# cola los mensajes con ETA que pasan de su visibility_timeout (1 h).
APLAZO_MAX = 300

# Cuánto dura la marca de "ya hay una copia pendiente". Si un mensaje se perdiera
# sin ejecutarse, el sweep puede volver a encolarlo pasado este tiempo.
TTL_PENDIENTE = 3 * 3600

# Un hueco se libera solo si su tarea murió sin soltarlo (worker matado). Dura
# el límite duro de la tarea (120 s por defecto; bunny, 1 h) más este margen.
MARGEN_HUECO = 30
TTL_HUECO = 120 + MARGEN_HUECO


# ---------------------------------------------------------------------------
# Redis
# ---------------------------------------------------------------------------
_cliente = None


def cliente():
    """Cliente Redis con timeouts cortos: si Redis va mal, mejor fallar abierto
    en un segundo que colgar el worker o el request."""
    global _cliente
    if _cliente is None:
        import redis
        from django.conf import settings

        _cliente = redis.Redis.from_url(
            settings.CELERY_BROKER_URL, socket_timeout=1, socket_connect_timeout=1,
        )
    return _cliente


def _k(*partes):
    return ':'.join((PREFIJO,) + tuple(str(p) for p in partes))


# ---------------------------------------------------------------------------
# 1. Una sola copia pendiente por (tarea, argumentos)
#    El valor guarda el id del mensaje publicado y cuándo: así se puede saber si
#    la marca se ha quedado huérfana (mensaje purgado o perdido) y limpiarla.
# ---------------------------------------------------------------------------
def clave_pendiente(nombre, args, kwargs):
    return _k('pendiente', nombre, repr(tuple(args or ())), repr(sorted((kwargs or {}).items())))


def _valor_pendiente(id_tarea):
    return f'{id_tarea}|{time.time():.0f}'


def reservar_pendiente(nombre, args, kwargs, id_tarea=''):
    """True si esta copia puede encolarse (no había otra pendiente)."""
    try:
        return bool(cliente().set(clave_pendiente(nombre, args, kwargs), _valor_pendiente(id_tarea),
                                  nx=True, ex=TTL_PENDIENTE))
    except Exception:
        logger.warning('[Resiliencia] Redis no responde al reservar %s; se encola igual', nombre)
        return True


def marcar_pendiente(nombre, args, kwargs, id_tarea=''):
    try:
        cliente().set(clave_pendiente(nombre, args, kwargs), _valor_pendiente(id_tarea), ex=TTL_PENDIENTE)
    except Exception:
        pass


def soltar_pendiente(nombre, args, kwargs):
    """Se llama al EMPEZAR la tarea: desde ese momento un cambio nuevo del
    objeto sí debe poder encolar otra copia (la que corre ya leyó el estado)."""
    try:
        cliente().delete(clave_pendiente(nombre, args, kwargs))
    except Exception:
        pass


def _ids_en_el_broker(r):
    """Ids de todos los mensajes vivos: en cola o entregados sin confirmar
    (ejecutándose o aplazados con ETA dentro de un worker)."""
    import json

    ids = set()
    crudos = []
    for cola in COLAS:
        crudos.extend(r.lrange(cola, 0, -1))
    crudos.extend(r.hvals('unacked'))
    for m in crudos:
        try:
            d = json.loads(m)
            if isinstance(d, list):  # unacked: [mensaje, exchange, routing_key]
                d = d[0]
            ids.add(d['headers']['id'])
        except Exception:
            continue
    return ids


def limpiar_pendientes_huerfanas(gracia=120, todas=False):
    """Borra las marcas de pendiente cuyo mensaje ya no existe en el broker (una
    purga a mano, un Redis vaciado...). Sin esto, el sweep no volvería a encolar
    esos objetos hasta que caducara la marca (3 h). Devuelve cuántas borró."""
    r = cliente()
    claves = list(r.scan_iter(match=_k('pendiente', '*'), count=1000))
    if not claves:
        return 0
    if todas:
        return r.delete(*claves)
    # Con una cola desbordada no se recorre el broker entero cada minuto; con la
    # deduplicación activa no debería pasar, y si pasa ya avisa check_colas.
    if sum(r.llen(c) for c in COLAS) + r.hlen('unacked') > 50000:
        return 0
    vivos = _ids_en_el_broker(r)
    ahora = time.time()
    huerfanas = []
    for clave, valor in zip(claves, r.mget(claves)):
        if valor is None:
            continue
        id_tarea, _, cuando = valor.decode().partition('|')
        try:
            antiguedad = ahora - float(cuando)
        except ValueError:
            antiguedad = gracia + 1
        if antiguedad > gracia and id_tarea not in vivos:
            huerfanas.append(clave)
    if huerfanas:
        r.delete(*huerfanas)
        logger.warning('[Resiliencia] %d marcas de pendiente huérfanas borradas', len(huerfanas))
    return len(huerfanas)


# ---------------------------------------------------------------------------
# 2. Huecos por servicio (semáforo con caducidad)
# ---------------------------------------------------------------------------
_LUA_HUECO = """
redis.call('ZREMRANGEBYSCORE', KEYS[1], '-inf', ARGV[1])
if redis.call('ZCARD', KEYS[1]) < tonumber(ARGV[2]) then
  redis.call('ZADD', KEYS[1], ARGV[3], ARGV[4])
  if redis.call('TTL', KEYS[1]) < tonumber(ARGV[5]) then redis.call('EXPIRE', KEYS[1], ARGV[5]) end
  return 1
end
return 0
"""


def ocupar_hueco(servicio, id_tarea, ttl=TTL_HUECO):
    """Cada hueco se guarda con su fecha de CADUCIDAD (ahora + ttl), así una
    tarea de 1 h no pierde el suyo a los 2 min."""
    conf = SERVICIOS.get(servicio)
    if not conf:
        return True
    ahora = time.time()
    try:
        return bool(cliente().eval(
            _LUA_HUECO, 1, _k('huecos', servicio),
            ahora, conf['huecos'], ahora + ttl, id_tarea, int(ttl) + 60,
        ))
    except Exception:
        return True


def soltar_hueco(servicio, id_tarea):
    try:
        cliente().zrem(_k('huecos', servicio), id_tarea)
    except Exception:
        pass


# ---------------------------------------------------------------------------
# 3. Ritmo por servicio: cada tarea reserva su turno en la fila del servicio
#    (GCRA: un turno cada 60/por_min segundos, con una ráfaga inicial) y se
#    aplaza exactamente hasta él. Así vuelven de una en una, a su ritmo, en vez
#    de aplazarse todas unos segundos y volver en tropel.
# ---------------------------------------------------------------------------
_LUA_TURNO = """
local ahora = tonumber(ARGV[1])
local intervalo = tonumber(ARGV[2])
local rafaga = tonumber(ARGV[3])
local tat = tonumber(redis.call('GET', KEYS[1]) or ahora)
if tat < ahora then tat = ahora end
local espera = tat - ahora - (rafaga - 1) * intervalo
if espera < 0 then espera = 0 end
local max_espera = tonumber(ARGV[4])
if max_espera >= 0 and espera > max_espera then return tostring(-espera) end
redis.call('SET', KEYS[1], tostring(tat + intervalo), 'EX', math.ceil(tat + intervalo - ahora) + 60)
return tostring(espera)
"""


def tomar_turno(servicio, max_espera=None):
    """Reserva el siguiente turno del servicio. 0 si es ya; si no, los segundos
    que faltan para él. Con `max_espera`, si el turno queda más lejos NO se
    reserva y devuelve la espera en negativo."""
    conf = SERVICIOS.get(servicio)
    if not conf or not conf.get('por_min'):
        return 0
    intervalo = 60.0 / conf['por_min']
    rafaga = max(1, int(conf['por_min'] / 60 * 5))  # hasta 5 s de ráfaga
    try:
        return float(cliente().eval(
            _LUA_TURNO, 1, _k('turno', servicio), time.time(), intervalo, rafaga,
            -1 if max_espera is None else max_espera,
        ))
    except Exception:
        return 0


def _turno_reservado(id_tarea):
    try:
        valor = cliente().get(_k('reservado', id_tarea))
        return float(valor) if valor is not None else None
    except Exception:
        return None


def _reservar(id_tarea, cuando):
    try:
        cliente().set(_k('reservado', id_tarea), repr(cuando), ex=int(cuando - time.time()) + 900)
    except Exception:
        pass


def _olvidar_turno(id_tarea):
    try:
        cliente().delete(_k('reservado', id_tarea))
    except Exception:
        pass


# ---------------------------------------------------------------------------
# 4. Cortacircuitos
# ---------------------------------------------------------------------------
def circuito_abierto(servicio):
    """Segundos que le quedan abierto al circuito (0 = cerrado)."""
    try:
        ttl = cliente().pttl(_k('circuito', servicio))
        return ttl / 1000.0 if ttl and ttl > 0 else 0
    except Exception:
        return 0


def abrir_circuito(servicio, segundos=None, motivo=''):
    try:
        r = cliente()
        if segundos is None:
            nivel = r.incr(_k('circuito_nivel', servicio))
            r.expire(_k('circuito_nivel', servicio), 3600)
            segundos = min(APERTURA_MAX, APERTURA_MIN * 2 ** (nivel - 1))
        segundos = max(1, min(APERTURA_MAX, int(segundos)))
        r.set(_k('circuito', servicio), motivo or 'abierto', ex=segundos)
        r.delete(_k('fallos', servicio))
        logger.warning('[Resiliencia] Circuito de %s ABIERTO %ss: %s', servicio, segundos, motivo)
    except Exception:
        pass


def _codigo_http(exc):
    return getattr(getattr(exc, 'response', None), 'status_code', None)


def es_fallo_del_servicio(exc):
    """Solo cuentan los fallos que dicen algo del servicio (red, timeouts, 5xx,
    429), no los nuestros (objeto borrado, datos inválidos)."""
    import requests
    from celery.exceptions import SoftTimeLimitExceeded, TimeLimitExceeded

    if isinstance(exc, (SoftTimeLimitExceeded, TimeLimitExceeded)):
        return True
    codigo = _codigo_http(exc)
    if codigo is not None:
        return codigo == 429 or codigo >= 500
    return isinstance(exc, requests.RequestException)


def registrar_fallo(servicio, exc):
    if not servicio or not es_fallo_del_servicio(exc):
        return
    if _codigo_http(exc) == 429:
        espera = None
        try:
            espera = float(exc.response.headers.get('Retry-After'))
        except Exception:
            pass
        abrir_circuito(servicio, espera or 60, 'HTTP 429')
        return
    try:
        r = cliente()
        clave = _k('fallos', servicio)
        n = r.incr(clave)
        if n == 1:
            r.expire(clave, VENTANA_FALLOS)
        if n >= FALLOS_PARA_ABRIR:
            abrir_circuito(servicio, motivo=f'{n} fallos en {VENTANA_FALLOS}s ({type(exc).__name__})')
    except Exception:
        pass


def registrar_exito(servicio):
    if not servicio:
        return
    try:
        cliente().delete(_k('fallos', servicio), _k('circuito_nivel', servicio))
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Decisión antes de ejecutar
# ---------------------------------------------------------------------------
# ---------------------------------------------------------------------------
# Carriles: lo que reencola un sweep (recuperación) solo usa la capacidad que el
# tráfico en vivo deja libre. Si la fila del servicio ya va más de
# ESPERA_MAX_RECUPERACION por delante, cede el paso y vuelve más tarde sin
# reservar turno: un backlog de miles de tareas nunca retrasa a un lead nuevo
# más que eso.
# ---------------------------------------------------------------------------
CARRIL_RECUPERACION = 'recuperacion'
ESPERA_MAX_RECUPERACION = 20
CEDER_PASO = (120, 300)

_carril = contextvars.ContextVar('resiliencia_carril', default=None)


def carril_actual():
    return _carril.get()


@contextlib.contextmanager
def en_carril(carril):
    token = _carril.set(carril)
    try:
        yield
    finally:
        _carril.reset(token)


SWEEPS = {
    'calendario.leads.tasks.sweep_incomplete_leads',
    'calendario.bookings.tasks.sweep_incomplete_reservas',
    'calendario.funnels.tasks.sweep_incomplete_prellamadas',
}


def motivo_para_aplazar(servicio, id_tarea, carril=None, ttl_hueco=TTL_HUECO):
    """(segundos, motivo) si la tarea no debe ejecutarse ahora; None si puede.
    Si devuelve None, la tarea tiene un hueco ocupado que hay que soltar.

    Una tarea aplazada conserva su id, así que su turno reservado la espera.
    """
    if not servicio:
        return None
    abierto = circuito_abierto(servicio)
    if abierto:
        # Al cerrarse, pedirá turno de nuevo: si conservara uno ya vencido, todas
        # las aplazadas saldrían a la vez y se saltarían el ritmo.
        _olvidar_turno(id_tarea)
        return abierto, 'circuito abierto'

    ahora = time.time()
    reservado = _turno_reservado(id_tarea)
    if reservado is None:
        if carril == CARRIL_RECUPERACION:
            espera = tomar_turno(servicio, max_espera=ESPERA_MAX_RECUPERACION)
            if espera < 0:
                return random.uniform(*CEDER_PASO), 'cede el paso al tráfico en vivo'
        else:
            espera = tomar_turno(servicio)
        if espera > 0:
            _reservar(id_tarea, ahora + espera)
            return espera, 'ritmo'
    elif reservado - ahora > 0.5:
        return reservado - ahora, 'ritmo'

    if not ocupar_hueco(servicio, id_tarea, ttl_hueco):
        # Ya ha pasado su turno: lo conserva y reintenta en unos segundos.
        _reservar(id_tarea, ahora + 5)
        return 5, 'sin hueco'
    _olvidar_turno(id_tarea)
    return None


def segundos_de_aplazo(segundos, motivo=''):
    """Lo que espera un turno reservado se respeta al segundo (el turno ya
    reparte); lo demás lleva jitter para no volver todo junto."""
    if motivo == 'ritmo' or motivo.startswith('cede'):
        return min(APLAZO_MAX, max(0.5, segundos))
    return min(APLAZO_MAX, max(1.0, segundos) * random.uniform(1.0, 1.5))


# ---------------------------------------------------------------------------
# Estado (para el monitor)
# ---------------------------------------------------------------------------
def longitudes_de_colas():
    r = cliente()
    return {c: r.llen(c) for c in COLAS}


def circuitos_abiertos():
    return {s: circuito_abierto(s) for s in SERVICIOS if circuito_abierto(s)}


def memoria_redis_mb():
    """(MB usados, maxmemory en MB o 0 si no tiene límite)."""
    info = cliente().info('memory')
    return info['used_memory'] / 1048576, (info.get('maxmemory') or 0) / 1048576


def registrar_latido(problemas):
    """Lo lee /health/colas/: cuándo corrió check_colas y qué vio."""
    import json
    try:
        cliente().set(_k('latido'), json.dumps({
            'ts': time.time(), 'problemas': [texto for _, texto in problemas],
        }), ex=3600)
    except Exception:
        pass


def leer_latido():
    import json
    try:
        valor = cliente().get(_k('latido'))
        return json.loads(valor) if valor else None
    except Exception:
        return None
