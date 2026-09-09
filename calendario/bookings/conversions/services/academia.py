"""Registro de las sesiones 1 a 1 en la academia (LMS).

Quien tiene que responder «¿cuántas sesiones dio este profesor en agosto?» es la
academia, no este calendario. Así que cada reserva de un tipo de evento con
`registrar_en_academia` se le envía al LMS.

Qué tipos de evento llevan esa marca es una decisión de negocio, no técnica: la
casilla está en todos y se va marcando lo que interese. En particular no es «lo
que se embebe en la academia» —eso hoy son tres— sino cualquier sesión cuyo
recuento haga falta del otro lado.

Por qué se envía en vez de que la academia lo lea de aquí (que era la otra
opción sobre la mesa y evitaría duplicar el dato): este calendario mueve del
orden de 500 agendas al día y las reservas viejas se acabarán limpiando, porque
si no la tabla no para de crecer. El histórico académico no puede depender de
algo que está previsto borrar. Duplicar es el precio de que sobreviva.

El transporte es el endpoint GraphQL que la academia ya usa para sus conexiones
externas (`/graphql/`, Strawberry, autenticado con `X-API-Key`). Los nombres de
aquí siguen los suyos —inglés, `success`/`created`/`errors` en la respuesta—
porque el contrato vive en su esquema, no en el nuestro; el equivalente más
parecido que ya tienen es `syncBillingOrder`.

Una sola mutación para todo el ciclo de vida —alta, cancelación y
reagendamiento— y del lado del LMS un upsert por `reservationId`:

  * reagendar es cancelar la vieja y crear otra, así que llegan dos mutaciones
    con dos `reservationId` distintos y ninguna se pierde;
  * reintentar un envío que se quedó a medias no duplica la fila;
  * y una sesión cancelada llega como tal en vez de desaparecer, que es lo que
    hace que las métricas no cuenten clases que nunca ocurrieron.
"""
import logging
import time

import requests
from django.conf import settings

logger = logging.getLogger(__name__)


# El LMS usa claves en inglés también en sus `choices` (ver
# `CalendarEvent.RECURRENCE_CHOICES`), así que el estado se traduce en la
# frontera en vez de colarle nuestro vocabulario a su esquema.
ESTADOS = {
    'confirmada': 'confirmed',
    'cancelada': 'cancelled',
}


MUTATION = '''
mutation SyncCalendarSession($input: SyncCalendarSessionInput!) {
  syncCalendarSession(input: $input) {
    success
    created
    errors
  }
}
'''.strip()


def _config():
    """URL y clave, o None si la integración no está lista para enviar."""
    if not settings.ACADEMIA_ENABLED:
        return None
    url = (settings.ACADEMIA_GRAPHQL_URL or '').strip()
    api_key = (settings.ACADEMIA_API_KEY or '').strip()
    if not url or not api_key:
        return None
    return url, api_key


def construir_payload(reserva):
    """Los datos de la sesión tal como los recibe la academia.

    Nombres en inglés y en snake_case: Strawberry los expone en camelCase, que es
    como están el resto de las mutaciones del LMS (`order_id`, `academy_id`,
    `payment_status`…). Se manda poco y estable a propósito.
    """
    et = reserva.event_type
    host = reserva.host
    duracion = int((reserva.fin_utc - reserva.inicio_utc).total_seconds() // 60)

    return {
        # Identidad de la sesión. `reservationId` es la clave del upsert.
        'reservationId': str(reserva.pk),
        'status': ESTADOS.get(reserva.estado, reserva.estado),  # confirmed | cancelled
        # A qué academia del LMS pertenece la sesión. Se configura en el tipo de
        # evento porque desde aquí no hay forma de deducirlo: el `school_code`
        # del resto de integraciones sale del funnel o del Lead, y una clase 1 a
        # 1 reservada desde la academia no tiene ninguno de los dos.
        'academyId': et.academia_lms_id if reserva.event_type_id else None,
        # Profesor: es un usuario del calendario y un Professor en el LMS. El
        # email es lo que tienen en común, vía `Professor.user`.
        'professorEmail': (host.email or '').strip().lower(),
        'professorName': host.get_full_name() or host.email,
        # Alumno. `studentLmsId` sale del token que firma el LMS para el iframe;
        # mientras la academia siga enlazando al calendario en vez de embeberlo,
        # viene vacío y solo queda el email.
        'studentLmsId': reserva.alumno_lms_uid or '',
        'studentEmail': (reserva.email_invitado or '').strip().lower(),
        'studentName': reserva.nombre_invitado or '',
        # Evento.
        'eventTypeId': str(et.pk) if reserva.event_type_id else '',
        'eventTypeName': et.nombre if reserva.event_type_id else '',
        # Cuándo. Todo en UTC con ISO-8601 —el LMS ya guarda sus horas en UTC—;
        # la zona en la que el alumno reservó va aparte, por si algún día hace
        # falta pintarlo como él lo vio.
        'startsAt': reserva.inicio_utc.isoformat() if reserva.inicio_utc else None,
        'endsAt': reserva.fin_utc.isoformat() if reserva.fin_utc else None,
        'durationMinutes': duracion,
        'studentTimezone': reserva.timezone_invitado or '',
        'bookedAt': reserva.fecha_creacion.isoformat() if reserva.fecha_creacion else None,
        'meetUrl': reserva.google_meet_url or '',
    }


def push_sesion(reserva):
    """Envía (o reenvía) la sesión a la academia.

    Manda siempre el estado actual de la reserva, así que sirve igual para el
    alta y para la cancelación: es la misma mutación y del otro lado es el mismo
    upsert.
    """
    enviar_payload(construir_payload(reserva))


def enviar_payload(payload):
    """Manda un payload ya armado.

    Existe aparte de `push_sesion` para el borrado de una reserva: ahí la fila
    desaparece de la base y el payload hay que construirlo antes, así que no hay
    objeto que pasar cuando llega el momento de enviarlo.
    """
    config = _config()
    if config is None:
        logger.info(
            '[Academia] Envío desactivado o sin configurar, se omite la reserva %s',
            payload.get('reservationId'),
        )
        return
    url, api_key = config

    referencia = payload.get('reservationId')

    start = time.time()
    response = requests.post(
        url,
        json={
            'query': MUTATION,
            'variables': {'input': payload},
            'operationName': 'RegistrarSesionCalendario',
        },
        headers={
            'X-API-Key': api_key,
            'Content-Type': 'application/json',
        },
        timeout=settings.ACADEMIA_TIMEOUT_SECONDS,
    )
    elapsed_ms = int((time.time() - start) * 1000)

    if response.status_code != 200:
        logger.error(
            '[Academia] Reserva %s falló (%dms) — status=%d respuesta=%s',
            referencia, elapsed_ms, response.status_code, response.text[:500],
        )
        response.raise_for_status()

    # GraphQL responde 200 aunque la mutación haya fallado: el error va en el
    # cuerpo. Sin este control, un endpoint roto se vería como un envío correcto
    # y la sesión se perdería en silencio, que es justo lo que no puede pasar
    # con el dato del que salen las métricas.
    try:
        cuerpo = response.json()
    except ValueError:
        logger.error(
            '[Academia] Reserva %s: respuesta que no es JSON (%dms) — %s',
            referencia, elapsed_ms, response.text[:500],
        )
        raise

    errores = cuerpo.get('errors')
    if errores:
        logger.error(
            '[Academia] Reserva %s rechazada (%dms) — %s',
            referencia, elapsed_ms, str(errores)[:500],
        )
        raise RuntimeError(f'La academia rechazó la reserva {referencia}: {str(errores)[:200]}')

    datos = (cuerpo.get('data') or {}).get('syncCalendarSession') or {}
    if datos.get('success') is False:
        logger.error(
            '[Academia] Reserva %s no registrada (%dms) — %s',
            referencia, elapsed_ms, str(datos.get('errors'))[:500],
        )
        raise RuntimeError(
            f'La academia no registró la reserva {referencia}: {str(datos.get("errors"))[:200]}'
        )

    logger.info(
        '[Academia] Reserva %s registrada como %s (%dms) — %s',
        referencia, payload.get('status'), elapsed_ms, str(datos)[:200],
    )
