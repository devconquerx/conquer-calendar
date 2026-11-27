"""
Los leads de LATAM de un closer sin setter confirman la llamada por WhatsApp.

La lista de closers sin setter es la del CRM (Closers para autosetter); la
reserva devuelve `confirmar_whatsapp` y el front enseña esa página en vez de la
confirmación de siempre.
"""
import json
from unittest.mock import MagicMock, patch

import requests
from django.core.cache import cache
from django.test import TestCase, override_settings
from django.urls import reverse

from calendario.funnels import autosetter
from calendario.funnels.models import FunnelForm, Prellamada
from tests.factories import crear_disponibilidad, crear_event_type, crear_host, slot_futuro

CACHES_TEST = {'default': {'BACKEND': 'django.core.cache.backends.locmem.LocMemCache'}}


def _respuesta_crm(emails):
    response = MagicMock()
    response.json.return_value = {'emails': emails}
    response.raise_for_status.return_value = None
    return response


@override_settings(CACHES=CACHES_TEST, CRM_API_KEY='clave', CRM_BASE_URL='https://crm.test')
class EmailsSinSetterTest(TestCase):

    def setUp(self):
        cache.clear()

    @patch('calendario.funnels.autosetter.requests.get')
    def test_pide_la_lista_al_crm_y_la_guarda_en_cache(self, get):
        get.return_value = _respuesta_crm(['Closer@ConquerX.com'])

        self.assertEqual(autosetter.emails_sin_setter(), {'closer@conquerx.com'})
        self.assertEqual(autosetter.emails_sin_setter(), {'closer@conquerx.com'})

        get.assert_called_once()
        self.assertEqual(get.call_args.args[0], 'https://crm.test/api/v1/ingest/autosetter-closers/')
        self.assertEqual(get.call_args.kwargs['headers'], {'X-API-Key': 'clave'})

    @patch('calendario.funnels.autosetter.requests.get')
    def test_si_el_crm_falla_usa_la_ultima_lista_buena(self, get):
        get.return_value = _respuesta_crm(['closer@conquerx.com'])
        autosetter.emails_sin_setter()
        cache.delete(autosetter.CACHE_KEY)  # caduca la caché corta

        get.side_effect = requests.ConnectionError('caído')
        self.assertEqual(autosetter.emails_sin_setter(), {'closer@conquerx.com'})

    @patch('calendario.funnels.autosetter.requests.get', side_effect=requests.Timeout('lento'))
    def test_sin_lista_nadie_confirma_por_whatsapp(self, _get):
        self.assertEqual(autosetter.emails_sin_setter(), set())

    @override_settings(CRM_API_KEY='')
    @patch('calendario.funnels.autosetter.requests.get')
    def test_sin_api_key_no_llama_al_crm(self, get):
        self.assertEqual(autosetter.emails_sin_setter(), set())
        get.assert_not_called()


@override_settings(CACHES=CACHES_TEST)
class ReservarConfirmarWhatsappTest(TestCase):

    def setUp(self):
        cache.clear()
        self.host = crear_host()
        self.et = crear_event_type(self.host)
        for dia in range(5):
            crear_disponibilidad(self.host, dia=dia)
        self.inicio = slot_futuro()

    def _reservar(self, region):
        funnel = FunnelForm.objects.create(
            key=f'Test{region}', slug=f'test-blocks-{region}', escuela='conquer-blocks',
            region=region, nombre='Funnel de test', config={},
        )
        prellamada = Prellamada.objects.create(
            funnel=funnel, nombre='Ana', email='ana@example.com',
            resultado=Prellamada.Resultado.CALENDARIO, event_type=self.et,
        )
        with patch('calendario.funnels.views._avisar_si_es_nueva'), \
             patch('calendario.bookings.services.hay_conflicto_calendario', return_value=False), \
             patch('calendario.bookings.services.crear_evento_google'):
            response = self.client.post(
                reverse('funnels:reservar', kwargs={'slug': funnel.slug}),
                content_type='application/json',
                data=json.dumps({
                    'prellamada_token': str(prellamada.token),
                    'inicio_utc': self.inicio.isoformat(),
                    'tz': 'America/Bogota',
                    'nombre': 'Ana', 'email': 'ana@example.com', 'telefono': '+573001112233',
                }),
            )
        self.assertEqual(response.status_code, 200)
        return response.json()

    def test_latam_con_closer_sin_setter(self):
        with patch.object(autosetter, 'emails_sin_setter', return_value={self.host.email.lower()}):
            self.assertTrue(self._reservar('latam')['confirmar_whatsapp'])

    def test_latam_con_closer_con_setter(self):
        with patch.object(autosetter, 'emails_sin_setter', return_value={'otro@conquerx.com'}):
            self.assertFalse(self._reservar('latam')['confirmar_whatsapp'])

    def test_eu_nunca(self):
        with patch.object(autosetter, 'emails_sin_setter', return_value={self.host.email.lower()}) as lista:
            self.assertFalse(self._reservar('eu')['confirmar_whatsapp'])
        lista.assert_not_called()
