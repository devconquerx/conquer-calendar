"""
Duplicado en el funnel (event_type con `unico_por_invitado`).

El endpoint /f/api/<slug>/reservar/ devuelve un 409 con los datos de la reserva
vieja para que el front pueda ofrecer reemplazarla, y acepta `reemplazar_token`
para cancelarla y crear la nueva en su lugar — el mismo trato que el modal de la
página pública de reserva.
"""
import json
from unittest.mock import patch

from django.test import TestCase
from django.urls import reverse

from calendario.bookings.models import Reserva
from calendario.funnels.models import FunnelForm, Prellamada
from tests.factories import (
    crear_disponibilidad, crear_event_type, crear_host, slot_futuro,
)

EMAIL = 'lead@ejemplo.com'


class ReservarDuplicadoFunnelTest(TestCase):

    def setUp(self):
        self.host = crear_host()
        self.et = crear_event_type(self.host)
        for dia in range(5):
            crear_disponibilidad(self.host, dia=dia)
        self.funnel = FunnelForm.objects.create(
            key='TestFunnel', slug='test-funnel', escuela='conquer-blocks',
            region='latam', nombre='Funnel de test', config={},
        )
        self.prellamada = Prellamada.objects.create(
            funnel=self.funnel, nombre='Lead', email=EMAIL,
            resultado=Prellamada.Resultado.CALENDARIO, event_type=self.et,
        )
        self.url = reverse('funnels:reservar', kwargs={'slug': self.funnel.slug})

    def _post(self, inicio_utc, **extra):
        body = {
            'prellamada_token': str(self.prellamada.token),
            'inicio_utc': inicio_utc.isoformat(),
            'tz': 'Europe/Madrid',
            'nombre': 'Lead',
            'email': EMAIL,
            **extra,
        }
        return self.client.post(self.url, data=json.dumps(body), content_type='application/json')

    @patch('calendario.funnels.views._enviar_correos_confirmacion')
    @patch('calendario.bookings.services.hay_conflicto_calendario', return_value=False)
    @patch('calendario.bookings.services.crear_evento_google')
    def test_segunda_reserva_devuelve_409_con_la_vieja(self, _ev, _conf, _mail):
        primera = self._post(slot_futuro())
        self.assertEqual(primera.status_code, 200)

        resp = self._post(slot_futuro(hora=12))
        self.assertEqual(resp.status_code, 409)
        data = resp.json()
        self.assertEqual(data['error'], 'duplicado')
        vieja = Reserva.objects.get(confirmacion_token=data['reserva_existente']['confirmacion_token'])
        self.assertEqual(vieja.estado, Reserva.Estado.CONFIRMADA)
        # El front necesita estos datos para pintar el modal.
        self.assertIn('inicio_utc', data['reserva_existente'])
        self.assertTrue(data['reserva_existente']['host'])
        self.assertEqual(data['reserva_existente']['event_type_nombre'], self.et.nombre)

    @patch('calendario.funnels.views._enviar_correos_confirmacion')
    @patch('calendario.bookings.services.hay_conflicto_calendario', return_value=False)
    @patch('calendario.bookings.services.cancelar_evento_google')
    @patch('calendario.bookings.services.crear_evento_google')
    def test_reemplazar_cancela_la_vieja_y_crea_la_nueva(self, _ev, _cancel, _conf, _mail):
        self._post(slot_futuro())
        duplicado = self._post(slot_futuro(hora=12)).json()
        token_viejo = duplicado['reserva_existente']['confirmacion_token']

        nuevo_inicio = slot_futuro(hora=12)
        resp = self._post(nuevo_inicio, reemplazar_token=token_viejo)
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.json()['ok'])

        vieja = Reserva.objects.get(confirmacion_token=token_viejo)
        self.assertEqual(vieja.estado, Reserva.Estado.CANCELADA)
        activas = Reserva.objects.filter(
            email_invitado__iexact=EMAIL, estado=Reserva.Estado.CONFIRMADA,
        )
        self.assertEqual(activas.count(), 1)
        self.assertEqual(activas.first().inicio_utc, nuevo_inicio)

    @patch('calendario.funnels.views._enviar_correos_confirmacion')
    @patch('calendario.bookings.services.hay_conflicto_calendario', return_value=False)
    @patch('calendario.bookings.services.crear_evento_google')
    def test_token_de_otro_email_no_cancela_nada(self, _ev, _conf, _mail):
        self._post(slot_futuro())
        duplicado = self._post(slot_futuro(hora=12)).json()
        token_viejo = duplicado['reserva_existente']['confirmacion_token']

        # Otro visitante mandando el token ajeno: rebota y la vieja sigue viva.
        otra_prellamada = Prellamada.objects.create(
            funnel=self.funnel, nombre='Otro', email='otro@ejemplo.com',
            resultado=Prellamada.Resultado.CALENDARIO, event_type=self.et,
        )
        body = {
            'prellamada_token': str(otra_prellamada.token),
            'inicio_utc': slot_futuro(hora=14).isoformat(),
            'tz': 'Europe/Madrid',
            'nombre': 'Otro',
            'email': 'otro@ejemplo.com',
            'reemplazar_token': token_viejo,
        }
        resp = self.client.post(self.url, data=json.dumps(body), content_type='application/json')
        self.assertEqual(resp.status_code, 404)
        self.assertEqual(resp.json()['error'], 'reemplazo_invalido')
        vieja = Reserva.objects.get(confirmacion_token=token_viejo)
        self.assertEqual(vieja.estado, Reserva.Estado.CONFIRMADA)
