"""
El botón SOS del CRM pasa una llamada de un closer a otro con `events.move`: el
evento sale del calendario del primero y aparece, con el mismo ID, en el del
segundo, que queda como organizador.

Visto desde el calendario de origen eso llega igual que un borrado —`status:
cancelled`—, así que el sync cancelaba la reserva de una cita que seguía en pie.
Estos tests fijan las dos mitades del arreglo: un evento movido no cancela y la
reserva pasa al host nuevo; y un evento borrado o rechazado de verdad (que es
como cancelan los closers desde Calendar) sigue cancelando igual que antes.
"""
from io import StringIO
from unittest.mock import MagicMock, patch

from django.core.management import call_command
from django.test import TestCase, override_settings

from calendario.bookings.models import CancelacionReserva, Reserva
from calendario.google_calendar.models import GoogleCalendarEvento, GoogleCalendarSyncEstado
from calendario.google_calendar.sync import (
    _cancelar_reservas_rechazadas, _evento_movido, _reasignar_reservas_recibidas,
    sincronizar_host_incremental,
)
from tests.factories import (
    crear_disponibilidad, crear_event_type, crear_host, slot_futuro,
)

PATCH_SERVICIO_SYNC = 'calendario.google_calendar.sync.obtener_servicio_calendar'
PATCH_CONFLICTO = 'calendario.bookings.services.hay_conflicto_calendario'
PATCH_CREAR = 'calendario.bookings.services.crear_evento_google'
PATCH_CANCELAR_GCAL = 'calendario.bookings.services.cancelar_evento_google'

GID = 'gcal-evt-sos'


# Formas reales de `events().get` desde el calendario de origen, tal como las
# devolvió Google en producción el 17/09/2026.
def _get_movido():
    return {
        'kind': 'calendar#event', 'id': GID, 'status': 'cancelled',
        'etag': '"1"', 'htmlLink': 'https://x', 'iCalUID': f'{GID}@google.com',
        'updated': '2026-09-17T14:00:00Z', 'transparency': 'opaque',
        'start': {'dateTime': '2030-01-01T10:00:00Z'},
        'end': {'dateTime': '2030-01-01T10:45:00Z'},
    }


def _get_borrado():
    return {
        'id': GID, 'status': 'cancelled', 'summary': 'Lead y Closer - Sesión',
        'organizer': {'email': 'origen@x.com', 'self': True},
        'attendees': [
            {'email': 'origen@x.com', 'self': True, 'organizer': True,
             'responseStatus': 'accepted'},
            {'email': 'lead@x.com', 'responseStatus': 'accepted'},
        ],
    }


def _get_en_destino(organiza='destino@x.com', yo='destino@x.com'):
    """El mismo evento pedido desde otro calendario que lo tiene."""
    return {
        'id': GID, 'status': 'confirmed', 'summary': 'Lead y Origen - Sesión',
        'organizer': {'email': organiza, 'self': organiza == yo},
        'attendees': [
            {'email': organiza, 'organizer': True, 'self': organiza == yo,
             'responseStatus': 'accepted'},
            {'email': 'lead@x.com', 'responseStatus': 'accepted'},
        ],
    }


PATCH_PEDIR = 'calendario.google_calendar.sync._pedir_evento'


def _google(**por_email):
    """
    Simula `_pedir_evento` calendario por calendario: `origen=..., destino=...`
    con el item que devuelve Google desde cada uno, o una excepción.
    """
    def pedir(host_email, _gid):
        respuesta = por_email.get(host_email.split('@')[0])
        if respuesta is None:
            raise Exception(f'404 en {host_email}')
        if isinstance(respuesta, Exception):
            raise respuesta
        return respuesta
    return MagicMock(side_effect=pedir)


def _servicio_get(respuesta=None, error=None):
    servicio = MagicMock()
    get = servicio.events.return_value.get.return_value
    if error:
        get.execute.side_effect = error
    else:
        get.execute.return_value = respuesta
    return servicio


class EventoMovidoTest(TestCase):

    def test_movido(self):
        self.assertTrue(_evento_movido(_get_movido()))

    def test_borrado_por_su_dueno_no_es_movido(self):
        self.assertFalse(_evento_movido(_get_borrado()))

    def test_evento_vivo_no_es_movido(self):
        self.assertFalse(_evento_movido({'id': GID, 'status': 'confirmed'}))


class _ConDosClosers(TestCase):
    """Base sin tests propios: los @patch van en cada subclase, porque en la
    base no llegan a los métodos test_* que definen las hijas."""


    def setUp(self):
        self.origen = crear_host(email='origen@x.com', first_name='Origen')
        self.destino = crear_host(email='destino@x.com', first_name='Destino')
        for host in (self.origen, self.destino):
            for dia in range(7):
                crear_disponibilidad(host, dia=dia)
        self.et = crear_event_type(self.origen, nombre='Sesión de Consultoría')

    def _reserva(self, event_type=None, gid=GID, inicio=None):
        from calendario.bookings.services import crear_reserva
        r = crear_reserva(
            event_type=event_type or self.et, inicio_utc=inicio or slot_futuro(),
            nombre_invitado='Lead', email_invitado='lead@x.com',
        )
        r.google_event_id = gid
        r.save(update_fields=['google_event_id'])
        return r

    def _en_copia_local(self, host, reserva):
        GoogleCalendarEvento.objects.create(
            host=host, google_event_id=reserva.google_event_id,
            titulo='Lead y Closer - Sesión',
            inicio_utc=reserva.inicio_utc, fin_utc=reserva.fin_utc,
        )


@patch(PATCH_CANCELAR_GCAL)
@patch(PATCH_CONFLICTO, return_value=False)
@patch(PATCH_CREAR)
@override_settings(CANCELAR_RECHAZOS_DESDE='2020-01-01T00:00:00')
class CancelacionEnOrigenTest(_ConDosClosers):
    """Lo que ve el sync del closer que suelta la llamada."""

    def _cancelar(self, origen=None, destino=None, cancelados=(GID,)):
        google = _google(origen=origen, destino=destino or _get_en_destino())
        with patch(PATCH_PEDIR, google):
            _cancelar_reservas_rechazadas(
                self.origen, [GID], {}, cancelados=list(cancelados))
        return google

    def test_movido_pasa_la_reserva_al_nuevo_closer(self, *_):
        r = self._reserva()
        self._en_copia_local(self.destino, r)
        self._cancelar(_get_movido())
        r.refresh_from_db()
        self.assertEqual(r.estado, Reserva.Estado.CONFIRMADA)
        self.assertEqual(r.host, self.destino)
        self.assertFalse(CancelacionReserva.objects.filter(reserva=r).exists())

    def test_movido_no_avisa_a_nadie(self, _crear, _conf, mock_cancelar_gcal):
        r = self._reserva()
        self._en_copia_local(self.destino, r)
        with self.captureOnCommitCallbacks(execute=True):
            self._cancelar(_get_movido())
        mock_cancelar_gcal.assert_not_called()

    def test_un_closer_solo_invitado_no_se_queda_la_reserva(self, *_):
        # El ID también está en el calendario de quien estaba invitado a la
        # cita (lo que le pasó a Lucas con Heumir), pero no es el organizador:
        # el evento se movió a otra persona.
        r = self._reserva()
        self._en_copia_local(self.destino, r)
        self._cancelar(
            _get_movido(),
            destino=_get_en_destino(organiza='fuera@x.com'),
        )
        r.refresh_from_db()
        self.assertEqual(r.estado, Reserva.Estado.CONFIRMADA)
        self.assertEqual(r.host, self.origen)

    def test_movido_sin_destino_conocido_no_cancela(self, *_):
        # El sync del destino aún no ha pasado (o el closer nuevo no es host de
        # la app): mejor dejarla en pie que cancelar una cita viva.
        r = self._reserva()
        self._cancelar(_get_movido())
        r.refresh_from_db()
        self.assertEqual(r.estado, Reserva.Estado.CONFIRMADA)
        self.assertEqual(r.host, self.origen)

    def test_borrado_de_verdad_sigue_cancelando(self, *_):
        r = self._reserva()
        self._cancelar(_get_borrado())
        r.refresh_from_db()
        self.assertEqual(r.estado, Reserva.Estado.CANCELADA)

    def test_borrado_con_copia_en_otro_calendario_sigue_cancelando(self, *_):
        # Que el ID esté en otro calendario (un invitado del workspace, una
        # cuenta alias) no convierte un borrado en un movimiento.
        r = self._reserva()
        self._en_copia_local(self.destino, r)
        self._cancelar(_get_borrado())
        r.refresh_from_db()
        self.assertEqual(r.estado, Reserva.Estado.CANCELADA)
        self.assertEqual(r.host, self.origen)

    def test_si_google_falla_se_cancela_como_antes(self, *_):
        r = self._reserva()
        self._cancelar(origen=Exception('red caída'))
        r.refresh_from_db()
        self.assertEqual(r.estado, Reserva.Estado.CANCELADA)

    def test_el_no_del_closer_no_consulta_a_google(self, *_):
        # Rechazar la invitación no mueve nada: cancela sin llamada extra.
        r = self._reserva()
        google = self._cancelar(_get_movido(), cancelados=())
        google.assert_not_called()
        r.refresh_from_db()
        self.assertEqual(r.estado, Reserva.Estado.CANCELADA)

    def test_nuevo_closer_ocupado_a_esa_hora_no_se_reasigna_ni_se_cancela(self, *_):
        inicio = slot_futuro()
        r = self._reserva(inicio=inicio)
        et_destino = crear_event_type(self.destino, nombre='Otra sesión')
        self._reserva(event_type=et_destino, gid='otro-evento', inicio=inicio)
        self._en_copia_local(self.destino, r)
        self._cancelar(_get_movido())
        r.refresh_from_db()
        self.assertEqual(r.estado, Reserva.Estado.CONFIRMADA)
        self.assertEqual(r.host, self.origen)

    def test_libera_el_hueco_del_origen_y_ocupa_el_del_destino(self, *_):
        from calendario.bookings.services import calcular_slots
        r = self._reserva()
        et_destino = crear_event_type(self.destino, nombre='Otra sesión')
        dia = r.inicio_utc.date()
        self.assertNotIn(r.inicio_utc, calcular_slots(self.et, dia, dia))
        self.assertIn(r.inicio_utc, calcular_slots(et_destino, dia, dia))
        self._en_copia_local(self.destino, r)
        self._cancelar(_get_movido())
        # Se quita el evento de la copia local del destino para comprobar que
        # quien le ocupa el hueco es la reserva, no el evento.
        GoogleCalendarEvento.objects.filter(host=self.destino).delete()
        self.assertIn(r.inicio_utc, calcular_slots(self.et, dia, dia))
        self.assertNotIn(r.inicio_utc, calcular_slots(et_destino, dia, dia))


@patch(PATCH_CANCELAR_GCAL)
@patch(PATCH_CONFLICTO, return_value=False)
@patch(PATCH_CREAR)
class RecepcionEnDestinoTest(_ConDosClosers):
    """Lo que ve el sync del closer que se queda la llamada."""

    def test_reasigna_cuando_el_origen_ya_no_tiene_el_evento(self, *_):
        r = self._reserva()
        _reasignar_reservas_recibidas(self.destino, [GID])
        r.refresh_from_db()
        self.assertEqual(r.host, self.destino)

    def test_espera_si_el_origen_todavia_lo_tiene(self, *_):
        # O su sync no ha pasado aún, o las dos cuentas son el mismo buzón.
        r = self._reserva()
        self._en_copia_local(self.origen, r)
        _reasignar_reservas_recibidas(self.destino, [GID])
        r.refresh_from_db()
        self.assertEqual(r.host, self.origen)

    def test_no_toca_reservas_canceladas(self, *_):
        from calendario.bookings.services import cancelar_reserva
        r = self._reserva()
        cancelar_reserva(r)
        _reasignar_reservas_recibidas(self.destino, [GID])
        r.refresh_from_db()
        self.assertEqual(r.host, self.origen)

    def test_devolver_la_llamada_la_vuelve_a_pasar(self, *_):
        # El líder la devuelve desde el CRM: otro `events.move`, al revés.
        r = self._reserva()
        _reasignar_reservas_recibidas(self.destino, [GID])
        _reasignar_reservas_recibidas(self.origen, [GID])
        r.refresh_from_db()
        self.assertEqual(r.host, self.origen)


def _servicio_list(items):
    servicio = MagicMock()
    request = MagicMock()
    request.execute.return_value = {'items': items, 'nextSyncToken': 'token-nuevo'}
    servicio.events.return_value.list.return_value = request
    servicio.events.return_value.list_next.return_value = None
    return servicio


@patch(PATCH_CANCELAR_GCAL)
@patch(PATCH_CONFLICTO, return_value=False)
@patch(PATCH_CREAR)
@override_settings(CANCELAR_RECHAZOS_DESDE='2020-01-01T00:00:00')
class SyncIncrementalMovidoTest(_ConDosClosers):
    """El recorrido completo por el sync incremental, en los dos calendarios."""

    def _sincronizar(self, host, items, get=None):
        GoogleCalendarSyncEstado.objects.update_or_create(
            host=host, defaults={'sync_token': 'token-viejo'})
        google = _google(origen=get, destino=_get_en_destino())
        with patch(PATCH_SERVICIO_SYNC, return_value=_servicio_list(items)), \
                patch(PATCH_PEDIR, google):
            sincronizar_host_incremental(host)

    def _item_en_destino(self, r):
        return {
            'id': GID, 'status': 'confirmed', 'summary': 'Lead y Origen - Sesión',
            'start': {'dateTime': r.inicio_utc.isoformat()},
            'end': {'dateTime': r.fin_utc.isoformat()},
            'organizer': {'email': 'destino@x.com', 'self': True},
            'attendees': [
                {'email': 'destino@x.com', 'self': True, 'organizer': True,
                 'responseStatus': 'accepted'},
                {'email': 'lead@x.com', 'responseStatus': 'accepted'},
            ],
        }

    def test_origen_primero_y_destino_despues(self, *_):
        r = self._reserva()
        self._en_copia_local(self.origen, r)
        self._sincronizar(self.origen, [{'id': GID, 'status': 'cancelled'}], get=_get_movido())
        r.refresh_from_db()
        self.assertEqual((r.estado, r.host), (Reserva.Estado.CONFIRMADA, self.origen))
        self._sincronizar(self.destino, [self._item_en_destino(r)])
        r.refresh_from_db()
        self.assertEqual((r.estado, r.host), (Reserva.Estado.CONFIRMADA, self.destino))

    def test_destino_primero_y_origen_despues(self, *_):
        r = self._reserva()
        self._en_copia_local(self.origen, r)
        self._sincronizar(self.destino, [self._item_en_destino(r)])
        r.refresh_from_db()
        self.assertEqual(r.host, self.origen)
        self._sincronizar(self.origen, [{'id': GID, 'status': 'cancelled'}], get=_get_movido())
        r.refresh_from_db()
        self.assertEqual((r.estado, r.host), (Reserva.Estado.CONFIRMADA, self.destino))

    def test_closer_que_borra_el_evento_sigue_cancelando(self, *_):
        r = self._reserva()
        self._en_copia_local(self.origen, r)
        self._sincronizar(self.origen, [{'id': GID, 'status': 'cancelled'}], get=_get_borrado())
        r.refresh_from_db()
        self.assertEqual(r.estado, Reserva.Estado.CANCELADA)

    def test_closer_que_rechaza_sigue_cancelando(self, *_):
        r = self._reserva()
        self._en_copia_local(self.origen, r)
        item = {
            'id': GID, 'status': 'confirmed',
            'start': {'dateTime': r.inicio_utc.isoformat()},
            'end': {'dateTime': r.fin_utc.isoformat()},
            'organizer': {'email': 'origen@x.com', 'self': True},
            'attendees': [
                {'email': 'origen@x.com', 'self': True, 'responseStatus': 'declined'},
                {'email': 'lead@x.com', 'responseStatus': 'accepted'},
            ],
        }
        self._sincronizar(self.origen, [item])
        r.refresh_from_db()
        self.assertEqual(r.estado, Reserva.Estado.CANCELADA)


@patch('calendario.bookings.management.commands.cancelar_reservas_rechazadas.cancelar_reserva')
@patch(PATCH_CANCELAR_GCAL)
@patch(PATCH_CONFLICTO, return_value=False)
@patch(PATCH_CREAR)
class ComandoManualMovidoTest(_ConDosClosers):

    def test_el_comando_no_cancela_eventos_movidos(self, _crear, _conf, _cancelar_gcal, mock_cancelar):
        r = self._reserva()
        GoogleCalendarSyncEstado.objects.update_or_create(
            host=self.origen, defaults={'estado': GoogleCalendarSyncEstado.ACTIVO})
        salida = StringIO()
        with patch(
            'calendario.bookings.management.commands.cancelar_reservas_rechazadas.obtener_servicio_calendar',
            return_value=_servicio_get(_get_movido()),
        ):
            call_command('cancelar_reservas_rechazadas', '--aplicar', stdout=salida)
        mock_cancelar.assert_not_called()
        self.assertIn('A cancelar: 0', salida.getvalue())
        r.refresh_from_db()
        self.assertEqual(r.estado, Reserva.Estado.CONFIRMADA)
