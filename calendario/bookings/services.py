import logging
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from django.core.cache import cache
from django.db import connections, transaction
from django.db.models import Count
from django.utils import timezone

from calendario.availability.models import BloqueHorarioSemanal, BloqueHorarioFecha
from calendario.event_types.models import EventType, EventTypeXHost
from calendario.google_calendar.services import (
    cancelar_evento_google, consultar_freebusy, crear_evento_google,
    eliminar_evento_google, obtener_busy_intervalos,
    obtener_busy_intervalos_local,
)
from .exceptions import ReservaDuplicadaError, SlotNoDisponibleError
from .models import Reserva
from .services_crm import notificar_crm

logger = logging.getLogger(__name__)


MAX_VENTANA_DIAS = 60
UTC = ZoneInfo('UTC')


def _intervals_overlap(a_inicio, a_fin, b_inicio, b_fin):
    return a_inicio < b_fin and b_inicio < a_fin


def _obtener_hosts_pool(event_type):
    """
    Hosts activos del pool del event_type, ordenados por pivot.id ASC.
    Si pool vacío, devuelve [].
    """
    pivots = (EventTypeXHost.objects
              .filter(event_type=event_type, host__is_active=True)
              .select_related('host')
              .order_by('id'))
    return [p.host for p in pivots]


def _obtener_busy_intervalos_con_fallback(host, desde_utc, hasta_utc):
    """
    Devuelve intervalos busy del host intentando primero la copia local.
    Fallback a freeBusy en vivo si el host no tiene sync activo (regla #2).
    """
    from calendario.google_calendar.models import GoogleCalendarSyncEstado
    try:
        sync_estado = GoogleCalendarSyncEstado.objects.get(host=host)
        if sync_estado.estado == GoogleCalendarSyncEstado.ACTIVO:
            return obtener_busy_intervalos_local(host, desde_utc, hasta_utc)
    except GoogleCalendarSyncEstado.DoesNotExist:
        pass
    return obtener_busy_intervalos(host.email, desde_utc, hasta_utc)


def _calcular_slots_para_host(event_type, host, fecha_desde, fecha_hasta):
    """
    Devuelve lista de inicio_utc aware-UTC disponibles para un host concreto.
    fecha_desde / fecha_hasta: date naive (interpretadas en TZ del host).
    Clamp servidor: fecha_hasta = min(fecha_hasta, fecha_desde + MAX_VENTANA_DIAS).
    """
    tz_host = ZoneInfo(host.timezone)
    duracion = event_type.duracion_minutos
    buffer_antes = event_type.buffer_antes_minutos
    buffer_despues = event_type.buffer_despues_minutos
    aviso = event_type.aviso_minimo_minutos

    fecha_hasta = min(fecha_hasta, fecha_desde + timedelta(days=MAX_VENTANA_DIAS))
    if fecha_hasta < fecha_desde:
        return []

    ahora_utc = timezone.now()
    minimo = ahora_utc + timedelta(minutes=aviso)
    maximo = ahora_utc + timedelta(days=event_type.aviso_maximo_dias)
    # Clamp fecha_hasta al día donde aún caben slots dentro del rolling window.
    fecha_hasta = min(fecha_hasta, maximo.astimezone(tz_host).date())
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

    desde_utc = datetime.combine(fecha_desde, datetime.min.time()).replace(tzinfo=tz_host).astimezone(UTC)
    hasta_utc = datetime.combine(fecha_hasta + timedelta(days=1), datetime.min.time()).replace(tzinfo=tz_host).astimezone(UTC)

    reservas = list(
        Reserva.objects.filter(
            host=host, estado=Reserva.Estado.CONFIRMADA,
            inicio_utc__lt=hasta_utc + timedelta(hours=24),
            fin_utc__gt=desde_utc - timedelta(hours=24),
        ).select_related('event_type').order_by('inicio_utc')
    )

    # Eventos externos cortos (<=duracion) se tratan como reuniones y reciben
    # buffer alrededor. Los largos se asumen bloqueos manuales (almuerzo,
    # focus time, etc.) y se respetan tal cual. Iguala el comportamiento de
    # Calendly.
    step_td = timedelta(minutes=duracion)
    busy_intervalos = [
        (b_ini - timedelta(minutes=buffer_antes), b_fin + timedelta(minutes=buffer_despues))
        if (b_fin - b_ini) <= step_td
        else (b_ini, b_fin)
        for b_ini, b_fin in _obtener_busy_intervalos_con_fallback(host, desde_utc, hasta_utc)
    ]

    slots = []
    step = timedelta(minutes=duracion)
    fecha_actual = fecha_desde
    while fecha_actual <= fecha_hasta:
        if fecha_actual in overrides_por_fecha:
            bloques_del_dia = overrides_por_fecha[fecha_actual]
        else:
            bloques_del_dia = bloques_por_dia[fecha_actual.weekday()]
        for bloque in bloques_del_dia:
            cursor_local = (
                datetime.combine(fecha_actual, bloque.hora_inicio).replace(tzinfo=tz_host)
                + timedelta(minutes=buffer_antes)
            )
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
                if slot_utc > maximo:
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
                cursor_local = next_cursor
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
    et_ids = (EventTypeXHost.objects
              .filter(host_id=host_id)
              .values_list('event_type_id', flat=True))
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
    Selecciona el host con menor número de reservas confirmadas para este event_type.
    Tiebreak: menor pivot.id (orden de añadido al pool).
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
    pivot_orden = dict(
        EventTypeXHost.objects
        .filter(event_type=event_type, host_id__in=host_ids)
        .values_list('host_id', 'id')
    )
    return min(
        candidatos,
        key=lambda h: (counts.get(h.id, 0), pivot_orden[h.id]),
    )


def crear_reserva(event_type, inicio_utc, nombre_invitado, email_invitado,
                  telefono_invitado='', notas='', timezone_invitado=''):
    """
    Crea una reserva eligiendo automáticamente un host del pool (round-robin
    least-loaded). Lock sobre la fila EventType para serializar concurrentes
    del mismo event_type. Lanza SlotNoDisponibleError si no hay candidato.
    """
    with transaction.atomic():
        et = EventType.objects.select_for_update().get(pk=event_type.pk)
        if not et.activo:
            raise SlotNoDisponibleError("El evento no está disponible.")

        if et.unico_por_invitado:
            email_norm = (email_invitado or '').strip().lower()
            existente = (Reserva.objects
                         .select_related('host', 'event_type')
                         .filter(event_type=et,
                                 estado=Reserva.Estado.CONFIRMADA,
                                 email_invitado__iexact=email_norm,
                                 fin_utc__gt=timezone.now())
                         .order_by('inicio_utc')
                         .first())
            if existente:
                raise ReservaDuplicadaError(existente)

        candidatos = _candidatos_para_slot(et, inicio_utc)
        if not candidatos:
            raise SlotNoDisponibleError("Ese slot ya no está disponible.")

        host_elegido = _seleccionar_host_round_robin(et, candidatos)
        fin_utc = inicio_utc + timedelta(minutes=et.duracion_minutos)

        if consultar_freebusy(host_elegido.email, inicio_utc, fin_utc):
            raise SlotNoDisponibleError("Ese slot ya no está disponible.")

        reserva = Reserva.objects.create(
            event_type=et,
            host=host_elegido,
            inicio_utc=inicio_utc,
            fin_utc=fin_utc,
            nombre_invitado=nombre_invitado.strip(),
            email_invitado=email_invitado,
            telefono_invitado=telefono_invitado.strip(),
            notas=notas.strip(),
            timezone_invitado=timezone_invitado,
        )
        et_id = et.pk
        transaction.on_commit(lambda: invalidar_slots(et_id))
        transaction.on_commit(lambda: crear_evento_google(reserva.pk))
        if et.notificar_crm:
            transaction.on_commit(lambda: notificar_crm(reserva.pk))
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
                       email_invitado, telefono_invitado='', notas='', timezone_invitado=''):
    """
    Cancela la reserva vieja y crea una nueva, en una sola transacción atómica.
    Saltea el check de duplicado de crear_reserva porque, al cancelar primero,
    la búsqueda de "reserva futura confirmada con el mismo email" ya no
    encuentra la vieja.
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

        # crear_reserva ahora no detecta duplicado porque la vieja está cancelada
        return crear_reserva(
            event_type=event_type,
            inicio_utc=inicio_utc,
            nombre_invitado=nombre_invitado,
            email_invitado=email_invitado,
            telefono_invitado=telefono_invitado,
            notas=notas,
            timezone_invitado=timezone_invitado,
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


def cancelar_reserva_solo_bd(reserva):
    """
    Marca la reserva como cancelada en BD únicamente.
    El evento de Google Calendar queda intacto.
    """
    if reserva.estado == Reserva.Estado.CANCELADA:
        return reserva
    reserva.estado = Reserva.Estado.CANCELADA
    reserva.save(update_fields=['estado', 'fecha_actualizacion'])
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
