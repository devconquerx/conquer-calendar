"""
Qué hacemos cuando NeverBounce no contesta.

La distinción que prueba este módulo es la que costaba dinero en workers y ruido
en Sentry: un *read timeout* no es un fallo transitorio que merezca reintento,
es la respuesta de facto para dominios que no contestan a la verificación SMTP
(medido en producción: de las llamadas que pasan de 8s, el 99% acaban en
'unknown'). Se registra como 'unknown' y se sigue. Lo demás —conexión caída,
5xx, JSON ilegible— sí sube para que la tarea lo reintente.
"""
from unittest.mock import patch

import requests
from django.test import TestCase, override_settings

from calendario.leads.models import Lead
from calendario.leads.services import neverbounce


@override_settings(NEVERBOUNCE_API_KEY='clave-de-test')
class ValidateEmailTest(TestCase):

    def setUp(self):
        self.lead = Lead.objects.create(email='alguien@ejemplo.com')

    def test_timeout_se_registra_como_unknown_y_no_relanza(self):
        """El caso que generaba los 500 eventos semanales en Sentry."""
        with patch('requests.get', side_effect=requests.exceptions.ReadTimeout('read timeout')):
            neverbounce.validate_email(self.lead)  # no debe relanzar

        self.lead.refresh_from_db()
        self.assertEqual(self.lead.neverbounce_result['status'], 'timeout')
        self.assertEqual(self.lead.neverbounce_result['result'], 'unknown')
        self.assertTrue(self.lead.neverbounce_result['is_uncertain'])
        self.assertFalse(self.lead.neverbounce_result['is_valid'])
        # Dejar el campo relleno es lo que evita que el CRM revalide por su
        # cuenta en un post_save síncrono.
        self.assertIsNotNone(self.lead.neverbounce_result)

    def test_fallo_transitorio_sube_para_que_la_tarea_reintente(self):
        with patch('requests.get', side_effect=requests.exceptions.ConnectionError('boom')):
            with self.assertRaises(requests.exceptions.ConnectionError):
                neverbounce.validate_email(self.lead)

        self.lead.refresh_from_db()
        self.assertIsNone(self.lead.neverbounce_result)

    def test_respuesta_buena_se_guarda(self):
        class RespuestaFalsa:
            @staticmethod
            def json():
                return {'status': 'success', 'result': 'valid', 'flags': ['has_dns']}

        with patch('requests.get', return_value=RespuestaFalsa()):
            neverbounce.validate_email(self.lead)

        self.lead.refresh_from_db()
        self.assertEqual(self.lead.neverbounce_result['result'], 'valid')
        self.assertTrue(self.lead.neverbounce_result['is_valid'])
        self.assertFalse(self.lead.neverbounce_result['is_uncertain'])

    def test_sin_api_key_no_toca_nada(self):
        with override_settings(NEVERBOUNCE_API_KEY=''):
            with patch('requests.get') as get:
                neverbounce.validate_email(self.lead)
                get.assert_not_called()

        self.lead.refresh_from_db()
        self.assertIsNone(self.lead.neverbounce_result)


@override_settings(NEVERBOUNCE_API_KEY='clave-de-test')
class ProcessNeverbounceTaskTest(TestCase):
    """La tarea completa: un timeout no debe dejar el lead sin procesar."""

    def test_timeout_marca_done_y_sigue_al_crm(self):
        from calendario.leads.tasks import process_neverbounce

        lead = Lead.objects.create(email='otro@ejemplo.com')
        with patch('requests.get', side_effect=requests.exceptions.ReadTimeout('read timeout')), \
                patch('calendario.leads.tasks.process_crm_send.delay') as crm:
            process_neverbounce.apply(args=[lead.pk]).get()

        lead.refresh_from_db()
        tags = set(lead.tags.names())
        # 'done' y no 'skipped': sí preguntamos, y la falta de respuesta quedó
        # registrada. Así el sweep tampoco vuelve a encolarlo.
        self.assertIn('neverbounce_done', tags)
        self.assertNotIn('neverbounce_skipped', tags)
        crm.assert_called_once_with(lead.pk)
