"""
Cancelación desde el enlace de los correos (/r/<token>/cancelar/).

El enlace viaja en un <a href> del correo de confirmación y del recordatorio, o
sea que se abre con GET. La vista solo tenía POST, así que devolvía 405 y la
reserva se quedaba viva: el invitado creía haber cancelado y el hueco seguía
ocupado.

Ahora el GET enseña una página de confirmación y solo el POST cancela. El GET no
puede cancelar: los clientes de correo y los antivirus abren los enlaces solos
para previsualizarlos, y cancelarían reservas sin que nadie las tocara.
"""
from datetime import datetime, timedelta, timezone as dt_timezone
from unittest.mock import patch

from django.test import Client, TestCase
from django.urls import reverse

from calendario.bookings.models import Reserva
from tests.factories import (
    EMAIL_INVITADO, NOMBRE_INVITADO, crear_event_type, crear_host,
)


class CancelarPublicaTest(TestCase):

    def setUp(self):
        self.client = Client()
        self.host = crear_host()
        self.et = crear_event_type(self.host)
        inicio = datetime(2030, 6, 10, 15, 0, tzinfo=dt_timezone.utc)
        self.reserva = Reserva.objects.create(
            event_type=self.et,
            host=self.host,
            inicio_utc=inicio,
            fin_utc=inicio + timedelta(minutes=self.et.duracion_minutos),
            nombre_invitado=NOMBRE_INVITADO,
            email_invitado=EMAIL_INVITADO,
            timezone_invitado='America/Caracas',
        )
        self.url = reverse(
            'public_token:cancelar_publica',
            kwargs={'token': self.reserva.confirmacion_token},
        )

    def test_get_no_cancela_y_pide_confirmacion(self):
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(resp.context['ya_cancelada'])
        self.reserva.refresh_from_db()
        self.assertEqual(self.reserva.estado, Reserva.Estado.CONFIRMADA)

    def test_get_muestra_la_hora_en_la_tz_del_invitado(self):
        # 15:00 UTC = 11:00 en Caracas (UTC-4).
        resp = self.client.get(self.url)
        self.assertEqual(resp.context['inicio_hora_str'], '11:00')
        self.assertEqual(resp.context['tz_display'], 'America/Caracas')

    @patch('calendario.bookings.services.eliminar_evento_google')
    def test_post_cancela(self, _google):
        resp = self.client.post(self.url)
        self.assertEqual(resp.status_code, 200)
        self.reserva.refresh_from_db()
        self.assertEqual(self.reserva.estado, Reserva.Estado.CANCELADA)

    @patch('calendario.bookings.services.eliminar_evento_google')
    def test_get_sobre_una_ya_cancelada_avisa_sin_romper(self, _google):
        self.client.post(self.url)
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.context['ya_cancelada'])
