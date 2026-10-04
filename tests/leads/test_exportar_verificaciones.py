"""El volcado de verificaciones que hereda Relay antes de borrarlas del calendario.

Los datos se meten por SQL: el modelo ya no los conoce, pero la tabla y la
columna siguen en la BD hasta la migración que las borra.
"""
import json
import os
import tempfile
from io import StringIO
from unittest.mock import patch

from django.core.management import call_command
from django.db import connection
from django.test import TestCase

from calendario.leads.models import Lead


class ExportarVerificacionesTest(TestCase):

    def setUp(self):
        with patch('celery.app.task.Task.apply_async'):
            self.viejo = Lead.objects.create(email='Viejo@Ejemplo.com')
            self.propio = Lead.objects.create(email='nuevo@ejemplo.com')
            Lead.objects.create(email='sin@veredicto.com')
        with connection.cursor() as cur:
            cur.execute(
                "INSERT INTO email_verification_cache (created, modified, email, result, reason, "
                "smtp_code, smtp_message, expires_at, hit_count) VALUES (now(), now(), "
                "'malo@ejemplo.com', 'invalid', 'smtp_user_unknown', 550, 'no such user', "
                "now() + interval '180 days', 3)"
            )
            cur.execute('UPDATE leads SET neverbounce_result = %s WHERE id = %s', [json.dumps({
                'status': 'success', 'result': 'valid', 'is_valid': True,
                'flags': ['has_dns'], 'execution_time': 120,
            }), self.viejo.pk])
            cur.execute('UPDATE leads SET neverbounce_result = %s WHERE id = %s', [json.dumps({
                'status': 'success', 'result': 'catchall', 'source': 'own_smtp',
                'reason': 'catchall_domain', 'flags': [], 'smtp_code': 250,
            }), self.propio.pk])

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
        self.assertEqual(cache['extra']['hit_count'], 3)
        self.assertTrue(cache['fecha'])

        viejo = por_email['viejo@ejemplo.com']  # en minúsculas
        self.assertEqual(viejo['origen'], 'lead')
        self.assertEqual(viejo['source'], 'neverbounce')  # sin `source` = NeverBounce
        self.assertEqual(viejo['flags'], ['has_dns'])
        self.assertEqual(viejo['extra']['lead_id'], self.viejo.pk)

        propio = por_email['nuevo@ejemplo.com']
        self.assertEqual(propio['source'], 'own_smtp')
        self.assertEqual(propio['reason'], 'catchall_domain')

    def test_solo_un_origen(self):
        self.assertEqual({f['origen'] for f in self._exportar(solo='cache')}, {'cache'})
        self.assertEqual({f['origen'] for f in self._exportar(solo='leads')}, {'lead'})
