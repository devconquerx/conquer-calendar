from datetime import timedelta
from unittest.mock import patch

from django.test import TestCase

from calendario.bookings.exceptions import SlotNoDisponibleError
from calendario.bookings.models import Reserva
from tests.factories import (
    EMAIL_INVITADO, NOMBRE_INVITADO,
    crear_disponibilidad, crear_event_type, crear_host, slot_futuro,
    crear_reserva,
)


class CrearReservaTest(TestCase):

    def setUp(self):
        self.host = crear_host()
        self.et = crear_event_type(self.host)
        crear_disponibilidad(self.host, dia=0)  # lunes
        crear_disponibilidad(self.host, dia=1)
        crear_disponibilidad(self.host, dia=2)
        crear_disponibilidad(self.host, dia=3)
        crear_disponibilidad(self.host, dia=4)

    @patch('calendario.bookings.services.hay_conflicto_calendario', return_value=False)
    @patch('calendario.bookings.services.crear_evento_google')
    def test_reserva_confirmada(self, mock_evento, mock_freebusy):
        inicio = slot_futuro()
        reserva = crear_reserva(self.et, inicio_utc=inicio)

        self.assertEqual(reserva.estado, Reserva.Estado.CONFIRMADA)
        self.assertEqual(reserva.email_invitado, EMAIL_INVITADO)
        self.assertEqual(reserva.nombre_invitado, NOMBRE_INVITADO)
        self.assertEqual(reserva.host, self.host)
        self.assertIsNotNone(reserva.confirmacion_token)

    @patch('calendario.bookings.services.hay_conflicto_calendario', return_value=False)
    @patch('calendario.bookings.services.crear_evento_google')
    def test_no_duplica_mismo_slot(self, mock_evento, mock_freebusy):
        inicio = slot_futuro()
        crear_reserva(self.et, inicio_utc=inicio)

        with self.assertRaises(SlotNoDisponibleError):
            crear_reserva(self.et, inicio_utc=inicio)

    @patch('calendario.bookings.services.hay_conflicto_calendario', return_value=True)
    @patch('calendario.bookings.services.crear_evento_google')
    def test_freebusy_ocupado_bloquea_reserva(self, mock_evento, mock_freebusy):
        inicio = slot_futuro()

        with self.assertRaises(SlotNoDisponibleError):
            crear_reserva(self.et, inicio_utc=inicio)

    @patch('calendario.bookings.services.hay_conflicto_calendario', return_value=False)
    @patch('calendario.bookings.services.crear_evento_google')
    def test_fin_utc_calculado_correctamente(self, mock_evento, mock_freebusy):
        inicio = slot_futuro()
        reserva = crear_reserva(self.et, inicio_utc=inicio)

        esperado = inicio + timedelta(minutes=self.et.duracion_minutos)
        self.assertEqual(reserva.fin_utc, esperado)

    @patch('calendario.bookings.services.hay_conflicto_calendario', return_value=False)
    @patch('calendario.bookings.services.crear_evento_google')
    def test_google_sync_pendiente_al_crear(self, mock_evento, mock_freebusy):
        inicio = slot_futuro()
        reserva = crear_reserva(self.et, inicio_utc=inicio)

        self.assertEqual(reserva.google_sync_estado, Reserva.GoogleSyncEstado.PENDIENTE)
