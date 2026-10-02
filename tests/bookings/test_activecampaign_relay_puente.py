"""
Agendas por el puente de Relay (migración desde ActiveCampaign).

Calendar manda (todas las escuelas: cuáles atiende lo decide Relay; las demás responden 404) la agenda a Relay y Relay escribe en AC. Si Relay falla,
tarda o no responde 200, calendar etiqueta AC directamente como siempre (plan B). Sin la variable, nada cambia.
"""
from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import requests
from django.test import TestCase, override_settings

from calendario.bookings.conversions.services import activecampaign
from calendario.bookings.models import Reserva
from tests.factories import crear_event_type, crear_host, slot_futuro

RELAY = {'RELAY_API_URL': 'https://relay.test', 'RELAY_API_KEY': 'rl_live_prueba', 'RELAY_PUENTE_ESCUELAS': 'cb',
         'ACTIVECAMPAIGN_API_URL': 'https://ac.test/api/3', 'ACTIVECAMPAIGN_API_KEY': 'ac'}


def ctx(escuela='cb'):
    return SimpleNamespace(school_code=escuela, lead_email='lead@ejemplo.com', lead_name='Lucía Pérez',
                           lead_phone_number='+34600111222')


def respuesta(status=200, cuerpo=None):
    r = MagicMock(status_code=status)
    r.json.return_value = cuerpo if cuerpo is not None else {'relay': True, 'contacto': 1, 'ac': 'encolado'}
    return r


@override_settings(**RELAY)
class PuenteRelayTest(TestCase):

    def setUp(self):
        host = crear_host()
        inicio = slot_futuro()
        self.reserva = Reserva.objects.create(
            event_type=crear_event_type(host), host=host, inicio_utc=inicio, fin_utc=inicio + timedelta(minutes=30),
            nombre_invitado='Lucía Pérez', email_invitado='lead@ejemplo.com')
        self.ac = MagicMock()
        self.ac.create_or_update_contact.return_value = {'id': '77'}
        patch.object(activecampaign, 'ActiveCampaignClient', return_value=self.ac).start()
        self.addCleanup(patch.stopall)

    def agendar(self, escuela='cb', post=None):
        with patch.object(activecampaign, 'build_schedule_ctx', return_value=ctx(escuela)), \
                patch.object(activecampaign.requests, 'post', post or MagicMock(return_value=respuesta())) as p:
            activecampaign.push_schedule(self.reserva)
        return p

    def test_escuela_activada_y_200_no_toca_ac(self):
        p = self.agendar()
        p.assert_called_once()
        url = p.call_args.args[0]
        self.assertEqual(url, 'https://relay.test/api/v1/puente-ac/agenda')
        self.assertEqual(p.call_args.kwargs['timeout'], 2)
        self.assertEqual(p.call_args.kwargs['headers']['Authorization'], 'Bearer rl_live_prueba')
        self.assertEqual(p.call_args.kwargs['json'], {
            'email': 'lead@ejemplo.com', 'nombre_completo': 'Lucía Pérez', 'escuela': 'cb',
            'telefono': '+34600111222', 'origen': 'calendar', 'reiniciar': False})
        self.ac.create_or_update_contact.assert_not_called()
        self.ac.add_tag.assert_not_called()
        self.assertIn('sch_relay_puente_done', self.reserva.tags.names())

    def test_200_con_relay_false_tampoco_toca_ac(self):
        self.agendar(post=MagicMock(return_value=respuesta(cuerpo={'relay': False})))
        self.ac.add_tag.assert_not_called()

    def test_escuela_no_activada_en_relay_va_a_ac_como_siempre(self):
        p = self.agendar(escuela='cl', post=MagicMock(return_value=respuesta(404)))
        self.assertEqual(p.call_args.kwargs['json']['escuela'], 'cl')
        self.ac.add_tag.assert_called_once_with('77', '477')

    def test_plan_b_si_relay_falla(self):
        for post in (MagicMock(side_effect=requests.Timeout()), MagicMock(side_effect=requests.ConnectionError()),
                     MagicMock(return_value=respuesta(500)), MagicMock(return_value=respuesta(401)),
                     MagicMock(return_value=respuesta(404))):
            with self.subTest(post=post):
                self.ac.reset_mock()
                self.agendar(post=post)
                self.ac.create_or_update_contact.assert_called_once_with('lead@ejemplo.com', 'Lucía')
                self.ac.add_tag.assert_called_once_with('77', '460')

    @override_settings(RELAY_API_KEY='')
    def test_relay_sin_configurar_va_a_ac(self):
        p = self.agendar()
        p.assert_not_called()
        self.ac.add_tag.assert_called_once_with('77', '460')

    @override_settings(RELAY_PUENTE_ESCUELAS='cb,cf')
    def test_fi_se_normaliza_a_cf(self):
        p = self.agendar(escuela='fi')
        self.assertEqual(p.call_args.kwargs['json']['escuela'], 'cf')
        self.ac.add_tag.assert_not_called()
