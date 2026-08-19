"""
Cadena de la variante A/B en el backend.

Dos caminos distintos y deliberados:
  - La variante de la LANDING viaja en el Lead (`utm_form_variant` del intake).
  - La variante de la PÁGINA DE VÍDEO viaja en la PRELLAMADA, dentro de
    `tracking`, y de ahí a `PreSchedule.utm_form_variant` del CRM.

Se prueban por separado porque el negocio los lee por separado, y porque el
frontend puede mandar los dos a la vez sin que uno pise al otro.
"""
import json
from unittest.mock import patch

from django.test import TestCase
from django.urls import reverse

from calendario.funnels.models import FunnelForm, Prellamada
from calendario.leads.models import Lead


class VarianteEnLaPrellamadaTest(TestCase):
    """La variante del vídeo llega en `tracking` y se guarda como columna."""

    def setUp(self):
        self.funnel = FunnelForm.objects.create(
            key='FullLatamTest', slug='blocks-latam-test', escuela='conquer-blocks',
            region='latam', nombre='Blocks LATAM (test)',
            config={'blocks': [], 'q_order': [], 'score_ranges': []},
        )
        self.url = reverse('funnels:resolver', kwargs={'slug': self.funnel.slug})

    def _post(self, tracking, final=False):
        cuerpo = {
            'respuestas': {'name': 'Lead', 'email': 'lead@ejemplo.com', 'phone': '+34600111222'},
            'tracking': tracking,
            'final': final,
        }
        return self.client.post(self.url, data=json.dumps(cuerpo), content_type='application/json')

    def test_guarda_la_variante_como_columna_de_la_prellamada(self):
        resp = self._post({'journey_id': 'jrn-1', 'uuid': '11111111-1111-4111-8111-111111111111',
                           'utm_form_variant': '4', 'utm_source': 'meta'})
        self.assertEqual(resp.status_code, 200)
        prellamada = Prellamada.objects.get()
        self.assertEqual(prellamada.utm_form_variant, '4')
        self.assertEqual(prellamada.utm_source, 'meta')

    def test_sin_variante_la_columna_queda_vacia_y_no_falla(self):
        """Es el caso de quien entra por link directo sin pasar por el vídeo."""
        self.assertEqual(self._post({'journey_id': 'jrn-2'}).status_code, 200)
        self.assertEqual(Prellamada.objects.get().utm_form_variant, '')

    def test_los_envios_progresivos_convergen_en_una_sola_prellamada(self):
        """El StepForm manda un pre-schedule por pregunta: mismo uuid, misma fila."""
        uuid = '22222222-2222-4222-8222-222222222222'
        for _ in range(3):
            self._post({'journey_id': 'jrn-3', 'uuid': uuid, 'utm_form_variant': '4'})
        self.assertEqual(Prellamada.objects.count(), 1)
        self.assertEqual(Prellamada.objects.get().utm_form_variant, '4')

    def test_la_variante_viaja_en_el_payload_que_se_manda_al_crm(self):
        from calendario.funnels.crm_preschedule import push_pre_schedule

        self._post({'journey_id': 'jrn-4', 'uuid': '33333333-3333-4333-8333-333333333333',
                    'utm_form_variant': '10'})
        prellamada = Prellamada.objects.get()

        with self.settings(CRM_API_KEY='clave-de-test'):
            with patch('calendario.funnels.crm_preschedule.requests.post') as post:
                post.return_value.status_code = 200
                push_pre_schedule(prellamada)

        self.assertTrue(post.called, 'no se llamó al ingest del CRM')
        enviado = post.call_args.kwargs.get('json') or post.call_args[1]['json']
        self.assertEqual(enviado['utm_form_variant'], '10')


class VarianteEnElLeadTest(TestCase):
    """La variante de la landing viaja en el Lead, no en la prellamada."""

    def setUp(self):
        self.url = reverse('funnels:register_lead')

    def _registrar(self, **extra):
        cuerpo = {'email': 'lead@ejemplo.com', 'full_name': 'Lead', 'funnel': 'blocks-latam',
                  'escuela': 'conquer-blocks', 'journey_id': 'jrn-lead', **extra}
        # El Lead dispara sus tareas por un signal post_save (ActiveCampaign,
        # respond.io, CRM, ads). Se parchea en el origen para que un test NUNCA
        # llame a un servicio externo.
        with patch('calendario.leads.tasks.dispatch_lead_tasks') as dispatch:
            resp = self.client.post(self.url, data=json.dumps(cuerpo), content_type='application/json')
        self.dispatch = dispatch
        return resp

    def test_guarda_utm_form_variant(self):
        self.assertIn(self._registrar(utm_form_variant='58').status_code, (200, 201))
        self.assertEqual(Lead.objects.get().utm_form_variant, '58')

    def test_ningun_servicio_externo_se_llama_desde_un_test(self):
        self._registrar(utm_form_variant='58')
        self.assertTrue(self.dispatch.called, 'el signal dejó de encolar las tareas del lead')

    def test_sin_variante_no_falla(self):
        self.assertIn(self._registrar().status_code, (200, 201))
        self.assertFalse(Lead.objects.get().utm_form_variant)

    def test_traduce_el_slug_al_codigo_que_indexa_el_crm(self):
        """El CRM indexa por códigos legacy (cb-latam), no por slug."""
        self._registrar(utm_form_variant='58')
        self.assertEqual(Lead.objects.get().funnel, 'cb-latam')
