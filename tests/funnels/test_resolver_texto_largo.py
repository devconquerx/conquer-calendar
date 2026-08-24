"""
El resolver no puede caerse porque alguien escriba de más.

Caso real (FUNNELS-88): un visitante escribió 255 caracteres en la casilla del
nombre —una queja al anuncio, no un nombre—. Cabe en `Lead.full_name` (255)
pero no en `Prellamada.nombre` (160), así que Postgres rechazaba el INSERT y el
resolver devolvía 500. Y como el StepForm llama al resolver una vez por
pregunta, esa sola persona generó 74 errores y se quedó atascada.

Hermano de tests/funnels/test_tracking_largo.py: mismo fallo, otra tabla.
"""
import json

from django.test import TestCase
from django.urls import reverse

from calendario.funnels.models import FunnelForm, Prellamada

# Literal del lead 22789 de producción, recortado a lo publicable.
QUEJA = (
    'Eres un imbecil y un gilipollas por hacerme perder el tiempo en tu estupido '
    'anuncio en vez de decirme de que puta profesion se trata y ahora estas pagando '
    'por clicks que no convierten porque la gente se harta de tanto misterio'
)


class ResolverTextoLargoTest(TestCase):

    def setUp(self):
        self.funnel = FunnelForm.objects.create(
            key='TestBlocksEu', slug='test-blocks-eu', escuela='conquer-blocks',
            region='eu', nombre='Funnel de test', config={},
        )
        self.url = reverse('funnels:resolver', kwargs={'slug': self.funnel.slug})

    def _post(self, nombre='Ana', tracking=None):
        """`final=False` es la llamada intermedia, una por pregunta contestada:
        es la que fallaba en producción (74 veces para un solo visitante)."""
        cuerpo = {
            'final': False,
            'respuestas': {'name': nombre, 'email': 'ana@ejemplo.com', 'phone': '+34600111222'},
            'tracking': {'journey_id': 'jrn_1', **(tracking or {})},
        }
        return self.client.post(self.url, data=json.dumps(cuerpo), content_type='application/json')

    def test_un_nombre_de_255_caracteres_no_tumba_el_resolver(self):
        self.assertGreater(len(QUEJA), 160)

        resp = self._post(nombre=QUEJA)

        self.assertEqual(resp.status_code, 200)
        p = Prellamada.objects.get(email='ana@ejemplo.com')
        self.assertEqual(len(p.nombre), 160)
        self.assertTrue(QUEJA.startswith(p.nombre))

    def test_un_utm_desmedido_tampoco(self):
        resp = self._post(tracking={
            'utm_content': 'Ads_2025_04_ESP_Bienve_Evergreen_' * 20,   # 660 > 255
            'utm_term': 'Open_Bienvenido_EU_TT_' * 30,
            'event_id': '1787511185450_akkcip',
        })

        self.assertEqual(resp.status_code, 200)
        p = Prellamada.objects.get(email='ana@ejemplo.com')
        self.assertEqual(len(p.utm_content), 255)
        self.assertEqual(len(p.utm_term), 255)
        self.assertEqual(p.event_id, '1787511185450_akkcip')

    def test_lo_que_cabe_se_guarda_intacto(self):
        resp = self._post(nombre='Ana María', tracking={'utm_source': 'TikTokAds'})

        self.assertEqual(resp.status_code, 200)
        p = Prellamada.objects.get(email='ana@ejemplo.com')
        self.assertEqual(p.nombre, 'Ana María')
        self.assertEqual(p.utm_source, 'TikTokAds')
