"""El HTML del funnel no lo puede cachear nadie.

Cuando conquerlanguages.com pasó a servirse desde Django, el navegador embebido
de TikTok siguió entregando durante horas la landing del proyecto viejo a parte
de los visitantes: mismo anuncio y misma URL, unos recibían la nueva y otros la
vieja, y los leads de esos últimos acababan en Make en vez de en el calendario.
La causa era que la respuesta no llevaba `Cache-Control`, así que cada caché
intermedia aplicaba su propia heurística y se quedaba con una copia.

Además cada respuesta lleva dentro `funnel-config` con el contenido y la
variante A/B de ESE visitante, así que tampoco debe compartirse entre usuarios.
"""
from django.test import TestCase
from django.urls import reverse

from calendario.funnels.models import FunnelForm


class FunnelSinCacheTest(TestCase):
    def setUp(self):
        self.funnel = FunnelForm.objects.create(
            key='FullLatamCache', slug='blocks-latam-cache', escuela='conquer-blocks',
            region='latam', nombre='Blocks LATAM (cache)',
            config={'blocks': [], 'q_order': [], 'score_ranges': []},
        )

    def _assert_sin_cache(self, resp, etapa):
        self.assertEqual(resp.status_code, 200, etapa)
        cache_control = resp.headers.get('Cache-Control', '')
        self.assertIn('no-store', cache_control, f'{etapa}: falta no-store ({cache_control!r})')
        self.assertIn('max-age=0', cache_control, etapa)

    def test_la_landing_no_se_cachea(self):
        url = reverse('clase_escuela', kwargs={'escuela': 'conquer-blocks', 'region': 'latam'})
        self._assert_sin_cache(self.client.get(url), 'landing')

    def test_la_pagina_de_video_no_se_cachea(self):
        url = reverse('video_escuela', kwargs={'escuela': 'conquer-blocks', 'region': 'latam'})
        self._assert_sin_cache(self.client.get(url), 'video')

    def test_el_stepform_no_se_cachea(self):
        url = reverse('funnel_agenda', kwargs={'producto': 'fullstack', 'region': 'latam'})
        self._assert_sin_cache(self.client.get(url), 'stepform')
