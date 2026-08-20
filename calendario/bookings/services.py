import logging
import math
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from django.core.cache import cache
from django.db import connections, transaction
from django.db.models import Count, Q, Value
from django.db.models.functions import Replace
from django.utils import timezone

from calendario.availability.models import BloqueHorarioSemanal, BloqueHorarioFecha
from calendario.event_types.models import EventType, EventTypeXHost
from calendario.google_calendar.services import (
    cancelar_evento_google, construir_titulo_evento, crear_evento_google,
    eliminar_evento_google, hay_conflicto_calendario, obtener_busy_intervalos,
    obtener_busy_intervalos_local, titulo_libera_horario,
)
from .exceptions import ReservaDuplicadaError, SlotNoDisponibleError
from .models import Reserva

logger = logging.getLogger(__name__)


MAX_VENTANA_DIAS = 60
UTC = ZoneInfo('UTC')

# Tope de reservas activas que admite un mismo horario cuando las reglas free/busy
# lo dejan abierto. Configurar palabras en el tipo de evento ya significa "aquí se
# puede reservar encima"; el tope no se expone en el panel porque siempre es 2.
MAX_RESERVAS_POR_SLOT = 2


def _intervals_overlap(a_inicio, a_fin, b_inicio, b_fin):
    return a_inicio < b_fin and b_inicio < a_fin


def _obtener_hosts_pool(event_type):
    """
    Hosts activos del pool del event_type que participan en el reparto, ordenados
    por pivot.id ASC.

    Los organizadores con prioridad 0 quedan fuera aquí, que es el único punto por
    el que pasan tanto los slots ofrecidos como la asignación de la reserva: así un
    excluido ni recibe reservas ni aporta sus horas al calendario público (ofrecer
    una hora que solo él cubre daría un slot que después no se puede reservar).

    Si el pool no tiene ninguna fila (evento no-equipo), usa el host dueño del
    evento como fallback. Un pool con filas pero todas en prioridad 0 NO cae al
    fallback: es una exclusión deliberada, y quedarse sin hosts es el resultado
    querido, no un evento personal.
    """
    pivots = list(EventTypeXHost.objects
                  .filter(event_type=event_type, host__is_active=True)
                  .select_related('host')
                  .order_by('id'))
    if pivots:
        return [p.host for p in pivots
                if p.prioridad > EventTypeXHost.PRIORIDAD_EXCLUIDO]
    if event_type.host.is_active:
        return [event_type.host]
    return []


def _obtener_busy_intervalos_con_fallback(host, desde_utc, hasta_utc, palabras_ignorar=None):
    """
    Devuelve intervalos busy del host intentando primero la copia local.
    Fallback a freeBusy en vivo si el host no tiene sync activo (regla #2).

    `palabras_ignorar` (reglas free/busy del tipo de evento) solo se aplica en
    la copia local, que es la que guarda el título del evento. El fallback
    freeBusy en vivo no devuelve títulos, así que no puede filtrar: para hosts
    sin sync activo la regla no aplica (degradación documentada).
    """
    from calendario.google_calendar.models import GoogleCalendarSyncEstado
    try:
        sync_estado = GoogleCalendarSyncEstado.objects.get(host=host)
        if sync_estado.estado == GoogleCalendarSyncEstado.ACTIVO:
            return obtener_busy_intervalos_local(host, desde_utc, hasta_utc, palabras_ignorar)
    except GoogleCalendarSyncEstado.DoesNotExist:
        pass
    return obtener_busy_intervalos(host.email, desde_utc, hasta_utc)


def _abiertas_para_event_type(host, reservas, palabras_ignorar, desde_utc, hasta_utc):
    """
    Devuelve `esta_abierta(reserva)`: True si esa reserva NO debe bloquear el
    hueco para el tipo de evento que se está consultando.

    Manda el título real del evento en Google Calendar comparado contra
    `palabras_ignorar` (las reglas del tipo consultado), igual que ya se hace con
    los eventos ajenos en `obtener_busy_intervalos_local`. Así una reserva nuestra
    y una reunión de Calendly con el mismo título se tratan igual.

    Respaldo: si la reserva no tiene su evento en la copia local (aún sin
    sincronizar, o el host lo borró en Google) no hay título que comparar y se
    usa `permite_overbooking`, el flag que dejó el sync al crearla.
    """
    if not reservas:
        return lambda r: False

    from calendario.google_calendar.models import GoogleCalendarEvento

    gids = [r.google_event_id for r in reservas if r.google_event_id]
    titulos = {}
    if gids:
        titulos = dict(
            GoogleCalendarEvento.objects
            .filter(host=host, google_event_id__in=gids)
            .exclude(estado='cancelled')
            .values_list('google_event_id', 'titulo')
        )

    def esta_abierta(reserva):
        if reserva.google_event_id in titulos:
            return titulo_libera_horario(titulos[reserva.google_event_id], palabras_ignorar)
        return reserva.permite_overbooking

    return esta_abierta


def _calcular_slots_para_host(event_type, host, fecha_desde, fecha_hasta, busy_override=None):
    """
    Devuelve lista de inicio_utc aware-UTC disponibles para un host concreto.
    fecha_desde / fecha_hasta: date naive (interpretadas en TZ del host).
    Clamp servidor: fecha_hasta = min(fecha_hasta, fecha_desde + MAX_VENTANA_DIAS).
    busy_override: si se pasa, usa esta lista de (inicio, fin) en vez de la caché local/API.
    """
    tz_host = ZoneInfo(host.timezone)
    duracion = event_type.duracion_minutos
    incremento = event_type.incremento_inicio_minutos
    buffer_antes = event_type.buffer_antes_minutos
    buffer_despues = event_type.buffer_despues_minutos
    aviso = event_type.aviso_minimo_minutos

    fecha_hasta = min(fecha_hasta, fecha_desde + timedelta(days=MAX_VENTANA_DIAS))
    if fecha_hasta < fecha_desde:
        return []

    ahora_utc = timezone.now()
    minimo = ahora_utc + timedelta(minutes=aviso)

    # La ventana reservable la decide `ventana_reservas`, el mismo sitio que usan
    # las vistas públicas para pintar el calendario: así el día que se puede
    # pinchar es exactamente el día que tiene horas. Los dos modos son
    # excluyentes —con rango de fechas fijo el rolling `aviso_maximo_dias` no
    # pinta nada— y el corte es siempre por DÍA COMPLETO, no al minuto: con 3
    # días rodantes, el día hoy+3 aparece entero desde sus 00:00, en vez de irse
    # destapando hora a hora conforme avanza el reloj.
    hoy_local = ahora_utc.astimezone(tz_host).date()
    ventana_desde, ventana_hasta = event_type.ventana_reservas(hoy_local)
    fecha_desde = max(fecha_desde, ventana_desde)
    fecha_hasta = min(fecha_hasta, ventana_hasta)
    if fecha_hasta < fecha_desde:
        return []

    bloques_por_dia = defaultdict(list)
    for b in BloqueHorarioSemanal.objects.filter(host=host):
        bloques_por_dia[b.dia_semana].append(b)

    # Overrides por fecha: si una fecha tiene bloques específicos, estos
    # sobrescriben el horario semanal de ese día (igual que Calendly).
    overrides_por_fecha = defaultdict(list)
    for b in BloqueHorarioFecha.objects.filter(
        host=host, fecha__range=(fecha_desde, fecha_hasta)
    ):
        overrides_por_fecha[b.fecha].append(b)

    # Si este EventTypeXHost tiene disponibilidad específica configurada,
    # reemplaza el horario semanal global y agrega sus overrides de fecha.
    etxh = EventTypeXHost.objects.filter(event_type=event_type, host=host).first()
    if etxh:
        franjas_etxh = list(etxh.disponibilidad.all())
        if franjas_etxh:
            bloques_por_dia = defaultdict(list)
            for f in franjas_etxh:
                bloques_por_dia[f.dia_semana].append(f)
        for f in etxh.disponibilidad_fechas.filter(fecha__range=(fecha_desde, fecha_hasta)):
            if f.hora_inicio and f.hora_fin:
                overrides_por_fecha[f.fecha] = [f]
            else:
                overrides_por_fecha[f.fecha] = []  # día bloqueado

    desde_utc = datetime.combine(fecha_desde, datetime.min.time()).replace(tzinfo=tz_host).astimezone(UTC)
    hasta_utc = datetime.combine(fecha_hasta + timedelta(days=1), datetime.min.time()).replace(tzinfo=tz_host).astimezone(UTC)

    palabras_ignorar = event_type.gcal_palabras_ignorar_lista

    reservas = list(
        Reserva.objects.filter(
            host=host, estado=Reserva.Estado.CONFIRMADA,
            inicio_utc__lt=hasta_utc + timedelta(hours=24),
            fin_utc__gt=desde_utc - timedelta(hours=24),
        ).select_related('event_type').order_by('inicio_utc')
    )

    # Reglas free/busy (estilo Calendly): una reserva "abierta" no bloquea el
    # slot, así entran varias reservas encima.
    #
    # Quién decide si está abierta son las palabras de ESTE `event_type` —el que
    # el invitado tiene delante— contra el título que el evento tiene en Google
    # Calendar. NO las palabras del tipo con el que se creó la reserva. Es como
    # funciona Calendly: las reglas viven en el tipo que se está reservando y se
    # evalúan contra el título de lo que ya hay en la agenda, venga de donde
    # venga (un evento personal, una reunión de Calendly o una reserva nuestra).
    #
    # Antes se miraba `permite_overbooking`, que el sync calcula con las palabras
    # del tipo DE LA RESERVA. Eso hacía que una reserva creada desde un tipo sin
    # reglas bloqueara para todos los demás tipos, aunque su título matcheara las
    # palabras de ellos: los eventos de Calendly liberaban el hueco y los nuestros
    # no. El flag se sigue usando como respaldo para las reservas cuyo evento aún
    # no está en la copia local (sin título no hay nada que comparar).
    #
    # El tope MAX_RESERVAS_POR_SLOT cierra el horario solo: mientras las abiertas
    # que arrancan a esa hora no lleguen al tope no bloquean; al alcanzarlo vuelven
    # a bloquear como una reserva normal. Se agrupan por hora de inicio, igual que
    # la restricción de unicidad (host + inicio_utc), y solo cuentan las confirmadas
    # — el queryset de arriba ya excluye las canceladas, así que cancelar una deja
    # hueco para otra sin tocar Google Calendar.
    #
    # Ojo: al llegar al tope NO se puede apagar `permite_overbooking`, porque dos
    # reservas exclusivas en el mismo slot violarían esa restricción. Por eso el
    # tope se aplica aquí, en el cálculo, y no en la BD.
    esta_abierta = _abiertas_para_event_type(
        host, reservas, palabras_ignorar,
        desde_utc - timedelta(hours=24), hasta_utc + timedelta(hours=24),
    )
    abiertas_por_inicio = Counter(
        r.inicio_utc for r in reservas if esta_abierta(r)
    )
    reservas = [
        r for r in reservas
        if not esta_abierta(r)
        or abiertas_por_inicio[r.inicio_utc] >= MAX_RESERVAS_POR_SLOT
    ]

    # Los eventos externos de GCal bloquean solo su tiempo real, sin buffer.
    # El buffer solo aplica alrededor de reservas confirmadas (igual que Calendly).
    if busy_override is not None:
        busy_intervalos = list(busy_override)
    else:
        busy_intervalos = list(_obtener_busy_intervalos_con_fallback(
            host, desde_utc, hasta_utc, palabras_ignorar,
        ))

    slots = []
    step = timedelta(minutes=incremento)
    fecha_actual = fecha_desde
    while fecha_actual <= fecha_hasta:
        if fecha_actual in overrides_por_fecha:
            bloques_del_dia = overrides_por_fecha[fecha_actual]
        else:
            bloques_del_dia = bloques_por_dia[fecha_actual.weekday()]
        for bloque in bloques_del_dia:
            block_start = datetime.combine(fecha_actual, bloque.hora_inicio).replace(tzinfo=tz_host)
            cursor_local = block_start
            fin_local = datetime.combine(fecha_actual, bloque.hora_fin).replace(tzinfo=tz_host)
            while cursor_local + timedelta(minutes=duracion) <= fin_local:
                slot_utc = cursor_local.astimezone(UTC)
                slot_fin_utc = slot_utc + timedelta(minutes=duracion)
                # Filtro DST: si el offset cambia dentro del slot, descartar.
                if slot_utc.utcoffset() != slot_fin_utc.utcoffset():
                    cursor_local += step
                    continue
                if slot_utc < minimo:
                    cursor_local += step
                    continue
                new_blocked_inicio = slot_utc - timedelta(minutes=buffer_antes)
                new_blocked_fin = slot_fin_utc + timedelta(minutes=buffer_despues)
                conflict = False
                next_cursor = cursor_local + step
                for r in reservas:
                    r_blocked_inicio = r.inicio_utc - timedelta(minutes=r.event_type.buffer_antes_minutos)
                    r_blocked_fin = r.fin_utc + timedelta(minutes=r.event_type.buffer_despues_minutos)
                    if r_blocked_inicio >= new_blocked_fin:
                        break  # reservas ordenadas; las siguientes son aún más tardías.
                    if _intervals_overlap(new_blocked_inicio, new_blocked_fin, r_blocked_inicio, r_blocked_fin):
                        conflict = True
                        jump = r_blocked_fin.astimezone(tz_host) + timedelta(minutes=buffer_antes)
                        if jump > next_cursor:
                            next_cursor = jump
                        break
                if not conflict:
                    for busy_inicio, busy_fin in busy_intervalos:
                        if busy_inicio >= new_blocked_fin:
                            break  # intervalos ordenados; los siguientes son aún más tardíos.
                        if _intervals_overlap(new_blocked_inicio, new_blocked_fin, busy_inicio, busy_fin):
                            conflict = True
                            jump = busy_fin.astimezone(tz_host) + timedelta(minutes=buffer_antes)
                            if jump > next_cursor:
                                next_cursor = jump
                            break
                if not conflict:
                    slots.append(slot_utc)
                # Grid estricto: si saltamos por un conflicto, re-alineamos al
                # siguiente punto de la cuadrícula (block_start + n * step).
                elapsed_secs = (next_cursor - block_start).total_seconds()
                step_secs = incremento * 60
                n = math.ceil(elapsed_secs / step_secs)
                snapped = block_start + timedelta(seconds=int(n * step_secs))
                cursor_local = max(next_cursor, snapped)
        fecha_actual += timedelta(days=1)

    return slots


def _slots_host_threadsafe(event_type, host, fecha_desde, fecha_hasta):
    try:
        return _calcular_slots_para_host(event_type, host, fecha_desde, fecha_hasta)
    finally:
        # Cada hilo abre su propia conexión a la BD; la cerramos al terminar
        # para no agotar el pool del backend.
        connections.close_all()


def calcular_slots(event_type, fecha_desde, fecha_hasta):
    """
    Devuelve la unión de slots disponibles entre todos los hosts del pool del event_type.
    Las llamadas freeBusy son IO-bound; las paralelizamos por host.
    """
    hosts = _obtener_hosts_pool(event_type)
    if not hosts:
        return []
    slots_set = set()
    if len(hosts) == 1:
        slots_set.update(
            _calcular_slots_para_host(event_type, hosts[0], fecha_desde, fecha_hasta)
        )
    else:
        with ThreadPoolExecutor(max_workers=len(hosts)) as pool:
            futuros = [
                pool.submit(_slots_host_threadsafe, event_type, h, fecha_desde, fecha_hasta)
                for h in hosts
            ]
            for f in futuros:
                slots_set.update(f.result())
    return sorted(slots_set)


_SLOTS_TTL = 45


def invalidar_slots(event_type_id):
    key_gen = f'slots_gen:{event_type_id}'
    try:
        cache.incr(key_gen)
    except ValueError:
        cache.set(key_gen, 1, timeout=None)


def invalidar_slots_por_host(host_id):
    # El host bloquea slots tanto en los event_types donde es dueño directo
    # (eventos personales, sin fila en EventTypeXHost) como en aquellos donde
    # participa en el pool de round-robin. Hay que invalidar ambos: si solo
    # miráramos EventTypeXHost, los eventos personales nunca refrescarían su
    # caché tras un cambio en Google Calendar.
    et_ids = set(
        EventTypeXHost.objects
        .filter(host_id=host_id)
        .values_list('event_type_id', flat=True)
    )
    et_ids.update(
        EventType.objects
        .filter(host_id=host_id)
        .values_list('id', flat=True)
    )
    for et_id in et_ids:
        invalidar_slots(et_id)


def calcular_slots_cacheado(event_type, fecha_desde, fecha_hasta):
    key_gen = f'slots_gen:{event_type.pk}'
    gen = cache.get(key_gen, default=0)
    key = f'slots:{event_type.pk}:{gen}:{fecha_desde.isoformat()}:{fecha_hasta.isoformat()}'
    cached = cache.get(key)
    if cached is not None:
        return [datetime.fromisoformat(s) for s in cached]
    slots = calcular_slots(event_type, fecha_desde, fecha_hasta)
    cache.set(key, [s.isoformat() for s in slots], timeout=_SLOTS_TTL)
    return slots


def _candidatos_para_slot(event_type, inicio_utc):
    """
    Hosts del pool que tienen inicio_utc disponible (dentro de su disponibilidad
    semanal y sin colisión con sus reservas, respetando buffers).
    Orden: pivot.id ASC.
    """
    hosts = _obtener_hosts_pool(event_type)
    if not hosts:
        return []
    candidatos = []
    for host in hosts:
        fecha_local = inicio_utc.astimezone(ZoneInfo(host.timezone)).date()
        slots_host = _calcular_slots_para_host(event_type, host, fecha_local, fecha_local)
        if inicio_utc in slots_host:
            candidatos.append(host)
    return candidatos


def _seleccionar_host_round_robin(event_type, candidatos):
    """
    Selecciona el host al que se le asigna la reserva, por este orden:

      1. Mayor `prioridad` en el pool (3 manda sobre 1).
      2. Menor número de reservas confirmadas para este event_type (reparto de carga).
      3. Menor pivot.id (orden de añadido al pool).

    Con todos los organizadores en la prioridad por defecto el primer criterio es
    constante y la elección queda idéntica al reparto histórico por carga.

    Los excluidos (prioridad 0) no llegan aquí: `_obtener_hosts_pool` ya los quitó
    aguas arriba, así que ningún candidato puede tener prioridad 0.
    Pre-condición: len(candidatos) >= 1.
    """
    if len(candidatos) == 1:
        return candidatos[0]
    host_ids = [h.id for h in candidatos]
    counts_qs = (Reserva.objects
                 .filter(event_type=event_type,
                         estado=Reserva.Estado.CONFIRMADA,
                         host_id__in=host_ids)
                 .values('host_id')
                 .annotate(c=Count('id')))
    counts = {row['host_id']: row['c'] for row in counts_qs}
    # {host_id: (pivot.id, prioridad)}. Un host sin fila en el pool (evento
    # personal que llegase aquí) cae al valor por defecto y no se cuela delante.
    pivots = {
        host_id: (pivot_id, prioridad)
        for host_id, pivot_id, prioridad in (
            EventTypeXHost.objects
            .filter(event_type=event_type, host_id__in=host_ids)
            .values_list('host_id', 'id', 'prioridad')
        )
    }
    defecto = (0, EventTypeXHost.PRIORIDAD_DEFECTO)

    def _clave(h):
        pivot_id, prioridad = pivots.get(h.id, defecto)
        return (-prioridad, counts.get(h.id, 0), pivot_id)

    return min(candidatos, key=_clave)


# Campos de tracking que la Reserva guarda como snapshot (del tracking de la
# Prellamada). Mismos nombres que el payload del CRM schedule / Supabase.
RESERVA_TRACKING_FIELDS = (
    'journey_id', 'event_id', 'setter', 'utm_source', 'utm_campaign', 'utm_medium',
    'utm_term', 'utm_content', 'utm_idcampaign', 'utm_adsetid', 'utm_adid',
    'utm_form_variant', 'url',
)


def _tracking_kwargs(tracking):
    """Extrae los campos de tracking de un dict (p.ej. Prellamada.tracking) a los
    kwargs del modelo Reserva. Devuelve '' para los que falten."""
    tr = tracking if isinstance(tracking, dict) else {}
    return {f: (tr.get(f) or '') for f in RESERVA_TRACKING_FIELDS}


# Separadores que la gente (y los forms de las landings) mete dentro del número:
# "+34 679 123-456", "(+57) 300 123 4567"… Se quitan antes de comparar, tanto del
# teléfono que llega como del que hay guardado (vía REPLACE en SQL).
_TEL_SEPARADORES = (' ', '-', '(', ')', '.', '\u00a0')

# Cuántos dígitos finales tienen que coincidir para dar dos teléfonos por iguales.
# Comparar el sufijo y no la cadena entera hace que "+34679123456", "0034679123456"
# y "679123456" sean el mismo número. Con 9 dígitos el sufijo ya es prácticamente
# único dentro de un país y no colisiona entre países (un móvil español y uno
# mexicano no comparten los últimos 9).
TEL_DIGITOS_COMPARAR = 9


def _sufijo_telefono(valor):
    """Sufijo comparable de un teléfono: sus últimos dígitos, sin prefijo ni
    separadores. Devuelve '' si no hay dígitos suficientes para comparar sin
    riesgo (extensiones, basura en el campo)."""
    digitos = ''.join(c for c in (valor or '') if c.isdigit())
    digitos = digitos.lstrip('0')  # 0034…/0424… → el 0 de marcación no cuenta
    if len(digitos) < 7:
        return ''
    return digitos[-TEL_DIGITOS_COMPARAR:]


def _annotate_telefono_normalizado(qs):
    """Anota el teléfono guardado sin separadores, para poder comparar sufijos
    en SQL (y no traerse todas las reservas futuras a memoria)."""
    expr = 'telefono_invitado'
    for sep in _TEL_SEPARADORES:
        expr = Replace(expr, Value(sep), Value(''))
    return qs.annotate(telefono_norm=expr)


def buscar_reserva_duplicada(event_type, email_invitado, telefono_invitado=''):
    """Reserva futura confirmada de este event_type hecha por el mismo invitado,
    entendiendo "el mismo" como mismo email O mismo teléfono. Devuelve None si no
    hay ninguna. La más próxima en el tiempo es la que se devuelve.
    """
    email_norm = (email_invitado or '').strip().lower()
    tel_sufijo = _sufijo_telefono(telefono_invitado)
    if not email_norm and not tel_sufijo:
        return None

    coincide = Q()
    if email_norm:
        coincide |= Q(email_invitado__iexact=email_norm)
    if tel_sufijo:
        coincide |= Q(telefono_norm__endswith=tel_sufijo)

    qs = Reserva.objects.select_related('host', 'event_type').filter(
        event_type=event_type,
        estado=Reserva.Estado.CONFIRMADA,
        fin_utc__gt=timezone.now(),
    )
    return _annotate_telefono_normalizado(qs).filter(coincide).order_by('inicio_utc').first()


def mismo_invitado(reserva, email_invitado, telefono_invitado=''):
    """¿La reserva es de este invitado? Mismo criterio que buscar_reserva_duplicada
    (email O teléfono), para validar el reemplazo de un duplicado detectado por
    teléfono aunque el email que escribió ahora sea otro."""
    email_norm = (email_invitado or '').strip().lower()
    if email_norm and (reserva.email_invitado or '').strip().lower() == email_norm:
        return True
    tel_sufijo = _sufijo_telefono(telefono_invitado)
    return bool(tel_sufijo) and _sufijo_telefono(reserva.telefono_invitado) == tel_sufijo


def crear_reserva(event_type, inicio_utc, nombre_invitado, email_invitado,
                  telefono_invitado='', notas='', timezone_invitado='', tracking=None):
    """
    Crea una reserva eligiendo automáticamente un host del pool (round-robin
    least-loaded). Lock sobre la fila EventType para serializar concurrentes
    del mismo event_type. Lanza SlotNoDisponibleError si no hay candidato.

    `tracking` (dict, opcional): journey_id/event_id/UTMs a guardar como snapshot
    en la reserva (lo pasa el flujo del funnel desde Prellamada.tracking).
    """
    with transaction.atomic():
        et = EventType.objects.select_for_update().get(pk=event_type.pk)
        if not et.activo:
            raise SlotNoDisponibleError("El evento no está disponible.")

        if et.unico_por_invitado:
            existente = buscar_reserva_duplicada(et, email_invitado, telefono_invitado)
            if existente:
                raise ReservaDuplicadaError(existente)

        candidatos = _candidatos_para_slot(et, inicio_utc)
        if not candidatos:
            raise SlotNoDisponibleError("Ese slot ya no está disponible.")

        host_elegido = _seleccionar_host_round_robin(et, candidatos)
        fin_utc = inicio_utc + timedelta(minutes=et.duracion_minutos)

        # Reglas free/busy (estilo Calendly): la reserva queda "abierta" (se puede
        # reservar encima) solo si el título que va a llevar su evento en Google
        # Calendar matchea alguna de las palabras configuradas. La app no toca el
        # título: para que un tipo de evento se pise a sí mismo, la palabra va en
        # el nombre del tipo de evento. El host cierra un horario concreto
        # quitándole la palabra a ese evento en Google (lo reconcilia el sync).
        nombre_invitado = nombre_invitado.strip()
        abierta = titulo_libera_horario(
            construir_titulo_evento(et, nombre_invitado, host_elegido),
            et.gcal_palabras_ignorar_lista,
        )

        # Si el host ya tiene algo a esa hora, la nueva reserva solo entra encima
        # cuando las reglas de ESTE tipo de evento liberan lo que hay — el mismo
        # criterio con el que se ofreció el slot. Si no lo liberan, es que el hueco
        # se ocupó entre medias: se rechaza aquí en vez de dejar que reviente la
        # restricción de unicidad. Y cuando sí conviven, es la reserva nueva la
        # que renuncia a la exclusividad, porque esa restricción solo admite una
        # reserva con `permite_overbooking=False` por (host, inicio_utc).
        existentes = list(
            Reserva.objects.filter(
                host=host_elegido,
                inicio_utc=inicio_utc,
                estado=Reserva.Estado.CONFIRMADA,
            ).select_related('event_type')
        )
        if existentes:
            libera = _abiertas_para_event_type(
                host_elegido, existentes, et.gcal_palabras_ignorar_lista,
                inicio_utc, fin_utc,
            )
            if (len(existentes) >= MAX_RESERVAS_POR_SLOT
                    or not all(libera(r) for r in existentes)):
                raise SlotNoDisponibleError("Ese slot ya no está disponible.")
            abierta = True

        if hay_conflicto_calendario(
            host_elegido.email, inicio_utc, fin_utc, et.gcal_palabras_ignorar_lista,
        ):
            raise SlotNoDisponibleError("Ese slot ya no está disponible.")

        reserva = Reserva.objects.create(
            event_type=et,
            host=host_elegido,
            inicio_utc=inicio_utc,
            fin_utc=fin_utc,
            nombre_invitado=nombre_invitado,
            email_invitado=email_invitado,
            telefono_invitado=telefono_invitado.strip(),
            notas=notas.strip(),
            timezone_invitado=timezone_invitado,
            permite_overbooking=abierta,
            **_tracking_kwargs(tracking),
        )
        et_id = et.pk
        transaction.on_commit(lambda: invalidar_slots(et_id))
        transaction.on_commit(lambda: crear_evento_google(reserva.pk))
        # Conversiones server-side (Meta CAPI/TikTok/Google Ads/AC/Respond.io/CRM)
        # vía Celery. La reserva ya quedó creada; si Celery/Redis falla, no
        # bloquea ni rompe el booking.
        reserva.tags.add('browser_done')
        transaction.on_commit(lambda: _dispatch_schedule_conversions(reserva.pk))
        return reserva


def _dispatch_schedule_conversions(reserva_id):
    """Encola las tareas de conversión de la reserva (best-effort)."""
    try:
        from .tasks import dispatch_schedule_tasks
        dispatch_schedule_tasks(reserva_id)
    except Exception:
        logger.exception("No se pudieron encolar las tareas de conversión de la reserva %s", reserva_id)


def reemplazar_reserva(reserva_vieja_pk, event_type, inicio_utc, nombre_invitado,
                       email_invitado, telefono_invitado='', notas='', timezone_invitado='',
                       tracking=None):
    """
    Cancela la reserva vieja y crea una nueva, en una sola transacción atómica.
    Saltea el check de duplicado de crear_reserva porque, al cancelar primero,
    la búsqueda de "reserva futura confirmada con el mismo email" ya no
    encuentra la vieja.

    `tracking` (dict, opcional): tracking a guardar en la reserva nueva. Sin él
    se hereda el de la vieja (página pública: el reagendamiento no genera un
    recorrido nuevo). El funnel sí lo pasa, porque su reserva de reemplazo nace
    del mismo recorrido que la original y lleva su schedule_event_id vivo, que
    es contra el que deduplican el píxel y el CAPI.
    """
    with transaction.atomic():
        try:
            vieja = Reserva.objects.select_for_update().get(pk=reserva_vieja_pk)
        except Reserva.DoesNotExist:
            vieja = None

        if vieja and vieja.estado == Reserva.Estado.CONFIRMADA:
            vieja.estado = Reserva.Estado.CANCELADA
            vieja.save(update_fields=['estado', 'fecha_actualizacion'])
            vieja_et_id = vieja.event_type_id
            transaction.on_commit(lambda: invalidar_slots(vieja_et_id))
            if vieja.google_event_id:
                vieja_pk = vieja.pk
                transaction.on_commit(lambda: cancelar_evento_google(vieja_pk))

        # crear_reserva ahora no detecta duplicado porque la vieja está cancelada.
        # El reagendamiento conserva el tracking de la reserva original.
        if tracking is not None:
            tracking_previo = tracking
        else:
            tracking_previo = {f: getattr(vieja, f, '') for f in RESERVA_TRACKING_FIELDS} if vieja else None
        return crear_reserva(
            event_type=event_type,
            inicio_utc=inicio_utc,
            nombre_invitado=nombre_invitado,
            email_invitado=email_invitado,
            telefono_invitado=telefono_invitado,
            notas=notas,
            timezone_invitado=timezone_invitado,
            tracking=tracking_previo,
        )


def cancelar_reserva(reserva):
    """
    Cancela una reserva idempotente. Si ya está cancelada, no hace nada.
    También cancela el evento en Google Calendar.
    """
    if reserva.estado == Reserva.Estado.CANCELADA:
        return reserva
    with transaction.atomic():
        reserva.estado = Reserva.Estado.CANCELADA
        reserva.save(update_fields=['estado', 'fecha_actualizacion'])
        et_id = reserva.event_type_id
        transaction.on_commit(lambda: invalidar_slots(et_id))
        if reserva.google_event_id:
            transaction.on_commit(lambda: cancelar_evento_google(reserva.pk))
    return reserva


def eliminar_reserva(reserva):
    """
    Elimina la reserva de la BD y borra el evento de Google Calendar si existe.
    """
    google_event_id = reserva.google_event_id
    host_email = reserva.host.email
    with transaction.atomic():
        reserva.delete()
        if google_event_id:
            transaction.on_commit(
                lambda: _eliminar_google_event_directo(google_event_id, host_email)
            )


def _eliminar_google_event_directo(google_event_id, host_email):
    """Elimina un evento de Google Calendar dado su ID directamente (sin objeto Reserva)."""
    import logging
    logger = logging.getLogger(__name__)
    try:
        from calendario.google_calendar.services import obtener_servicio_calendar
        servicio = obtener_servicio_calendar(host_email)
        servicio.events().delete(calendarId='primary', eventId=google_event_id, sendUpdates='all').execute()
        logger.info("eliminar_reserva: evento Google %s eliminado (host=%s)", google_event_id, host_email)
    except Exception:
        logger.exception("eliminar_reserva: error borrando evento Google %s (host=%s)", google_event_id, host_email)
