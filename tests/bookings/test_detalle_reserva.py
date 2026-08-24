"""
Lo que la ficha de una reserva tiene que dejar ver de un vistazo.

- La hora de creación **con segundos**: sin ellos no se puede medir la distancia
  entre dos reservas seguidas, que es justo lo que distingue un doble envío
  (segundos) de dos reservas de verdad (minutos u horas). Ver
  tests/bookings/test_doble_envio_reserva.py.
- El **host**, con nombre y correo: el reparto es automático, así que a quién le
  ha tocado la reserva no se deduce de ningún otro campo de la ficha.
"""
from unittest.mock import patch

from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone as dj_timezone

from tests.factories import crear_disponibilidad, crear_event_type, crear_host, crear_reserva


class DetalleReservaCreadaTest(TestCase):

    @patch('calendario.bookings.services.hay_conflicto_calendario', return_value=False)
    @patch('calendario.bookings.services.crear_evento_google')
    def setUp(self, *_):
        self.host = crear_host()
        self.et = crear_event_type(self.host)
        for dia in range(5):
            crear_disponibilidad(self.host, dia=dia)
        self.reserva = crear_reserva(self.et)
        self.client = Client()
        self.client.force_login(self.host)

    def test_la_hora_de_creacion_lleva_segundos(self):
        resp = self.client.get(
            reverse('panel_reservas:reserva_detail', kwargs={'pk': self.reserva.pk})
        )
        self.assertEqual(resp.status_code, 200)

        creada = dj_timezone.localtime(self.reserva.fecha_creacion)
        self.assertContains(resp, creada.strftime('%d/%m/%Y %H:%M:%S'))

    def test_muestra_el_host_con_nombre_y_correo(self):
        resp = self.client.get(
            reverse('panel_reservas:reserva_detail', kwargs={'pk': self.reserva.pk})
        )
        self.assertContains(resp, self.reserva.host.nombre_display())
        self.assertContains(resp, f'mailto:{self.reserva.host.email}')
        self.assertContains(resp, self.reserva.host.email)
