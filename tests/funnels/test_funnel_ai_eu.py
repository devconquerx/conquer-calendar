"""El funnel de Conquer AI EU: sus cuatro páginas y su identidad de marca.

Conquer AI es un clon del funnel de Conquer Blocks EU con URLs propias
(www.conquerblocks.com/conquer-ai/...). Como es una línea de Blocks y no una
marca nueva, hay dos cosas que tienen que cumplirse a la vez y que se rompen por
sitios distintos:

  1. Es INDEPENDIENTE: sus cuatro páginas responden en su propio prefijo y el
     funnel que sirven es el suyo (`ai-eu`), no el de Blocks EU.
  2. Es de BLOCKS: píxeles, contenedor de GTM, escuela del CRM y banner de
     consentimiento son los de Blocks. Un mapeo que falte aquí no rompe la
     página —sigue pintándose— pero deja los leads sin medición, que es
     precisamente el fallo que nadie ve hasta que cuadra los números.

La fila la crea la migración 0030 copiando el `config` de Conquer Blocks EU (y
0031 la renombra a su slug definitivo), así que estos tests también comprueban
que ese clonado ocurrió.
"""
import json

from django.test import TestCase
from django.urls import reverse

from calendario.funnels.models import FunnelForm
from calendario.leads.models import Lead

SLUG = 'ai-eu'
ESCUELA = 'conquer-ai'


class FunnelAiEuSembradoTest(TestCase):
    """La migración deja la fila creada y clonada de Conquer Blocks EU."""

    def test_existe_y_es_de_su_propia_escuela(self):
        funnel = FunnelForm.objects.get(key='FullAiEu')
        self.assertEqual(funnel.slug, SLUG)
        self.assertEqual(funnel.escuela, ESCUELA)
        self.assertEqual(funnel.region, 'eu')
        self.assertTrue(funnel.activo)

    def test_clona_el_contenido_de_blocks_eu(self):
        ai = FunnelForm.objects.get(key='FullAiEu')
        eu = FunnelForm.objects.get(key='FullEu')
        # Mismo formulario, mismo scoring y mismos tramos de score (o sea: los
        # mismos EventTypes, hasta que se le den los suyos desde el panel).
        self.assertEqual(ai.config['blocks'], eu.config['blocks'])
        self.assertEqual(ai.config['q_order'], eu.config['q_order'])
        self.assertEqual(ai.config['score_ranges'], eu.config['score_ranges'])
        # ...pero anunciándose como sí mismo: el `key` viaja dentro del JSON.
        self.assertEqual(ai.config['key'], 'FullAiEu')

    def test_no_le_roba_las_paginas_a_blocks_eu(self):
        """Blocks EU sigue sirviendo su propio funnel, no el de AI."""
        resp = self.client.get(reverse('clase_escuela', kwargs={
            'escuela': 'conquer-blocks', 'region': 'eu'}))
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.context['slug'], 'blocks-eu')


class FunnelAiEuPaginasTest(TestCase):
    """Las cuatro etapas responden en las URLs pedidas y sirven el funnel de AI."""

    def _get(self, url):
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200, url)
        self.assertEqual(resp.context['slug'], SLUG, url)
        self.assertEqual(resp.context['escuela'], ESCUELA, url)
        return resp

    def test_landing(self):
        resp = self._get('/conquer-ai/clase-online-gratuita-eu')
        self.assertEqual(resp.context['stage'], 'landing')

    def test_pagina_de_video(self):
        resp = self._get('/conquer-ai/video-clase-eu/')
        self.assertEqual(resp.context['stage'], 'video')

    def test_stepform(self):
        resp = self._get('/agenda/ai/eu/')
        self.assertEqual(resp.context['stage'], 'stepform')

    def test_confirmacion(self):
        resp = self._get('/conquer-ai/confirmacion-llamada-eu/')
        self.assertEqual(resp.context['stage'], 'confirmation')

    def test_las_urls_que_emite_encadenan_el_funnel_entero(self):
        """La SPA navega con estas URLs: si una apunta a Blocks, el visitante
        se cambia de funnel a mitad del recorrido."""
        resp = self.client.get('/conquer-ai/clase-online-gratuita-eu')
        self.assertEqual(resp.context['landing_url'], '/conquer-ai/clase-online-gratuita-eu/')
        self.assertEqual(resp.context['video_url'], '/conquer-ai/video-clase-eu/')
        self.assertEqual(resp.context['stepform_url'], '/agenda/ai/eu/')
        self.assertEqual(resp.context['confirmation_url'], '/conquer-ai/confirmacion-llamada-eu/')


class FunnelAiEuMarcaTest(TestCase):
    """Medición y consentimiento: los de Conquer Blocks."""

    def setUp(self):
        self.resp = self.client.get('/conquer-ai/clase-online-gratuita-eu')

    def test_usa_el_contenedor_de_gtm_de_blocks(self):
        self.assertEqual(self.resp.context['gtm']['id'], 'GTM-5PK5LTG')

    def test_usa_los_pixeles_de_blocks(self):
        self.assertEqual(self.resp.context['pixel_ids']['meta'], '921361326426436')

    def test_usa_el_banner_y_la_politica_de_blocks(self):
        consentimiento = self.resp.context['consentimiento']
        self.assertIn('conquerblocks.com', consentimiento['politica_url'])


class FunnelAiEuLeadTest(TestCase):
    """El lead entra con el slug del funnel y sale con el código del CRM."""

    def test_el_slug_viaja_al_crm_sin_traducir(self):
        resp = self.client.post(
            reverse('funnels:register_lead'),
            data=json.dumps({
                'email': 'ai@ejemplo.com', 'name': 'Lead AI',
                'escuela': ESCUELA, 'funnel': SLUG,
            }),
            content_type='application/json',
        )
        self.assertEqual(resp.status_code, 200)
        lead = Lead.objects.get()
        self.assertEqual(lead.funnel, 'ai-eu')
        self.assertEqual(lead.school, ESCUELA)

    def test_el_lead_cuenta_como_blocks_en_region_eu(self):
        """De este par salen el píxel, la cuenta de Ads y la lista de AC.

        La región importa más de lo que parece: si el funnel no la deja leer,
        `get_region_from_lead` cae a su fallback de LATAM y el lead europeo sale
        a Ads valorado a 1 € en vez de 10 € (y su reserva a 10 € en vez de
        100 €), se etiqueta LATAM en Respond.io y su % de VSL se escribe en el
        campo de otra región. No falla nada visible: solo salen mal los números.
        """
        from calendario.leads.services.utils import (
            get_conversion_value, get_region_from_lead, get_school_code,
        )

        lead = Lead.objects.create(email='ai@ejemplo.com', school=ESCUELA, funnel=SLUG)
        self.assertEqual(get_school_code(lead), 'cb')
        self.assertEqual(get_region_from_lead(lead), 'EU')
        self.assertEqual(get_conversion_value('EU', 'lead'), 10)

    def test_sin_escuela_la_deduce_del_propio_funnel(self):
        """'ai-eu' no empieza por ninguno de los códigos conocidos (cb/cf/cl/
        fi/cg), así que sin su rama propia un lead sin escuela se quedaría sin
        píxel, sin cuenta de Ads y sin lista — como le pasaba a 'legal-eu'."""
        from calendario.leads.services.utils import get_school_code

        lead = Lead.objects.create(email='ai2@ejemplo.com', school='', funnel=SLUG)
        self.assertEqual(get_school_code(lead), 'cb')

    def test_tiene_etiqueta_propia_en_activecampaign(self):
        """Comparte lista con Blocks, pero no etiqueta: si cayera en la de
        cb-eu, sus leads serían indistinguibles de los de Blocks EU."""
        from calendario.leads.services.activecampaign import FUNNEL_TAG_MAP

        self.assertIn(SLUG, FUNNEL_TAG_MAP)
        self.assertNotEqual(FUNNEL_TAG_MAP[SLUG], FUNNEL_TAG_MAP['cb-eu'])


class FunnelAiEuNombreAcademiaTest(TestCase):
    """El nombre con el que se anuncia en Respond.io.

    Es lo único que NO comparte con Blocks: las plantillas de WhatsApp dicen
    "Conquer {{nombre_academia}}", así que un lead de Conquer AI que llegue como
    "Blocks" se presenta con la marca equivocada. Etiquetas, closers, píxeles y
    vídeo siguen siendo los de cb.
    """

    def test_el_registro_se_anuncia_como_ai(self):
        from calendario.leads.services.utils import get_school_code, get_school_display_name

        lead = Lead.objects.create(email='ai3@ejemplo.com', school=ESCUELA, funnel=SLUG)
        self.assertEqual(
            get_school_display_name(get_school_code(lead), lead.school, lead.funnel),
            'AI',
        )

    def test_la_reserva_lo_deduce_de_la_key_del_formulario(self):
        """La reserva no lleva escuela: al CRM y a Respond.io viaja `FullAiEu`."""
        from calendario.leads.services.utils import get_school_display_name

        self.assertEqual(get_school_display_name('cb', '', 'FullAiEu'), 'AI')

    def test_blocks_sigue_diciendo_blocks(self):
        from calendario.leads.services.utils import get_school_display_name

        self.assertEqual(get_school_display_name('cb', 'conquer-blocks', 'cb-eu'), 'Blocks')
        self.assertEqual(get_school_display_name('cb', '', 'FullEu'), 'Blocks')
        # 'ai' suelto dentro de otro código no convierte el funnel en Conquer AI.
        self.assertEqual(get_school_display_name('cb', '', 'cb-trainingweek'), 'Blocks')


class FunnelAiEuEtiquetasTest(TestCase):
    """Las etiquetas de Respond.io también son suyas: 'AI', 'lead-AI',
    'preschedule-AI', 'schedule-AI'. Sus flujos de WhatsApp se separan así de los
    de Blocks, aunque el lead lo trabaje el mismo equipo."""

    def test_el_registro_se_etiqueta_como_ai(self):
        from calendario.leads.services.utils import get_school_code, get_school_tag_abbr

        lead = Lead.objects.create(email='ai4@ejemplo.com', school=ESCUELA, funnel=SLUG)
        self.assertEqual(get_school_tag_abbr(get_school_code(lead), lead.school, lead.funnel), 'AI')

    def test_la_reserva_lo_deduce_de_la_key_del_formulario(self):
        from calendario.leads.services.utils import get_school_tag_abbr

        self.assertEqual(get_school_tag_abbr('cb', '', 'FullAiEu'), 'AI')

    def test_la_prellamada_lo_deduce_de_la_escuela_del_funnel(self):
        from types import SimpleNamespace

        from calendario.funnels.respondio_preschedule import _school_abbr

        funnel = SimpleNamespace(escuela=ESCUELA, key='FullAiEu')
        self.assertEqual(_school_abbr(SimpleNamespace(funnel=funnel)), 'AI')

    def test_blocks_sigue_etiquetandose_como_cb(self):
        from types import SimpleNamespace

        from calendario.funnels.respondio_preschedule import _school_abbr
        from calendario.leads.services.utils import get_school_tag_abbr

        self.assertEqual(get_school_tag_abbr('cb', 'conquer-blocks', 'cb-eu'), 'CB')
        funnel = SimpleNamespace(escuela='conquer-blocks', key='FullEu')
        self.assertEqual(_school_abbr(SimpleNamespace(funnel=funnel)), 'CB')
