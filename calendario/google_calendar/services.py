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


def consultar_freebusy(host_email, inicio_utc, fin_utc, ignorar_event_id=None):
    """
    Devuelve True si el rango [inicio_utc, fin_utc) colisiona con un evento
    en el calendario primario del host.
    Fail-open: si Google falla, devuelve False y loguea WARNING.
    ignorar_event_id: si está seteado y Google reporta busy, hace fallback con
    events.list y descarta ese eventId del cálculo (usado por reagendar).
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
        if not cal_info.get('busy'):
            return False
        if not ignorar_event_id:
            return True
        # Fallback: freeBusy no expone eventIds, así que listamos eventos
        # del rango y descartamos el que pidieron ignorar.
        eventos = servicio.events().list(
            calendarId='primary',
            timeMin=inicio_utc.isoformat(),
            timeMax=fin_utc.isoformat(),
            singleEvents=True,
            showDeleted=False,
        ).execute().get('items', [])
        for ev in eventos:
            if ev.get('id') == ignorar_event_id:
                continue
            if ev.get('status') == 'cancelled':
                continue
            if ev.get('transparency') == 'transparent':
                continue
            return True
        return False
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
                'summary': f'{reserva.event_type.nombre} con {reserva.nombre_invitado}',
                'description': reserva.notas or '',
                'start': {
                    'dateTime': reserva.inicio_utc.isoformat(),
                    'timeZone': 'UTC',
                },
                'end': {
                    'dateTime': reserva.fin_utc.isoformat(),
                    'timeZone': 'UTC',
                },
                'attendees': [
                    {'email': host_email, 'displayName': reserva.host.nombre_display()},
                    {'email': reserva.email_invitado, 'displayName': reserva.nombre_invitado},
                ],
                'conferenceData': {
                    'createRequest': {
                        'requestId': str(reserva.confirmacion_token),
                        'conferenceSolutionKey': {'type': 'hangoutsMeet'},
                    },
                },
                'reminders': {'useDefault': True},
            }
            evento = servicio.events().insert(
                calendarId='primary',
                body=body,
                conferenceDataVersion=1,
                sendUpdates='all',
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
