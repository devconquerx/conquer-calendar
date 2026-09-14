"""El push del registro a Respond.io: qué payload sale por el cable.

El fallo que cubre este fichero no se ve en los logs ni en el código: Respond.io
acepta con 200 un `customFields` en forma de diccionario y no escribe nada, así
que el registro llegaba con la academia, el vídeo y el país vacíos mientras el
push se daba por bueno. Solo se cae si el payload va como lista de
{name, value}, que es lo que espera la API (y lo que ya mandan los pushes de la
prellamada y de la reserva).
"""
from unittest.mock import patch

from django.test import TestCase, override_settings

from calendario.leads.models import Lead
from calendario.leads.services import respondio


@override_settings(RESPONDIO_API_KEY='test-key')
class PushLeadPayloadTest(TestCase):

    def _push(self, **kwargs):
        lead = Lead.objects.create(
            email='lead@ejemplo.com', full_name='Lead Ejemplo',
            lead_country='España', **kwargs,
        )
        with patch.object(respondio, '_ensure_contact', return_value=('email:lead@ejemplo.com', False)), \
             patch.object(respondio, 'requests') as mock_requests:
            respondio.push_lead(lead)
        cuerpo = mock_requests.put.call_args.kwargs['json']
        etiquetas = mock_requests.post.call_args.kwargs['json']
        return cuerpo, etiquetas

    def test_los_custom_fields_viajan_como_lista_de_name_value(self):
        cuerpo, _ = self._push(school='conquer-blocks', funnel='cb-eu')

        self.assertIn('custom_fields', cuerpo)
        self.assertIsInstance(cuerpo['custom_fields'], list)
        campos = {c['name']: c['value'] for c in cuerpo['custom_fields']}
        self.assertEqual(campos['nombre_academia'], 'Blocks')
        self.assertEqual(campos['enlace_video_clase'], 'https://video.conquerblocks.com/')
        self.assertEqual(campos['pais_lead'], 'España')

    def test_el_registro_de_conquer_ai_sale_con_su_marca_y_sus_etiquetas(self):
        cuerpo, etiquetas = self._push(school='conquer-ai', funnel='ai-eu')

        campos = {c['name']: c['value'] for c in cuerpo['custom_fields']}
        self.assertEqual(campos['nombre_academia'], 'AI')
        # El vídeo sigue siendo el de Blocks: comparten VSL.
        self.assertEqual(campos['enlace_video_clase'], 'https://video.conquerblocks.com/')
        self.assertIn('AI', etiquetas)
        self.assertIn('lead-AI', etiquetas)
        self.assertIn('EU', etiquetas)
        self.assertNotIn('CB', etiquetas)
