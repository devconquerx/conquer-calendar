"""
Registro de lead y % de VSL por el puente de Relay (migración desde ActiveCampaign).

Calendar manda (todas las escuelas: cuáles atiende lo decide Relay; las demás responden 404) el lead y el % de VSL a Relay y Relay escribe en AC.
Si Relay falla, tarda o no responde 200, calendar escribe en AC directamente como siempre (plan B). Sin la variable,
nada cambia.
"""
from unittest.mock import MagicMock, patch

import requests
from django.test import TestCase, override_settings

from calendario.leads.models import Lead
from calendario.leads.services import activecampaign

RELAY = {'RELAY_API_URL': 'https://relay.test', 'RELAY_API_KEY': 'rl_live_prueba', 'RELAY_PUENTE_ESCUELAS_LEAD': 'cb',
         'ACTIVECAMPAIGN_API_URL': 'https://ac.test/api/3', 'ACTIVECAMPAIGN_API_KEY': 'ac'}


def respuesta(status=200):
    r = MagicMock(status_code=status)
    r.json.return_value = {'relay': False, 'ac': 'encolado'}
    return r


@override_settings(**RELAY)
class PuenteRelayLeadTest(TestCase):

    def setUp(self):
        self.lead = Lead.objects.create(email='lead@ejemplo.com', full_name='Lucía Pérez', funnel='cb-eu-2',
                                        utm_source='metaads', utm_campaign='c1', lead_phone='600111222',
                                        lead_phone_prefix='+34')
        self.ac = MagicMock()
        self.ac.create_or_update_contact.return_value = {'id': '77'}
        self.ac.get_contact_tags.return_value = []
        patch.object(activecampaign, 'ActiveCampaignClient', return_value=self.ac).start()
        patch.object(activecampaign, 'get_school_code', side_effect=lambda lead: self.escuela).start()
        patch.object(activecampaign, 'get_region_from_lead', return_value='EU').start()
        self.escuela = 'cb'
        self.addCleanup(patch.stopall)

    def registrar(self, post=None):
        with patch.object(activecampaign.requests, 'post', post or MagicMock(return_value=respuesta())) as p:
            activecampaign.push_lead(self.lead)
        return p

    def vsl(self, percent=30, region='usa', post=None):
        with patch.object(activecampaign.requests, 'post', post or MagicMock(return_value=respuesta())) as p:
            activecampaign.push_vsl_percent(self.lead, percent, region)
        return p

    def test_lead_escuela_activada_y_200_no_toca_ac(self):
        p = self.registrar()
        p.assert_called_once()
        self.assertEqual(p.call_args.args[0], 'https://relay.test/api/v1/puente-ac/lead')
        self.assertEqual(p.call_args.kwargs['timeout'], 2)
        self.assertEqual(p.call_args.kwargs['headers']['Authorization'], 'Bearer rl_live_prueba')
        enviado = dict(p.call_args.kwargs['json'])
        self.assertEqual((enviado.pop('referencia'), bool(enviado.pop('fecha'))), (f'calendar-lead:{self.lead.pk}', True))
        self.assertEqual(enviado, {
            'email': 'lead@ejemplo.com', 'nombre_completo': 'Lucía Pérez', 'escuela': 'cb', 'funnel': 'cb-eu-2',
            'telefono': '+34600111222', 'origen': 'calendar', 'utm_source': 'metaads', 'utm_campaign': 'c1'})
        self.ac.create_or_update_contact.assert_not_called()
        self.ac.add_tag.assert_not_called()
        self.lead.refresh_from_db()
        self.assertTrue(self.lead.is_form_vsl_processed)
        self.assertIn('relay_puente_lead_done', self.lead.tags.names())

    def test_lead_plan_b_si_relay_falla(self):
        for post in (MagicMock(side_effect=requests.Timeout()), MagicMock(side_effect=requests.ConnectionError()),
                     MagicMock(return_value=respuesta(500)), MagicMock(return_value=respuesta(404))):
            with self.subTest(post=post):
                self.ac.reset_mock()
                self.ac.create_or_update_contact.return_value = {'id': '77'}
                self.ac.get_contact_tags.return_value = []
                self.registrar(post=post)
                self.ac.create_or_update_contact.assert_called_once()
                self.ac.add_tag.assert_called_once_with('77', '502')
                self.ac.add_to_list.assert_called_once_with('77', '19', status=1)

    def test_lead_escuela_no_activada_en_relay_va_a_ac(self):
        self.escuela = 'cl'
        self.lead.funnel = 'cl-eu'
        p = self.registrar(post=MagicMock(return_value=respuesta(404)))
        self.assertEqual(p.call_args.kwargs['json']['escuela'], 'cl')
        self.ac.add_tag.assert_called_once_with('77', '466')

    @override_settings(RELAY_API_KEY='')
    def test_sin_relay_configurado_no_llama_a_relay(self):
        p = self.registrar()
        p.assert_not_called()
        self.ac.create_or_update_contact.assert_called_once()

    def test_vsl_por_el_puente(self):
        p = self.vsl(percent=30, region='usa')
        self.assertEqual(p.call_args.args[0], 'https://relay.test/api/v1/puente-ac/vsl')
        enviado = dict(p.call_args.kwargs['json'])
        registro = dict(enviado['registro'])
        self.assertEqual((registro.pop('referencia'), bool(registro.pop('fecha'))), (f'calendar-lead:{self.lead.pk}', True))
        enviado['registro'] = registro
        self.assertEqual(enviado, {
            'email': 'lead@ejemplo.com', 'escuela': 'cb', 'region': 'us', 'porcentaje': 30, 'origen': 'calendar',
            'registro': {'funnel': 'cb-eu-2', 'nombre_completo': 'Lucía Pérez',
                         'utm': {'utm_source': 'metaads', 'utm_campaign': 'c1'}, 'en_ac': False}})
        self.lead.tags.add('activecampaign_done')
        p = self.vsl(percent=40, region='usa')
        self.assertTrue(p.call_args.kwargs['json']['registro']['en_ac'])
        self.ac.create_or_update_contact.assert_not_called()

    def test_vsl_plan_b(self):
        self.vsl(percent=30, region='eu', post=MagicMock(side_effect=requests.Timeout()))
        self.ac.create_or_update_contact.assert_called_once_with('lead@ejemplo.com', field_values={'81': '30'})

    def test_vsl_region_del_lead_si_no_llega(self):
        p = self.vsl(percent=50, region=None)
        self.assertEqual(p.call_args.kwargs['json']['region'], 'eu')
