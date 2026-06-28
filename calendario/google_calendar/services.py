import logging
import os
from datetime import datetime

from django.conf import settings
from django.db import transaction
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from .exceptions import EmailFueraDeDominioError, ServiceAccountNoConfiguradaError

logger = logging.getLogger(__name__)


def obtener_credenciales_impersonadas(host_email, scopes):
    if not host_email:
        raise EmailFueraDeDominioError("Host sin email no es impersonable.")
    sa_file = settings.GOOGLE_SERVICE_ACCOUNT_FILE
    if not sa_file or not os.path.exists(sa_file):
        raise ServiceAccountNoConfiguradaError(
            "GOOGLE_SERVICE_ACCOUNT_FILE no apunta a un archivo válido."
        )
    creds = service_account.Credentials.from_service_account_file(sa_file, scopes=scopes)
    return creds.with_subject(host_email)


def obtener_servicio_calendar(host_email):
    creds = obtener_credenciales_impersonadas(host_email, settings.GOOGLE_CALENDAR_SCOPES)
    return build('calendar', 'v3', credentials=creds, cache_discovery=False)


def consultar_freebusy(host_email, inicio_utc, fin_utc):
    """
    Devuelve True si el rango [inicio_utc, fin_utc) colisiona con un evento
    en el calendario primario del host.
    Fail-open: si Google falla, devuelve False y loguea WARNING.
    """
    try:
        servicio = obtener_servicio_calendar(host_email)
    except (ServiceAccountNoConfiguradaError, EmailFueraDeDominioError) as e:
        logger.warning(
            "freebusy: no se puede consultar para %s — %s. Fail-open: sin conflicto.",
            host_email, e.__class__.__name__,
        )
        return False

    try:
        body = {
            'timeMin': inicio_utc.isoformat(),
            'timeMax': fin_utc.isoformat(),
            'timeZone': 'UTC',
            'items': [{'id': 'primary'}],
        }
        resp = servicio.freebusy().query(body=body).execute()
        cal_info = resp.get('calendars', {}).get('primary', {})
        if cal_info.get('errors'):
            logger.info(
                "freebusy: primary de %s con errores %s, ignorado.",
                host_email, cal_info['errors'],
            )
            return False
        return bool(cal_info.get('busy'))
    except HttpError as e:
        logger.warning(
            "freebusy: query falló para %s (HTTP %s). Fail-open: sin conflicto.",
            host_email, e.resp.status,
        )
        return False
    except Exception:
        logger.exception(
            "freebusy: error inesperado para %s. Fail-open: sin conflicto.", host_email,
        )
        return False


def hay_conflicto_calendario(host_email, inicio_utc, fin_utc, palabras_ignorar=None):
    """
    Chequeo de conflicto en vivo para la confirmación de una reserva, que
    respeta las reglas free/busy del tipo de evento.

    - Sin `palabras_ignorar`: delega en freeBusy (idéntico al comportamiento
      histórico; freeBusy no devuelve títulos pero es más barato).
    - Con `palabras_ignorar`: usa events.list (que sí trae el título) y reporta
      conflicto solo si hay un evento que se solapa cuyo título NO contiene
      ninguna de las palabras/emojis. Así un evento "liberado" no rechaza la
      reserva en la confirmación, igual que no la rechazó al pintar el slot.
    Fail-open: si Google falla, devuelve False (sin conflicto) y loguea WARNING.
    """
    if not palabras_ignorar:
        return consultar_freebusy(host_email, inicio_utc, fin_utc)

    try:
        servicio = obtener_servicio_calendar(host_email)
    except (ServiceAccountNoConfiguradaError, EmailFueraDeDominioError) as e:
        logger.warning(
            "conflicto_calendario: no se puede consultar para %s — %s. Fail-open.",
            host_email, e.__class__.__name__,
        )
        return False

    try:
        resp = servicio.events().list(
            calendarId='primary',
            singleEvents=True,
            timeMin=inicio_utc.isoformat(),
            timeMax=fin_utc.isoformat(),
            maxResults=50,
        ).execute()
        for item in resp.get('items', []):
            if item.get('status') == 'cancelled':
                continue
            if item.get('transparency', 'opaque') == 'transparent':
                continue
            if titulo_libera_horario(item.get('summary', ''), palabras_ignorar):
                continue
            return True
        return False
    except HttpError as e:
        logger.warning(
            "conflicto_calendario: query falló para %s (HTTP %s). Fail-open.",
            host_email, e.resp.status,
        )
        return False
    except Exception:
        logger.exception(
            "conflicto_calendario: error inesperado para %s. Fail-open.", host_email,
        )
        return False


def obtener_busy_intervalos(host_email, time_min_utc, time_max_utc):
    """
    Devuelve lista ordenada de (inicio_utc, fin_utc) ocupados en el calendario
    primario del host entre [time_min_utc, time_max_utc). Una sola llamada a freeBusy.
    Fail-open: si Google falla, devuelve [] y loguea WARNING.
    """
    try:
        servicio = obtener_servicio_calendar(host_email)
    except (ServiceAccountNoConfiguradaError, EmailFueraDeDominioError) as e:
        logger.warning(
            "busy_intervalos: no se puede consultar para %s — %s. Fail-open: sin ocupados.",
            host_email, e.__class__.__name__,
        )
        return []

    try:
        body = {
            'timeMin': time_min_utc.isoformat(),
            'timeMax': time_max_utc.isoformat(),
            'timeZone': 'UTC',
            'items': [{'id': 'primary'}],
        }
        resp = servicio.freebusy().query(body=body).execute()
        cal_info = resp.get('calendars', {}).get('primary', {})
        if cal_info.get('errors'):
            logger.info(
                "busy_intervalos: primary de %s con errores %s, ignorado.",
                host_email, cal_info['errors'],
            )
            return []
        intervalos = []
        for b in cal_info.get('busy', []):
            inicio = datetime.fromisoformat(b['start'].replace('Z', '+00:00'))
            fin = datetime.fromisoformat(b['end'].replace('Z', '+00:00'))
            intervalos.append((inicio, fin))
        intervalos.sort()
        return intervalos
    except HttpError as e:
        logger.warning(
            "busy_intervalos: query falló para %s (HTTP %s). Fail-open: sin ocupados.",
            host_email, e.resp.status,
        )
        return []
    except Exception:
        logger.exception(
            "busy_intervalos: error inesperado para %s. Fail-open: sin ocupados.", host_email,
        )
        return []


def titulo_libera_horario(titulo, palabras_ignorar):
    """
    True si el título de un evento de Google Calendar contiene alguna de las
    `palabras_ignorar` (regla free/busy del tipo de evento). Match 'includes'
    (substring) e insensible a mayúsculas, igual que el operador "Includes" de
    Calendly. Lista vacía -> nunca libera (comportamiento histórico).
    """
    if not palabras_ignorar:
        return False
    t = (titulo or '').casefold()
    return any(p.casefold() in t for p in palabras_ignorar if p)


def obtener_google_event_ids_liberados(host, time_min_utc, time_max_utc, palabras_ignorar):
    """
    Conjunto de google_event_id de la copia local cuyo título matchea alguna de
    las `palabras_ignorar` (reglas free/busy). Sirve para que una Reserva cuyo
    evento de Google Calendar fue marcado con el candado deje de bloquear el
    slot (igual que Calendly, que reserva por encima de sus propias reuniones si
    el título matchea). Lista vacía -> conjunto vacío.
    """
    if not palabras_ignorar:
        return set()
    from .models import GoogleCalendarEvento
    filas = (
        GoogleCalendarEvento.objects
        .filter(
            host=host,
            inicio_utc__lt=time_max_utc,
            fin_utc__gt=time_min_utc,
        )
        .exclude(estado='cancelled')
        .values_list('google_event_id', 'titulo')
    )
    return {
        gid for gid, titulo in filas
        if titulo_libera_horario(titulo, palabras_ignorar)
    }


def obtener_busy_intervalos_local(host, time_min_utc, time_max_utc, palabras_ignorar=None):
    """
    Devuelve lista ordenada de (inicio_utc, fin_utc) ocupados leyendo la copia
    local (GoogleCalendarEvento). Misma estructura que obtener_busy_intervalos.
    Solo considera eventos opaque y no cancelados.

    `palabras_ignorar`: si se pasa una lista no vacía, los eventos cuyo título
    contenga alguna de esas palabras/emojis NO se cuentan como ocupados (reglas
    free/busy). Sin palabras -> comportamiento idéntico al histórico.
    """
    from .models import GoogleCalendarEvento
    qs = (
        GoogleCalendarEvento.objects
        .filter(
            host=host,
            transparencia='opaque',
            inicio_utc__lt=time_max_utc,
            fin_utc__gt=time_min_utc,
        )
        .exclude(estado='cancelled')
        .order_by('inicio_utc')
    )
    if not palabras_ignorar:
        return list(qs.values_list('inicio_utc', 'fin_utc'))
    return [
        (inicio, fin)
        for titulo, inicio, fin in qs.values_list('titulo', 'inicio_utc', 'fin_utc')
        if not titulo_libera_horario(titulo, palabras_ignorar)
    ]


def _titulo_evento(reserva):
    fmt = reserva.event_type.formato_titulo_gcal
    if fmt == 'invitado_evento':
        return f'{reserva.nombre_invitado} - {reserva.event_type.nombre}'
    return f'{reserva.event_type.nombre} con {reserva.nombre_invitado}'


def _extraer_meet_uri(conference_data):
    for ep in conference_data.get('entryPoints', []):
        if ep.get('entryPointType') == 'video' and ep.get('uri'):
            return ep['uri']
    return ''


def crear_evento_google(reserva_pk):
    """
    Crea un evento Google Calendar + Meet para la reserva.
    Fail-soft: captura todas las excepciones y persiste google_sync_estado='error'.
    """
    from calendario.bookings.models import Reserva

    with transaction.atomic():
        try:
            reserva = Reserva.objects.select_for_update().get(pk=reserva_pk)
        except Reserva.DoesNotExist:
            logger.warning("crear_evento_google: reserva %s no existe", reserva_pk)
            return

        if reserva.estado == Reserva.Estado.CANCELADA:
            logger.info(
                "crear_evento_google: reserva %s ya cancelada, omitiendo.", reserva_pk,
            )
            return

        if reserva.google_sync_estado == Reserva.GoogleSyncEstado.SINCRONIZADO:
            logger.info(
                "crear_evento_google: reserva %s ya sincronizada, omitiendo.", reserva_pk,
            )
            return

        host_email = reserva.host.email

        try:
            servicio = obtener_servicio_calendar(host_email)
            body = {
                'summary': _titulo_evento(reserva),
                'description': '\n'.join(filter(None, [
                    f"Teléfono: {reserva.telefono_invitado}" if reserva.telefono_invitado else None,
                    f"Email: {reserva.email_invitado}",
                    f"Notas: {reserva.notas}" if reserva.notas else None,
                ])),
                'start': {
                    'dateTime': reserva.inicio_utc.isoformat(),
                    'timeZone': 'UTC',
                },
                'end': {
                    'dateTime': reserva.fin_utc.isoformat(),
                    'timeZone': 'UTC',
                },
                'attendees': [
                    {'email': host_email, 'displayName': reserva.host.nombre_display(), 'responseStatus': 'accepted'},
                    {'email': reserva.email_invitado, 'displayName': reserva.nombre_invitado, 'responseStatus': 'accepted'},
                ],
                'conferenceData': {
                    'createRequest': {
                        'requestId': str(reserva.confirmacion_token),
                        'conferenceSolutionKey': {'type': 'hangoutsMeet'},
                    },
                },
                'reminders': {'useDefault': True},
            }
            # Si Django tiene plantilla de correo para el invitado, suprime el
            # email de GCal para no duplicar. GCal sigue creando el evento y Meet.
            from calendario.bookings.correos import resolver_config
            _, cfg_inv = resolver_config(reserva, 'confirmacion_inv')
            send_updates = 'none' if cfg_inv else 'all'

            evento = servicio.events().insert(
                calendarId='primary',
                body=body,
                conferenceDataVersion=1,
                sendUpdates=send_updates,
            ).execute()

            reserva.google_event_id = evento['id']
            reserva.google_meet_url = (
                evento.get('hangoutLink')
                or _extraer_meet_uri(evento.get('conferenceData', {}))
            )
            reserva.google_sync_estado = Reserva.GoogleSyncEstado.SINCRONIZADO
            reserva.save(update_fields=[
                'google_event_id',
                'google_meet_url',
                'google_sync_estado',
                'fecha_actualizacion',
            ])
            logger.info(
                "crear_evento_google: OK reserva=%s host=%s event_id=%s",
                reserva_pk, host_email, evento['id'],
            )
        except (ServiceAccountNoConfiguradaError, EmailFueraDeDominioError) as e:
            logger.error(
                "crear_evento_google: config/dominio error reserva=%s host=%s — %s",
                reserva_pk, host_email, e,
            )
            reserva.google_sync_estado = Reserva.GoogleSyncEstado.ERROR
            reserva.save(update_fields=['google_sync_estado', 'fecha_actualizacion'])
        except HttpError as e:
            logger.error(
                "crear_evento_google: HttpError %s reserva=%s host=%s — %s",
                e.resp.status, reserva_pk, host_email, e,
            )
            reserva.google_sync_estado = Reserva.GoogleSyncEstado.ERROR
            reserva.save(update_fields=['google_sync_estado', 'fecha_actualizacion'])
        except Exception:
            logger.exception(
                "crear_evento_google: error inesperado reserva=%s host=%s",
                reserva_pk, host_email,
            )
            reserva.google_sync_estado = Reserva.GoogleSyncEstado.ERROR
            reserva.save(update_fields=['google_sync_estado', 'fecha_actualizacion'])


def cancelar_evento_google(reserva_pk):
    """
    Marca el evento en Google Calendar como cancelado: cambia el título a
    'Cancelado: ...' y lo pone transparente para liberar el hueco en freebusy.
    Notifica a todos los attendees via sendUpdates='all'.
    """
    from calendario.bookings.models import Reserva

    try:
        reserva = Reserva.objects.select_related('host', 'event_type').get(pk=reserva_pk)
    except Reserva.DoesNotExist:
        return

    if not reserva.google_event_id:
        return

    host_email = reserva.host.email

    try:
        servicio = obtener_servicio_calendar(host_email)
        evento_actual = servicio.events().get(
            calendarId='primary',
            eventId=reserva.google_event_id,
        ).execute()
        attendees_declinados = [
            {**a, 'responseStatus': 'declined'}
            for a in evento_actual.get('attendees', [])
        ]
        servicio.events().patch(
            calendarId='primary',
            eventId=reserva.google_event_id,
            body={
                'summary': f'Cancelado: {_titulo_evento(reserva)}',
                'transparency': 'transparent',
                'attendees': attendees_declinados,
            },
            sendUpdates='all',
        ).execute()
        logger.info(
            "cancelar_evento_google: OK reserva=%s host=%s event_id=%s",
            reserva_pk, host_email, reserva.google_event_id,
        )
    except HttpError as e:
        if e.resp.status in (404, 410):
            logger.info(
                "cancelar_evento_google: evento ya inexistente (HTTP %s) reserva=%s",
                e.resp.status, reserva_pk,
            )
            return
        logger.error(
            "cancelar_evento_google: HttpError %s reserva=%s host=%s — %s",
            e.resp.status, reserva_pk, host_email, e,
        )
    except (ServiceAccountNoConfiguradaError, EmailFueraDeDominioError) as e:
        logger.error(
            "cancelar_evento_google: config/dominio error reserva=%s host=%s — %s",
            reserva_pk, host_email, e,
        )
    except Exception:
        logger.exception(
            "cancelar_evento_google: error inesperado reserva=%s host=%s",
            reserva_pk, host_email,
        )


def eliminar_evento_google(reserva_pk):
    """
    Elimina el evento Google Calendar de la reserva. Idempotente.
    HttpError 404/410 se trata como éxito (ya borrado).
    """
    from calendario.bookings.models import Reserva

    try:
        reserva = Reserva.objects.get(pk=reserva_pk)
    except Reserva.DoesNotExist:
        return

    if not reserva.google_event_id:
        return

    host_email = reserva.host.email

    try:
        servicio = obtener_servicio_calendar(host_email)
        servicio.events().delete(
            calendarId='primary',
            eventId=reserva.google_event_id,
            sendUpdates='all',
        ).execute()
        logger.info(
            "eliminar_evento_google: OK reserva=%s host=%s event_id=%s",
            reserva_pk, host_email, reserva.google_event_id,
        )
    except HttpError as e:
        if e.resp.status in (404, 410):
            logger.info(
                "eliminar_evento_google: evento ya inexistente (HTTP %s) reserva=%s",
                e.resp.status, reserva_pk,
            )
            return
        logger.error(
            "eliminar_evento_google: HttpError %s reserva=%s host=%s — %s",
            e.resp.status, reserva_pk, host_email, e,
        )
    except (ServiceAccountNoConfiguradaError, EmailFueraDeDominioError) as e:
        logger.error(
            "eliminar_evento_google: config/dominio error reserva=%s host=%s — %s",
            reserva_pk, host_email, e,
        )
    except Exception:
        logger.exception(
            "eliminar_evento_google: error inesperado reserva=%s host=%s",
            reserva_pk, host_email,
        )
