import logging
import uuid
from datetime import datetime, timedelta, timezone

from django.conf import settings
from django.db import transaction
from django.utils import timezone as django_tz
from googleapiclient.errors import HttpError

from .exceptions import EmailFueraDeDominioError, ServiceAccountNoConfiguradaError
from .models import GoogleCalendarEvento, GoogleCalendarSyncEstado
from .services import obtener_servicio_calendar

logger = logging.getLogger(__name__)

_VENTANA_SYNC_DIAS = 90


def _parse_evento(item):
    """
    Extrae campos relevantes de un item de events.list.
    Devuelve dict listo para upsert, o None si el evento debe ignorarse
    (p.ej. eventos recurrentes padre sin fecha).
    """
    estado = item.get('status', 'confirmed')
    transparencia = item.get('transparency', 'opaque')

    start = item.get('start', {})
    end = item.get('end', {})

    es_todo_el_dia = 'date' in start and 'dateTime' not in start

    if es_todo_el_dia:
        try:
            inicio_utc = datetime.fromisoformat(start['date']).replace(
                hour=0, minute=0, second=0, microsecond=0, tzinfo=timezone.utc
            )
            fin_utc = datetime.fromisoformat(end['date']).replace(
                hour=0, minute=0, second=0, microsecond=0, tzinfo=timezone.utc
            )
        except (KeyError, ValueError):
            return None
    else:
        try:
            inicio_str = start.get('dateTime', '')
            fin_str = end.get('dateTime', '')
            if not inicio_str or not fin_str:
                return None
            inicio_utc = datetime.fromisoformat(inicio_str.replace('Z', '+00:00')).astimezone(timezone.utc)
            fin_utc = datetime.fromisoformat(fin_str.replace('Z', '+00:00')).astimezone(timezone.utc)
        except (ValueError, TypeError):
            return None

    if fin_utc <= inicio_utc:
        return None

    return {
        'inicio_utc': inicio_utc,
        'fin_utc': fin_utc,
        'es_todo_el_dia': es_todo_el_dia,
        'transparencia': transparencia,
        'estado': estado,
    }


def _upsert_evento(host, google_event_id, campos):
    """Upsert de un evento. Si cancelled/transparent, lo borra."""
    cancelado = campos['estado'] == 'cancelled'
    transparente = campos['transparencia'] == 'transparent'

    if cancelado or transparente:
        GoogleCalendarEvento.objects.filter(
            host=host, google_event_id=google_event_id
        ).delete()
        return

    GoogleCalendarEvento.objects.update_or_create(
        host=host,
        google_event_id=google_event_id,
        defaults=campos,
    )


def sincronizar_host_completo(host):
    """
    Sync completo desde events.list paginado. Idempotente.
    Limpia eventos previos del host y repuebla desde Google.
    Guarda nextSyncToken y marca estado='activo'.
    Fail-soft: loguea error y marca estado='error' sin propagar.
    """
    sync_estado, _ = GoogleCalendarSyncEstado.objects.get_or_create(host=host)

    try:
        servicio = obtener_servicio_calendar(host.email)
    except (ServiceAccountNoConfiguradaError, EmailFueraDeDominioError) as e:
        logger.error("sync_completo: no se puede obtener servicio para %s — %s", host.email, e)
        sync_estado.estado = GoogleCalendarSyncEstado.ERROR
        sync_estado.save(update_fields=['estado'])
        return

    ahora = django_tz.now()
    time_min = ahora.isoformat()
    time_max = (ahora + timedelta(days=_VENTANA_SYNC_DIAS)).isoformat()

    try:
        request = servicio.events().list(
            calendarId='primary',
            singleEvents=True,
            timeMin=time_min,
            timeMax=time_max,
            maxResults=250,
        )

        nuevos_eventos = {}
        next_sync_token = None

        while request is not None:
            response = request.execute()
            for item in response.get('items', []):
                google_event_id = item.get('id')
                if not google_event_id:
                    continue
                campos = _parse_evento(item)
                if campos is None:
                    continue
                nuevos_eventos[google_event_id] = campos

            next_sync_token = response.get('nextSyncToken')
            request = servicio.events().list_next(request, response)

        with transaction.atomic():
            # Limpia copia previa y repuebla
            GoogleCalendarEvento.objects.filter(host=host).delete()
            for google_event_id, campos in nuevos_eventos.items():
                cancelado = campos['estado'] == 'cancelled'
                transparente = campos['transparencia'] == 'transparent'
                if not cancelado and not transparente:
                    GoogleCalendarEvento.objects.create(
                        host=host,
                        google_event_id=google_event_id,
                        **campos,
                    )

            sync_estado.sync_token = next_sync_token or ''
            sync_estado.estado = GoogleCalendarSyncEstado.ACTIVO
            sync_estado.ultima_sync_utc = django_tz.now()
            sync_estado.save(update_fields=['sync_token', 'estado', 'ultima_sync_utc'])

        logger.info(
            "sync_completo: OK host=%s eventos_activos=%d sync_token=%s",
            host.email,
            GoogleCalendarEvento.objects.filter(host=host).count(),
            bool(next_sync_token),
        )

    except HttpError as e:
        logger.error(
            "sync_completo: HttpError %s para %s — %s", e.resp.status, host.email, e
        )
        sync_estado.estado = GoogleCalendarSyncEstado.ERROR
        sync_estado.save(update_fields=['estado'])
    except Exception:
        logger.exception("sync_completo: error inesperado para %s", host.email)
        sync_estado.estado = GoogleCalendarSyncEstado.ERROR
        sync_estado.save(update_fields=['estado'])


def sincronizar_host_incremental(host):
    """
    Sync incremental usando syncToken. Si recibe 410 Gone, hace resync completo.
    Usa select_for_update para serializar syncs concurrentes del mismo host.
    Fail-soft: loguea y sale sin romper el request del visitante.
    """
    try:
        sync_estado = GoogleCalendarSyncEstado.objects.get(host=host)
    except GoogleCalendarSyncEstado.DoesNotExist:
        logger.info("sync_incremental: no hay sync_estado para %s, iniciando sync completo", host.email)
        sincronizar_host_completo(host)
        return

    if not sync_estado.sync_token:
        logger.info("sync_incremental: sin sync_token para %s, iniciando sync completo", host.email)
        sincronizar_host_completo(host)
        return

    try:
        servicio = obtener_servicio_calendar(host.email)
    except (ServiceAccountNoConfiguradaError, EmailFueraDeDominioError) as e:
        logger.error("sync_incremental: no se puede obtener servicio para %s — %s", host.email, e)
        return

    try:
        with transaction.atomic():
            sync_estado = GoogleCalendarSyncEstado.objects.select_for_update(
                skip_locked=True
            ).filter(host=host).first()

            if sync_estado is None:
                # Otro proceso tiene el lock; ya está sincronizando
                logger.debug("sync_incremental: lock no obtenido para %s, omitiendo", host.email)
                return

            try:
                request = servicio.events().list(
                    calendarId='primary',
                    syncToken=sync_estado.sync_token,
                )
                next_sync_token = None
                hay_cambios = False

                while request is not None:
                    response = request.execute()
                    for item in response.get('items', []):
                        google_event_id = item.get('id')
                        if not google_event_id:
                            continue
                        campos = _parse_evento(item)
                        if campos is None:
                            continue
                        _upsert_evento(host, google_event_id, campos)
                        hay_cambios = True

                    next_sync_token = response.get('nextSyncToken')
                    request = servicio.events().list_next(request, response)

                sync_estado.sync_token = next_sync_token or sync_estado.sync_token
                sync_estado.ultima_sync_utc = django_tz.now()
                sync_estado.estado = GoogleCalendarSyncEstado.ACTIVO
                sync_estado.save(update_fields=['sync_token', 'ultima_sync_utc', 'estado'])

                if hay_cambios:
                    _invalidar_cache_por_host(host)

                logger.info("sync_incremental: OK host=%s cambios=%s", host.email, hay_cambios)

            except HttpError as e:
                if e.resp.status == 410:
                    logger.warning(
                        "sync_incremental: 410 Gone para %s, resync completo", host.email
                    )
                    # Salimos del atomic para hacer sync completo sin lock anidado
                    raise _ResyncNecesario()
                logger.error(
                    "sync_incremental: HttpError %s para %s — %s", e.resp.status, host.email, e
                )
                sync_estado.estado = GoogleCalendarSyncEstado.ERROR
                sync_estado.save(update_fields=['estado'])

    except _ResyncNecesario:
        sincronizar_host_completo(host)
    except Exception:
        logger.exception("sync_incremental: error inesperado para %s", host.email)


class _ResyncNecesario(Exception):
    pass


def registrar_canal_watch(host, webhook_url):
    """
    Registra un canal push con Google Calendar para el host.
    Guarda canal_id, canal_resource_id, canal_expira_utc en GoogleCalendarSyncEstado.
    Fail-soft: loguea y devuelve False si falla.
    """
    try:
        servicio = obtener_servicio_calendar(host.email)
    except (ServiceAccountNoConfiguradaError, EmailFueraDeDominioError) as e:
        logger.error("watch: no se puede obtener servicio para %s — %s", host.email, e)
        return False

    canal_id = str(uuid.uuid4())
    body = {
        'id': canal_id,
        'type': 'web_hook',
        'address': webhook_url,
    }

    try:
        response = servicio.events().watch(calendarId='primary', body=body).execute()
        expira_ms = int(response.get('expiration', 0))
        expira_utc = datetime.fromtimestamp(expira_ms / 1000, tz=timezone.utc) if expira_ms else None

        sync_estado, _ = GoogleCalendarSyncEstado.objects.get_or_create(host=host)
        sync_estado.canal_id = canal_id
        sync_estado.canal_resource_id = response.get('resourceId', '')
        sync_estado.canal_expira_utc = expira_utc
        sync_estado.save(update_fields=['canal_id', 'canal_resource_id', 'canal_expira_utc'])

        logger.info(
            "watch: canal registrado host=%s canal_id=%s expira=%s",
            host.email, canal_id, expira_utc,
        )
        return True

    except HttpError as e:
        logger.error("watch: HttpError %s para %s — %s", e.resp.status, host.email, e)
        return False
    except Exception:
        logger.exception("watch: error inesperado para %s", host.email)
        return False


def detener_canal(host):
    """Detiene el canal watch activo del host. Best-effort; ignora 404."""
    try:
        sync_estado = GoogleCalendarSyncEstado.objects.get(host=host)
    except GoogleCalendarSyncEstado.DoesNotExist:
        return

    if not sync_estado.canal_id or not sync_estado.canal_resource_id:
        return

    try:
        servicio = obtener_servicio_calendar(host.email)
        servicio.channels().stop(body={
            'id': sync_estado.canal_id,
            'resourceId': sync_estado.canal_resource_id,
        }).execute()
        logger.info("watch: canal detenido host=%s canal_id=%s", host.email, sync_estado.canal_id)
    except HttpError as e:
        if e.resp.status not in (404, 410):
            logger.warning("watch: error deteniendo canal para %s (HTTP %s)", host.email, e.resp.status)
    except (ServiceAccountNoConfiguradaError, EmailFueraDeDominioError) as e:
        logger.warning("watch: config/dominio error deteniendo canal para %s — %s", host.email, e)
    except Exception:
        logger.exception("watch: error inesperado deteniendo canal para %s", host.email)

    sync_estado.canal_id = ''
    sync_estado.canal_resource_id = ''
    sync_estado.canal_expira_utc = None
    sync_estado.save(update_fields=['canal_id', 'canal_resource_id', 'canal_expira_utc'])


def renovar_canales_por_expirar(margen_horas=24):
    """
    Renueva los canales watch cuya expiración está dentro del margen indicado.
    Requiere la URL del webhook; se lee de settings.GCAL_WEBHOOK_URL.
    """
    webhook_url = getattr(settings, 'GCAL_WEBHOOK_URL', '')
    if not webhook_url:
        logger.warning("renovar_canales: GCAL_WEBHOOK_URL no configurada, omitiendo renovación")
        return

    limite = django_tz.now() + timedelta(hours=margen_horas)
    por_renovar = GoogleCalendarSyncEstado.objects.filter(
        canal_expira_utc__lte=limite,
        canal_id__gt='',
    ).select_related('host')

    for sync_estado in por_renovar:
        host = sync_estado.host
        detener_canal(host)
        registrar_canal_watch(host, webhook_url)


def _invalidar_cache_por_host(host):
    """Invalida la cache de slots de todos los event_types del host."""
    from calendario.bookings.services import invalidar_slots_por_host
    invalidar_slots_por_host(host.id)
