"""El volcado de verificaciones que hereda Relay antes de borrarlas del calendario."""
import json
import os
import tempfile
from datetime import timedelta
from io import StringIO
from unittest.mock import patch

from django.core.management import call_command
from django.test import TestCase
from django.utils import timezone

from calendario.leads.models import EmailVerificationCache, Lead


class ExportarVerificacionesTest(TestCase):

    def setUp(self):
        EmailVerificationCache.objects.create(
            email='malo@ejemplo.com', result='invalid', reason='smtp_user_unknown',
            smtp_code=550, smtp_message='no such user',
            expires_at=timezone.now() + timedelta(days=180),
        )
        with patch('celery.app.task.Task.apply_async'):
            self.nb = Lead.objects.create(email='Viejo@Ejemplo.com', neverbounce_result={
                'status': 'success', 'result': 'valid', 'is_valid': True,
                'is_rejected': False, 'flags': ['has_dns'], 'execution_time': 120,
            })
            self.propio = Lead.objects.create(email='nuevo@ejemplo.com', neverbounce_result={
                'status': 'success', 'result': 'catchall', 'source': 'own_smtp',
                'reason': 'catchall_domain', 'flags': [], 'smtp_code': 250,
            })
            Lead.objects.create(email='sin@veredicto.com')

    def _exportar(self, **opts):
        with tempfile.TemporaryDirectory() as tmp:
            ruta = os.path.join(tmp, 'v.jsonl')
            call_command('exportar_verificaciones', salida=ruta, stderr=StringIO(), **opts)
            with open(ruta, encoding='utf-8') as fh:
                return [json.loads(linea) for linea in fh]

    def test_vuelca_la_cache_y_los_veredictos_de_los_leads(self):
        filas = self._exportar()
        self.assertEqual(len(filas), 3)
        por_email = {f['email']: f for f in filas}

        cache = por_email['malo@ejemplo.com']
        self.assertEqual(cache['origen'], 'cache')
        self.assertEqual(cache['result'], 'invalid')
        self.assertEqual(cache['reason'], 'smtp_user_unknown')
        self.assertEqual(cache['source'], 'own_smtp')
        self.assertEqual(cache['extra']['smtp_code'], 550)
        self.assertTrue(cache['fecha'])

        viejo = por_email['viejo@ejemplo.com']  # en minúsculas
        self.assertEqual(viejo['origen'], 'lead')
        self.assertEqual(viejo['source'], 'neverbounce')  # sin `source` = NeverBounce
        self.assertEqual(viejo['flags'], ['has_dns'])
        self.assertEqual(viejo['extra']['lead_id'], self.nb.pk)

        propio = por_email['nuevo@ejemplo.com']
        self.assertEqual(propio['source'], 'own_smtp')
        self.assertEqual(propio['reason'], 'catchall_domain')

    def test_solo_un_origen(self):
        self.assertEqual({f['origen'] for f in self._exportar(solo='cache')}, {'cache'})
        self.assertEqual({f['origen'] for f in self._exportar(solo='leads')}, {'lead'})
