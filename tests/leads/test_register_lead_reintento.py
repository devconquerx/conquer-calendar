"""
El frontend reintenta el registro del lead si la red falla (FUNNELS-D2). Si el
primer intento sí llegó y solo se perdió la respuesta, el reintento no puede
crear un segundo Lead.
"""
import json
from unittest.mock import patch

from django.test import TestCase

from calendario.leads.models import Lead


def _post(client, **extra):
    cuerpo = {'name': 'Ana', 'email': 'ana@ejemplo.com', 'funnel': 'cb-latam',
              'journey_id': 'j-1', 'event_id': 'e-1', **extra}
    with patch('celery.app.task.Task.apply_async'):
        return client.post('/f/api/lead/', data=json.dumps(cuerpo), content_type='application/json')


class RegisterLeadReintentoTest(TestCase):

    def test_el_reintento_del_mismo_envio_devuelve_el_mismo_lead(self):
        primero = _post(self.client).json()
        segundo = _post(self.client).json()

        self.assertEqual(Lead.objects.count(), 1)
        self.assertEqual(primero['id'], segundo['id'])

    def test_otro_evento_del_mismo_visitante_es_otro_lead(self):
        _post(self.client)
        _post(self.client, event_id='e-2')

        self.assertEqual(Lead.objects.count(), 2)

    def test_otro_correo_en_el_mismo_evento_es_otro_lead(self):
        _post(self.client)
        _post(self.client, email='otra@ejemplo.com')

        self.assertEqual(Lead.objects.count(), 2)
