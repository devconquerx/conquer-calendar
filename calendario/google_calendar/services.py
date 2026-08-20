import logging
import os
import re
from datetime import datetime
from html import unescape

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


def construir_titulo_evento(et, nombre_invitado, host=None):
    """
    Título que llevará el evento de Google Calendar de una reserva.

    Formato único para todas las agendas: "Invitado y Host - Nombre del evento".
    Primero las personas y al final el evento, que es como se leen las agendas de
    un vistazo. Si no se sabe el host (llamadas antiguas sin ese dato) se cae a
    "Invitado - Nombre del evento".

    El campo `EventType.formato_titulo_gcal` ya no se consulta: el formato dejó de
    ser configurable por tipo de evento. El campo sigue en el modelo para no tocar
    la base de datos.

    Igual que Calendly, la app NUNCA añade nada más al título. Si quieres que las
    reservas de un tipo de evento se puedan pisar entre sí, mete la palabra/emoji
    de las reglas free/busy en el NOMBRE del tipo de evento.

    Se expone aparte de `_titulo_evento` porque al crear la reserva hay que saber
    el título antes de que exista el evento en Google (ver `crear_reserva`).
    """
    personas = (nombre_invitado or '').strip()
    nombre_host = host.nombre_display().strip() if host else ''
    if personas and nombre_host:
        personas = f'{personas} y {nombre_host}'
    elif nombre_host:
        personas = nombre_host
    if not personas:
        return et.nombre
    return f'{personas} - {et.nombre}'


def _html_a_texto(html):
    """Pasa el HTML del editor (Quill) a texto plano con saltos de línea.

    La descripción del evento se escribe en un editor rich text, así que llega
    como "<p>…</p><ul><li>…</li></ul>". En la descripción de Google Calendar el
    resto de líneas van en texto plano separadas por \n; si se colara HTML,
    Google renderizaría todo el campo como HTML y esos \n dejarían de verse.
    """
    if not html:
        return ''
    texto = re.sub(r'(?i)<br\s*/?>', '\n', html)
    texto = re.sub(r'(?i)</(p|div|li|h[1-6]|tr)>', '\n', texto)
    texto = re.sub(r'(?i)<li[^>]*>', '• ', texto)
    texto = re.sub(r'<[^>]+>', '', texto)
    texto = unescape(texto)
    texto = texto.replace('\xa0', ' ')
    texto = '\n'.join(linea.rstrip() for linea in texto.split('\n'))
    texto = re.sub(r'\n{3,}', '\n\n', texto)  # Quill deja <p><br></p> de relleno
    return texto.strip()


PIE_DESCRIPCION = 'Desarrollado por ConquerX'


def _descripcion_evento(reserva, meet_url=''):
    """Descripción del evento de Google Calendar: los datos de contacto del
    invitado, luego el nombre y la descripción del tipo de evento —para que el
    host abra la agenda y sepa de qué va la reunión— y al final el enlace de Meet.

    `meet_url` no se puede rellenar al crear el evento: la URL la devuelve Google
    en la respuesta del insert. Por eso `crear_evento_google` monta la descripción
    dos veces, la segunda ya con el enlace (ver el patch de allí).

    Cada bloque va separado por una línea en blanco.
    """
    et = reserva.event_type
    contacto = '\n'.join(filter(None, [
        f"Teléfono: {reserva.telefono_invitado}" if reserva.telefono_invitado else None,
        f"Email: {reserva.email_invitado}",
        f"Notas: {reserva.notas}" if reserva.notas else None,
    ]))
    meet = (
        'Esto es una conferencia web de Google Meet puedes unirte mediante este '
        f'enlace:\n{meet_url}'
    ) if meet_url else None
    return '\n\n'.join(filter(None, [
        contacto,
        'Nombre del evento:',
        et.nombre,
        # La descripción va suelta, sin etiqueta que la anuncie.
        _html_a_texto(et.descripcion),
        meet,
        PIE_DESCRIPCION,
    ]))


def _titulo_evento(reserva):
    return construir_titulo_evento(
        reserva.event_type, reserva.nombre_invitado, reserva.host,
    )


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
                'description': _descripcion_evento(reserva),
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

            # El evento se crea en silencio a propósito. El enlace de Meet solo lo
            # devuelve Google en esta respuesta, así que si la invitación saliera
            # aquí viajaría con la descripción todavía sin el enlace — y el .ics
            # que reciben Outlook y Apple es una foto fija: la corrección posterior
            # no les llega nunca. Se avisa en el patch de más abajo, ya con la
            # descripción completa.
            evento = servicio.events().insert(
                calendarId='primary',
                body=body,
                conferenceDataVersion=1,
                sendUpdates='none',
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

            # Segunda escritura: reescribe la descripción ya con el enlace de Meet
            # y es la que dispara la invitación. Se ejecuta SIEMPRE, aunque no haya
            # enlace: Google crea la sala de forma asíncrona y a veces responde con
            # la conferencia aún pendiente, y si esto fuese condicional esas reservas
            # se quedarían sin avisar a nadie. Sin enlace la descripción sale igual
            # que antes, pero el invitado recibe su invitación.
            # num_retries deja que el cliente de Google haga backoff ante el
            # rateLimitExceeded que devuelve al escribir dos veces seguidas.
            try:
                servicio.events().patch(
                    calendarId='primary',
                    eventId=evento['id'],
                    body={'description': _descripcion_evento(reserva, reserva.google_meet_url)},
                    sendUpdates=send_updates,
                ).execute(num_retries=3)
            except Exception:
                # El evento existe y la reserva está sincronizada, así que no se
                # marca como fallida. Pero la gravedad depende de quién avisa: si
                # el correo lo manda Django solo se pierde una línea de texto; si
                # lo mandaba Google, el invitado se ha quedado sin invitación.
                if send_updates == 'none':
                    logger.exception(
                        "crear_evento_google: no se pudo añadir el enlace de Meet a la "
                        "descripción, reserva=%s event_id=%s", reserva_pk, evento['id'],
                    )
                else:
                    logger.exception(
                        "crear_evento_google: la invitación de Google NO se envió, "
                        "reserva=%s event_id=%s invitado=%s",
                        reserva_pk, evento['id'], reserva.email_invitado,
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


def cancelar_evento_google(reserva_pk, avisar_invitado=True):
    """
    Marca el evento en Google Calendar como cancelado: cambia el título a
    'Cancelado: ...' y lo pone transparente para liberar el hueco en freebusy.

    `avisar_invitado=True` (por defecto) notifica a los attendees con
    sendUpdates='all', que es el correo de cancelación que le llega al invitado.
    En False el evento se marca igual pero en silencio: sirve para poner al día
    reservas viejas sin escribir a gente por citas que ya nadie esperaba.
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
            sendUpdates='all' if avisar_invitado else 'none',
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
