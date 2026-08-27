"""
Reenviar el mismo hueco desde otra Prellamada no puede dar error.

Caso real (FUNNELS-96, 112 veces en dos días): `crear_reserva` es idempotente
—pedir dos veces el mismo hueco devuelve la reserva que ya existe, que es lo que
evita las citas dobles—. Pero recargar el formulario crea una Prellamada nueva,
y `Prellamada.reserva` es OneToOne: al atar la segunda a la misma reserva
saltaba IntegrityError y el visitante veía un 500 DESPUÉS de haber reservado
bien.
"""
import json

from django.test import TestCase
from django.urls import reverse

from calendario.bookings.models import Reserva
from calendario.funnels.models import FunnelForm, Prellamada
from tests.factories import (
    crear_disponibilidad, crear_event_type, crear_host, slot_futuro,
)
from unittest.mock import patch

EMAIL = 'villalsofia651@gmail.com'


class ReservarReenvioTest(TestCase):

    def setUp(self):
        self.host = crear_host()
        self.et = crear_event_type(self.host)
        for dia in range(5):
            crear_disponibilidad(self.host, dia=dia)
        self.funnel = FunnelForm.objects.create(
            key='TestCl', slug='test-languages-latam', escuela='conquer-languages',
            region='latam', nombre='Funnel de test', config={},
        )
        self.url = reverse('funnels:reservar', kwargs={'slug': self.funnel.slug})
        self.inicio = slot_futuro()

    def _nueva_prellamada(self):
        """Cada recarga del formulario crea una fila nueva, con otro token."""
        return Prellamada.objects.create(
            funnel=self.funnel, nombre='Sofi', email=EMAIL,
            resultado=Prellamada.Resultado.CALENDARIO, event_type=self.et,
        )

    def _reservar(self, prellamada):
        return self.client.post(self.url, content_type='application/json', data=json.dumps({
            'prellamada_token': str(prellamada.token),
            'inicio_utc': self.inicio.isoformat(),
            'tz': 'America/Mexico_City',
            'nombre': 'Sofi', 'email': EMAIL, 'telefono': '+523310164313',
        }))

    @patch('calendario.funnels.views._avisar_si_es_nueva')
    @patch('calendario.bookings.services.hay_conflicto_calendario', return_value=False)
    @patch('calendario.bookings.services.crear_evento_google')
    def test_reenvio_desde_otra_prellamada_no_da_error(self, _ev, _cf, _mail):
        primera = self._nueva_prellamada()
        self.assertEqual(self._reservar(primera).status_code, 200)

        segunda = self._nueva_prellamada()          # el visitante recarga y repite
        resp = self._reservar(segunda)

        self.assertEqual(resp.status_code, 200)
        # Una sola reserva: la idempotencia sigue haciendo su trabajo.
        self.assertEqual(Reserva.objects.filter(email_invitado=EMAIL).count(), 1)
        # El vínculo se queda con la primera.
        reserva = Reserva.objects.get(email_invitado=EMAIL)
        primera.refresh_from_db(); segunda.refresh_from_db()
        self.assertEqual(primera.reserva_id, reserva.pk)
        self.assertIsNone(segunda.reserva_id)

    @patch('calendario.funnels.views._avisar_si_es_nueva')
    @patch('calendario.bookings.services.hay_conflicto_calendario', return_value=False)
    @patch('calendario.bookings.services.crear_evento_google')
    def test_el_reenvio_llega_marcado_como_reutilizado(self, _ev, _cf, avisar):
        """La marca `reutilizada` es la que impide repetir los correos; el
        reenvío tiene que llegar con ella puesta."""
        self._reservar(self._nueva_prellamada())
        self.assertFalse(getattr(avisar.call_args.args[0], 'reutilizada', False))

        self._reservar(self._nueva_prellamada())
        self.assertTrue(avisar.call_args.args[0].reutilizada)

    @patch('calendario.funnels.views._avisar_si_es_nueva')
    @patch('calendario.bookings.services.hay_conflicto_calendario', return_value=False)
    @patch('calendario.bookings.services.crear_evento_google')
    def test_el_camino_normal_sigue_enlazando(self, _ev, _cf, _mail):
        p = self._nueva_prellamada()
        self.assertEqual(self._reservar(p).status_code, 200)
        p.refresh_from_db()
        self.assertEqual(p.reserva_id, Reserva.objects.get(email_invitado=EMAIL).pk)
