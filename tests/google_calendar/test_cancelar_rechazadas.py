"""
Un "No" del host en la invitación de Google es su forma de cancelar: los closers
de los funnels no entran a la app. El sync debe cancelar esa reserva, que es lo
que libera el hueco, corta los recordatorios y avisa al invitado.

Antes solo se quitaba el evento de la copia local: el calendario quedaba libre
pero la reserva seguía confirmada, así que el hueco seguía bloqueado y el
invitado no se enteraba de nada.
"""
from unittest.mock import patch

from django.test import TestCase, override_settings

from calendario.bookings.models import Reserva
from calendario.google_calendar.sync import (
    _cancelar_reservas_rechazadas, _host_declino,
)
from tests.factories import (
    crear_disponibilidad, crear_event_type, crear_host, slot_futuro,
)

PATCH_CONFLICTO = 'calendario.bookings.services.hay_conflicto_calendario'
PATCH_CREAR = 'calendario.bookings.services.crear_evento_google'
PATCH_CANCELAR_GCAL = 'calendario.bookings.services.cancelar_evento_google'


def _item(status='confirmed', mi_respuesta='accepted', invitado='needsAction'):
    return {
        'id': 'gcal-evt-1',
        'status': status,
        'attendees': [
            {'email': 'host@x.com', 'self': True, 'responseStatus': mi_respuesta},
            {'email': 'lead@x.com', 'responseStatus': invitado},
        ],
    }


class HostDeclinoTest(TestCase):

    def test_detecta_el_no_del_host(self):
        self.assertTrue(_host_declino(_item(mi_respuesta='declined')))

    def test_no_confunde_el_no_del_invitado_con_el_del_host(self):
        self.assertFalse(_host_declino(_item(invitado='declined')))

    def test_evento_aceptado_no_es_rechazo(self):
        self.assertFalse(_host_declino(_item()))

    def test_evento_sin_attendees(self):
        self.assertFalse(_host_declino({'id': 'x', 'status': 'confirmed'}))


# El corte de arranque (`CANCELAR_RECHAZOS_DESDE`) hace que por defecto no se
# cancele nada: sin él, activar esto sobre una base con rechazos viejos los
# drenaría todos de golpe. Aquí se pone una fecha pasada para probar el
# comportamiento en sí.
@override_settings(CANCELAR_RECHAZOS_DESDE='2020-01-01T00:00:00')
@patch(PATCH_CANCELAR_GCAL)
@patch(PATCH_CONFLICTO, return_value=False)
@patch(PATCH_CREAR)
class CancelarReservasRechazadasTest(TestCase):

    def setUp(self):
        self.host = crear_host()
        self.et = crear_event_type(self.host, nombre='Sesión de Consultoría')
        for dia in range(7):
            crear_disponibilidad(self.host, dia=dia)

    def _reserva(self, gid='gcal-evt-1'):
        from calendario.bookings.services import crear_reserva
        r = crear_reserva(
            event_type=self.et, inicio_utc=slot_futuro(),
            nombre_invitado='Lead', email_invitado='lead@x.com',
        )
        r.google_event_id = gid
        r.save(update_fields=['google_event_id'])
        return r

    def test_cancela_la_reserva_del_evento_rechazado(self, *_):
        r = self._reserva()
        _cancelar_reservas_rechazadas(self.host, ['gcal-evt-1'])
        r.refresh_from_db()
        self.assertEqual(r.estado, Reserva.Estado.CANCELADA)

    def test_avisa_al_invitado_por_google(self, _crear, _conf, mock_cancelar_gcal):
        r = self._reserva()
        # El aviso sale por transaction.on_commit, que dentro de TestCase no se
        # dispara solo: hay que capturar los callbacks para ejecutarlos.
        with self.captureOnCommitCallbacks(execute=True):
            _cancelar_reservas_rechazadas(self.host, ['gcal-evt-1'])
        # cancelar_evento_google hace el patch con sendUpdates='all'.
        mock_cancelar_gcal.assert_called_once_with(r.pk, avisar_invitado=True)

    def test_libera_el_hueco(self, *_):
        from calendario.bookings.services import calcular_slots
        r = self._reserva()
        dia = r.inicio_utc.date()
        self.assertNotIn(r.inicio_utc, calcular_slots(self.et, dia, dia))
        _cancelar_reservas_rechazadas(self.host, ['gcal-evt-1'])
        self.assertIn(r.inicio_utc, calcular_slots(self.et, dia, dia))

    def test_sale_de_los_recordatorios(self, *_):
        r = self._reserva()
        _cancelar_reservas_rechazadas(self.host, ['gcal-evt-1'])
        pendientes = Reserva.objects.filter(
            estado=Reserva.Estado.CONFIRMADA, inicio_utc__gt=r.inicio_utc.replace(hour=0))
        self.assertNotIn(r, list(pendientes))

    def test_no_toca_reservas_de_otros_eventos(self, *_):
        r = self._reserva()
        _cancelar_reservas_rechazadas(self.host, ['otro-evento-id'])
        r.refresh_from_db()
        self.assertEqual(r.estado, Reserva.Estado.CONFIRMADA)

    def test_es_idempotente(self, _crear, _conf, mock_cancelar_gcal):
        r = self._reserva()
        with self.captureOnCommitCallbacks(execute=True):
            _cancelar_reservas_rechazadas(self.host, ['gcal-evt-1'])
            _cancelar_reservas_rechazadas(self.host, ['gcal-evt-1'])
        r.refresh_from_db()
        self.assertEqual(r.estado, Reserva.Estado.CANCELADA)
        # El segundo paso no vuelve a avisar al invitado.
        self.assertEqual(mock_cancelar_gcal.call_count, 1)

    def test_lista_vacia_no_hace_nada(self, *_):
        r = self._reserva()
        _cancelar_reservas_rechazadas(self.host, [])
        r.refresh_from_db()
        self.assertEqual(r.estado, Reserva.Estado.CONFIRMADA)
