"""
La página pública de reserva: el tracking largo tampoco puede bloquearla.

Hermano de tests/funnels/test_tracking_largo.py. Allí el problema era un
DataError de Postgres; aquí es más silencioso: la página mete
`window.location.href` en un hidden al enviar (booking/page.html:669), y el
formulario lo validaba contra max_length=1500. Una URL más larga no reventaba,
simplemente daba el formulario por inválido y el visitante se quedaba sin
reserva por un campo oculto que ni sabe que existe.
"""
from datetime import timedelta

from django.test import TestCase
from django.utils import timezone

from calendario.bookings.forms import BookingForm
from calendario.bookings.models import Reserva


def datos(**extra):
    inicio = (timezone.now() + timedelta(days=3)).replace(microsecond=0)
    return {
        'inicio_utc': inicio.strftime('%Y-%m-%dT%H:%M:%S%z'),
        'nombre_invitado': 'Jorge Cristhian',
        'email_invitado': 'lead@ejemplo.com',
        'telefono_invitado': '+51977733243',
        **extra,
    }


class TrackingLargoFormTest(TestCase):

    def test_url_larguisima_no_invalida_el_formulario(self):
        url = 'https://www.conquerblocks.com/reservar/?ttclid=' + 'E_C_P_x' * 400  # 2846
        form = BookingForm(datos(url=url))

        self.assertTrue(form.is_valid(), form.errors.as_json())
        self.assertEqual(len(form.cleaned_data['url']), 1500)
        self.assertTrue(url.startswith(form.cleaned_data['url']))

    def test_setter_largo_tampoco(self):
        form = BookingForm(datos(setter='juan.perez' * 40))   # 400 > 140

        self.assertTrue(form.is_valid(), form.errors.as_json())
        self.assertEqual(len(form.cleaned_data['setter']), 140)

    def test_lo_que_cabe_se_queda_igual(self):
        url = 'https://www.conquerblocks.com/reservar/?utm_source=TikTokAds'
        form = BookingForm(datos(url=url, setter='juan.perez'))

        self.assertTrue(form.is_valid(), form.errors.as_json())
        self.assertEqual(form.cleaned_data['url'], url)
        self.assertEqual(form.cleaned_data['setter'], 'juan.perez')

    def test_el_recorte_usa_el_tope_real_de_la_columna(self):
        """Si alguien amplía la columna, el recorte debe seguirla sin tocar nada."""
        self.assertEqual(Reserva._meta.get_field('url').max_length, 1500)
        self.assertEqual(Reserva._meta.get_field('setter').max_length, 140)
