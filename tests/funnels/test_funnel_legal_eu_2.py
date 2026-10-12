"""La segunda landing de Conquer Legal EU (legal-eu-2, código cg-eu-2).

Registro y prellamada propios, reserva compartida con legal-eu. Lo que se
rompe si falla algo de esto no se ve en la página: el visitante se cambia de
funnel a mitad del recorrido (y su prellamada cuenta como de legal-eu), o el
lead llega al CRM con un código que no reconoce.

La fila la crea la migración 0037 clonando la de legal-eu.
"""
import json

from django.test import TestCase
from django.urls import reverse

from calendario.funnels.models import FunnelForm, Prellamada
from calendario.leads.models import Lead

SLUG = 'legal-eu-2'
LEGAL = {'HTTP_HOST': 'www.conquerlegal.com'}


class LegalEu2SembradoTest(TestCase):

    def test_clona_legal_eu_con_su_propia_key(self):
        eu2 = FunnelForm.objects.get(key='LegalEu2')
        eu = FunnelForm.objects.get(key='LegalEu')
        self.assertEqual((eu2.slug, eu2.escuela, eu2.region), (SLUG, 'conquer-legal', 'eu'))
        self.assertTrue(eu2.activo)
        self.assertEqual(eu2.config['key'], 'LegalEu2')
        # Mismo evento de reserva: los tramos de score apuntan a los mismos EventTypes.
        self.assertEqual(eu2.config['score_ranges'], eu.config['score_ranges'])
        self.assertEqual(eu2.config['landing'], eu.config['landing'])


class LegalEu2PaginasTest(TestCase):

    def _get(self, url, etapa):
        resp = self.client.get(url, **LEGAL)
        self.assertEqual(resp.status_code, 200, url)
        self.assertEqual(resp.context['slug'], SLUG, url)
        self.assertEqual(resp.context['stage'], etapa, url)
        return resp

    def test_sus_tres_paginas_sirven_su_funnel(self):
        self._get('/hub/registro-2-eu', 'landing')
        self._get('/hub/video-2-eu', 'video')
        self._get('/hub/agendar-2-eu', 'stepform')

    def test_las_urls_que_emite_no_saltan_a_legal_eu(self):
        resp = self.client.get('/hub/registro-2-eu', **LEGAL)
        self.assertEqual(resp.context['landing_url'], '/hub/registro-2-eu')
        self.assertEqual(resp.context['video_url'], '/hub/video-2-eu')
        self.assertEqual(resp.context['stepform_url'], '/hub/agendar-2-eu')
        self.assertEqual(resp.context['confirmation_url'], '/hub/confirmacion')

    def test_legal_eu_sigue_con_las_suyas(self):
        for url in ('/hub/registro-eu', '/hub/video-eu', '/hub/agendar-eu'):
            with self.subTest(url=url):
                resp = self.client.get(url, **LEGAL)
                self.assertEqual(resp.context['slug'], 'legal-eu')
        resp = self.client.get('/hub/registro-eu', **LEGAL)
        self.assertEqual(resp.context['stepform_url'], '/hub/agendar-eu')


class LegalEu2RegistroYPrellamadaTest(TestCase):

    def test_el_lead_llega_al_crm_como_cg_eu_2(self):
        from calendario.leads.services.activecampaign import FUNNEL_TAG_MAP
        from calendario.leads.services.utils import get_region_from_lead, get_school_code

        resp = self.client.post(
            reverse('funnels:register_lead'),
            data=json.dumps({'email': 'legal2@ejemplo.com', 'name': 'Lead Legal 2',
                             'escuela': 'conquer-legal', 'funnel': SLUG}),
            content_type='application/json',
        )
        self.assertEqual(resp.status_code, 200)
        lead = Lead.objects.get()
        self.assertEqual(lead.funnel, 'cg-eu-2')
        self.assertEqual(get_school_code(lead), 'cg')
        self.assertEqual(get_region_from_lead(lead), 'EU')
        # Misma etiqueta de AC que cg-eu: mismas automatizaciones.
        self.assertEqual(FUNNEL_TAG_MAP['cg-eu-2'], FUNNEL_TAG_MAP['cg-eu'])

    def test_la_prellamada_es_suya(self):
        resp = self.client.post(
            reverse('funnels:resolver', kwargs={'slug': SLUG}),
            data=json.dumps({
                'final': False,
                'respuestas': {'name': 'Ana', 'email': 'ana@ejemplo.com', 'phone': '+34600111222'},
                'tracking': {'journey_id': 'jrn_legal2'},
            }),
            content_type='application/json',
        )
        self.assertEqual(resp.status_code, 200)
        p = Prellamada.objects.get(email='ana@ejemplo.com')
        self.assertEqual(p.funnel.key, 'LegalEu2')
