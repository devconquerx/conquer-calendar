# -*- coding: utf-8 -*-
"""Los leads de evento (lanzamiento) van SOLO al CRM.

No es una decisión de diseño nueva, es lo que hacía el escenario de Make: sus
ramas de correo, Respond.io y CAPI están apagadas, y se comprueba en el log de
ejecuciones —un evento de Blocks consume 2 operaciones (webhook + CRM) y uno de
Languages con teléfono 3 (webhook + CRM + FunnelChat)—. Si salieran correos o
Respond.io habría 5 o más, y no hay ninguna ejecución por encima de 4 en
150.969 registros.

Tampoco pasan por NeverBounce: Make postea directo al ingest y valida el CRM.
"""
import json
import re
from unittest.mock import patch

from django.test import TestCase
from django.urls import reverse

from calendario.leads.models import Lead
from calendario.funnels.evento_views import EVENTOS
from calendario.leads.tasks import es_lead_de_lanzamiento

RUTA = 'calendario.leads.tasks.'
SERVICIOS = ('process_supabase', 'process_meta_capi', 'process_tiktok_events',
             'process_google_ads', 'process_respondio', 'process_activecampaign',
             'process_neverbounce', 'process_funnelchat')


class DetectaLanzamientoTest(TestCase):
    def test_reconoce_los_codigos_de_edicion(self):
        for codigo in ('cb-lanzamiento11', 'cl-lanzamiento8', 'cf-lanzamiento9', 'CB-Lanzamiento12'):
            self.assertTrue(es_lead_de_lanzamiento(Lead(funnel=codigo)), codigo)

    def test_no_confunde_los_funnels_normales(self):
        for codigo in ('cb-eu', 'cl-latam', 'fi-us', 'cb-eu-2', '', None):
            self.assertFalse(es_lead_de_lanzamiento(Lead(funnel=codigo)), repr(codigo))


class DespachoDeLanzamientoTest(TestCase):
    """El alta de un lead dispara las tareas por signal, así que se crea el Lead
    de verdad y se comprueba qué se encoló."""

    def _crear(self, funnel):
        parches = {n: patch(RUTA + n) for n in SERVICIOS}
        parches['process_crm_send'] = patch(RUTA + 'process_crm_send')
        activos = {n: p.start() for n, p in parches.items()}
        try:
            Lead.objects.create(email='lead@ejemplo.com', full_name='Ana', funnel=funnel)
            return {n: m.delay.called for n, m in activos.items()}
        finally:
            for p in parches.values():
                p.stop()

    def test_el_de_evento_solo_va_al_crm(self):
        llamadas = self._crear('cb-lanzamiento11')
        self.assertTrue(llamadas['process_crm_send'], 'el CRM debe recibirlo')
        for servicio in SERVICIOS:
            self.assertFalse(llamadas[servicio], f'{servicio} no debería dispararse')

    def test_el_del_funnel_sigue_disparando_todo(self):
        llamadas = self._crear('cb-eu')
        self.assertTrue(llamadas['process_supabase'])
        self.assertTrue(llamadas['process_respondio'])
        self.assertTrue(llamadas['process_neverbounce'])
        # El CRM le llega encadenado desde NeverBounce, no directo.
        self.assertFalse(llamadas['process_crm_send'])


class AltaDesdeLaPantallaDeEventoTest(TestCase):
    """El formulario del evento postea al mismo endpoint que el resto de leads."""

    def test_guarda_el_lead_con_el_codigo_de_la_edicion(self):
        cuerpo = {
            'name': 'Ana Pérez', 'email': 'ana@ejemplo.com',
            'lead_phone': '600111222', 'lead_phone_prefix': '+34',
            'lead_country': 'España', 'funnel': 'cb-lanzamiento11',
            'url': 'https://www.conquerblocks.com/evento/evento-online?utm_source=ActiveCampaign',
            'utm_source': 'ActiveCampaign', 'utm_campaign': 'cb-lanzamiento11',
        }
        with patch(RUTA + 'process_crm_send') as crm:
            resp = self.client.post(reverse('funnels:register_lead'),
                                    data=json.dumps(cuerpo), content_type='application/json')
        self.assertEqual(resp.status_code, 200)
        lead = Lead.objects.get()
        self.assertEqual(lead.funnel, 'cb-lanzamiento11')
        self.assertEqual(lead.full_name, 'Ana Pérez')
        self.assertEqual(lead.lead_phone_prefix, '+34')
        self.assertEqual(lead.utm_campaign, 'cb-lanzamiento11')
        self.assertTrue(crm.delay.called)


class CodigoDeEdicionEnLaPantallaTest(TestCase):
    """La edición viaja en la campaña, como en Webflow.

    `getFunnelValue()` de la página de Webflow copiaba `utm_campaign` en el
    campo `funnel` al enviar; por eso en el CRM conviven `cf-lanzamiento10` y
    `cf-lanzamiento11` sin orden cronológico. Si aquí se quedara fijo el código
    del código fuente, cada lanzamiento nuevo se archivaría bajo la edición
    anterior hasta que alguien se acordara de desplegar.
    """

    def _funnel_renderizado(self, query):
        resp = self.client.get('/evento/evento-online' + query,
                               HTTP_HOST='www.conquerblocks.com')
        self.assertEqual(resp.status_code, 200)
        html = resp.content.decode()
        marca = 'window.__EVENTO__ = { funnel: "'
        inicio = html.index(marca) + len(marca)
        crudo = html[inicio:html.index('"', inicio)]
        # `escapejs` escapa hasta los guiones (`cb\\u002Dlanzamiento11`).
        return re.sub(r'\\u([0-9a-fA-F]{4})', lambda m: chr(int(m.group(1), 16)), crudo)

    def test_la_campana_manda_sobre_el_codigo_del_codigo_fuente(self):
        self.assertEqual(
            self._funnel_renderizado('?utm_campaign=cb-lanzamiento12'),
            'cb-lanzamiento12')

    def test_sin_campana_cae_al_codigo_configurado(self):
        # Webflow mandaba el campo vacío; un `funnel` vacío no pasa por
        # `es_lead_de_lanzamiento` y el lead se iría por el pipeline completo.
        self.assertEqual(self._funnel_renderizado(''), EVENTOS['conquer-blocks']['funnel'])

    def test_una_campana_que_no_es_de_lanzamiento_no_secuestra_el_codigo(self):
        obtenido = self._funnel_renderizado('?utm_campaign=black-friday')
        self.assertEqual(obtenido, EVENTOS['conquer-blocks']['funnel'])
        self.assertTrue(es_lead_de_lanzamiento(Lead(funnel=obtenido)))
