"""
El sync incremental es el único sitio donde se ve un rechazo en el momento en
que pasa. Estos tests cubren el cableado: que el "No" del host y el del invitado
lleguen a `_cancelar_reservas_rechazadas` por el carril que les toca.

Van aparte de test_cancelar_rechazadas.py, que prueba la decisión de cancelar en
sí; aquí lo que se prueba es de dónde sale cada señal, porque las dos se leen
del item crudo de Google y se parecen mucho.
"""
from unittest.mock import MagicMock, patch

from django.test import TestCase

from calendario.google_calendar.models import GoogleCalendarSyncEstado
from calendario.google_calendar.sync import sincronizar_host_incremental
from tests.factories import crear_host

PATCH_SERVICIO = 'calendario.google_calendar.sync.obtener_servicio_calendar'
PATCH_CANCELAR = 'calendario.google_calendar.sync._cancelar_reservas_rechazadas'


def _servicio_que_devuelve(items):
    """Simula events().list() devolviendo una sola página."""
    servicio = MagicMock()
    request = MagicMock()
    request.execute.return_value = {'items': items, 'nextSyncToken': 'token-nuevo'}
    servicio.events.return_value.list.return_value = request
    servicio.events.return_value.list_next.return_value = None
    return servicio


def _evento(respuesta_host='accepted', respuesta_invitado='needsAction',
            status='confirmed'):
    return {
        'id': 'evt-1',
        'status': status,
        'summary': 'Sesión',
        'start': {'dateTime': '2030-01-01T10:00:00Z'},
        'end': {'dateTime': '2030-01-01T11:00:00Z'},
        'attendees': [
            {'email': 'host@x.com', 'self': True, 'responseStatus': respuesta_host},
            {'email': 'lead@x.com', 'responseStatus': respuesta_invitado},
        ],
    }


@patch(PATCH_CANCELAR)
class SyncIncrementalRechazosTest(TestCase):

    def setUp(self):
        self.host = crear_host()
        GoogleCalendarSyncEstado.objects.update_or_create(
            host=self.host, defaults={'sync_token': 'token-viejo'})

    def _sincronizar(self, items):
        with patch(PATCH_SERVICIO, return_value=_servicio_que_devuelve(items)):
            sincronizar_host_incremental(self.host)

    def test_el_no_del_host_va_por_la_lista_de_rechazados(self, mock_cancelar):
        self._sincronizar([_evento(respuesta_host='declined')])
        _host, rechazados, por_invitado = mock_cancelar.call_args[0]
        self.assertEqual(rechazados, ['evt-1'])
        self.assertEqual(por_invitado, {})

    def test_el_no_del_invitado_va_por_su_diccionario(self, mock_cancelar):
        self._sincronizar([_evento(respuesta_invitado='declined')])
        _host, rechazados, por_invitado = mock_cancelar.call_args[0]
        self.assertEqual(rechazados, [])
        self.assertEqual(por_invitado, {'evt-1': {'lead@x.com'}})

    def test_si_rechazan_los_dos_manda_el_host(self, mock_cancelar):
        # El evento ya está tachado y la hora libre: tratarlo como rechazo del
        # invitado solo cambiaría el motivo que se registra, para peor.
        self._sincronizar([
            _evento(respuesta_host='declined', respuesta_invitado='declined')])
        _host, rechazados, por_invitado = mock_cancelar.call_args[0]
        self.assertEqual(rechazados, ['evt-1'])
        self.assertEqual(por_invitado, {})

    def test_evento_borrado_en_google_cuenta_como_rechazo(self, mock_cancelar):
        self._sincronizar([{'id': 'evt-1', 'status': 'cancelled'}])
        _host, rechazados, por_invitado = mock_cancelar.call_args[0]
        self.assertEqual(rechazados, ['evt-1'])
        self.assertEqual(por_invitado, {})

    def test_evento_sin_rechazos_no_manda_nada(self, mock_cancelar):
        self._sincronizar([_evento()])
        _host, rechazados, por_invitado = mock_cancelar.call_args[0]
        self.assertEqual(rechazados, [])
        self.assertEqual(por_invitado, {})
