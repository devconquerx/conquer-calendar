"""
Las páginas del visitante no cargan el JavaScript del panel.

Reservar, confirmación, cancelar… extendían la misma base que el panel y se
llevaban su JavaScript entero —Metronic, jQuery, Bootstrap, select2—, que
ninguna usa. Pesaba ~0,9 MB comprimido y dentro del iframe de la academia era
parte de lo que tardaba en aparecer el calendario. Ahora extienden
`layout/visitante.html`, que lo deja fuera; el panel sigue igual.
"""
from datetime import datetime, timedelta, timezone as dt_timezone

from django.test import Client, TestCase
from django.urls import reverse

from calendario.bookings.models import Reserva
from calendario.users.models import User
from tests.factories import (
    EMAIL_INVITADO, NOMBRE_INVITADO, crear_disponibilidad, crear_event_type, crear_host,
)

JS_DEL_PANEL = ('plugins.bundle.js', 'scripts.bundle.js', 'jQuery(document)')


class LayoutVisitanteTest(TestCase):

    def setUp(self):
        self.client = Client()
        self.host = crear_host()
        crear_disponibilidad(self.host, dia=0)
        self.et = crear_event_type(self.host)
        inicio = datetime(2030, 6, 10, 15, 0, tzinfo=dt_timezone.utc)
        self.reserva = Reserva.objects.create(
            event_type=self.et, host=self.host, inicio_utc=inicio,
            fin_utc=inicio + timedelta(minutes=self.et.duracion_minutos),
            nombre_invitado=NOMBRE_INVITADO, email_invitado=EMAIL_INVITADO,
        )

    def assertSinJsDelPanel(self, resp):
        self.assertEqual(resp.status_code, 200)
        html = resp.content.decode()
        for trozo in JS_DEL_PANEL:
            self.assertNotIn(trozo, html)
        # Los estilos sí se quedan: de ellos depende cómo se ve la página.
        self.assertIn('style.bundle', html)

    def test_pagina_de_reserva(self):
        self.assertSinJsDelPanel(self.client.get(reverse('public_booking:booking_page', kwargs={
            'user_slug': self.host.slug, 'event_type_slug': self.et.slug})))

    def test_confirmacion(self):
        self.assertSinJsDelPanel(self.client.get(reverse(
            'public_token:confirmacion', kwargs={'token': self.reserva.confirmacion_token})))

    def test_cancelar(self):
        """Va por `layout/public.html`, que también pasa por la base del visitante."""
        self.assertSinJsDelPanel(self.client.get(reverse(
            'public_token:cancelar_publica', kwargs={'token': self.reserva.confirmacion_token})))

    def test_limite_alcanzado(self):
        self.assertSinJsDelPanel(self.client.get(reverse('public_token:limite_reservas')))

    def test_el_panel_lo_sigue_cargando(self):
        admin = User.objects.create_user(
            email='admin.layout@test.com', username='admin_layout',
            password='test1234', is_active=True, is_superuser=True,
        )
        self.client.force_login(admin)
        html = self.client.get(reverse('panel_event_types:event_type_list')).content.decode()
        for trozo in JS_DEL_PANEL:
            self.assertIn(trozo, html)
