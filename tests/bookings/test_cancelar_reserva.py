from unittest.mock import patch

from django.test import TestCase

from calendario.bookings.models import Reserva
from tests.factories import (
    crear_disponibilidad, crear_event_type, crear_host, slot_futuro, crear_reserva,
)


class CancelarReservaTest(TestCase):

    def setUp(self):
        self.host = crear_host()
        self.et = crear_event_type(self.host)
        for dia in range(5):
            crear_disponibilidad(self.host, dia=dia)

    def _reserva(self, inicio=None):
        with patch('calendario.bookings.services.consultar_freebusy', return_value=False), \
             patch('calendario.bookings.services.crear_evento_google'):
            return crear_reserva(self.et, inicio_utc=inicio or slot_futuro())

    @patch('calendario.bookings.services.eliminar_evento_google')
    def test_cancelar_cambia_estado(self, mock_eliminar):
        from calendario.bookings.services import cancelar_reserva
        reserva = self._reserva()
        cancelar_reserva(reserva)

        reserva.refresh_from_db()
        self.assertEqual(reserva.estado, Reserva.Estado.CANCELADA)

    def test_cancelar_llama_google(self):
        """eliminar_evento_google se dispara vía on_commit solo si hay google_event_id."""
        from calendario.bookings.services import cancelar_reserva
        reserva = self._reserva()
        reserva.google_event_id = 'evento-abc-123'
        reserva.save(update_fields=['google_event_id'])

        with patch('calendario.bookings.services.eliminar_evento_google') as mock_eliminar:
            with self.captureOnCommitCallbacks(execute=True):
                cancelar_reserva(reserva)

        mock_eliminar.assert_called_once_with(reserva.pk)

    def test_slot_liberado_tras_cancelacion(self):
        from calendario.bookings.services import cancelar_reserva
        inicio = slot_futuro()
        reserva = self._reserva(inicio)

        with patch('calendario.bookings.services.eliminar_evento_google'):
            cancelar_reserva(reserva)

        with patch('calendario.bookings.services.consultar_freebusy', return_value=False), \
             patch('calendario.bookings.services.crear_evento_google'):
            nueva = crear_reserva(self.et, inicio_utc=inicio)

        self.assertEqual(nueva.estado, Reserva.Estado.CONFIRMADA)
