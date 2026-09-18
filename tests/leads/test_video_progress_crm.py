"""
Quién paga la espera cuando el CRM no contesta (FUNNELS-5C).

`/f/api/video-progress/` recibe un ping cada 10% de vídeo y, al cruzar un hito,
reenvía el progreso al CRM. Ese reenvío salía con `requests.patch` DENTRO del
request, con un timeout de 10 segundos, mientras sus dos vecinos de la misma
vista —el respaldo en Supabase y el % a ActiveCampaign— van por Celery.

Eso convierte un dato que a nadie le urge en tiempo de servidor: 121 read
timeouts en siete días, y cada uno inmoviliza uno de los tres workers de
gunicorn durante diez segundos. En promedio se diluye; el problema es que estos
fallos llegan a la vez —cuando el CRM se cae, se cae para todo el mundo— y ahí
los tres workers pueden acabar esperando juntos a un servicio que no responde,
con el calendario entero sin contestar.

El test mide lo único que hace falta medir: si el CRM tarda, ¿tarda también la
respuesta al visitante? La espera simulada es de un segundo en vez de diez
—demuestra lo mismo sin un test lento— y el margen se toma con holgura para que
no dependa de lo cargada que esté la máquina.
"""
import time
from unittest.mock import patch

import requests
from django.test import TestCase, override_settings

from calendario.leads.models import Lead


ESPERA_DEL_CRM = 1.0


def _crm_lento(*args, **kwargs):
    """Un CRM que tarda y acaba en nada, como los read timeout de producción."""
    time.sleep(ESPERA_DEL_CRM)
    raise requests.exceptions.ReadTimeout('read timeout')


@override_settings(CRM_API_KEY='clave-de-test', CRM_BASE_URL='https://crm.ejemplo.com')
class VideoProgressNoEsperaAlCrmTest(TestCase):

    def setUp(self):
        self.lead = Lead.objects.create(email='alguien@ejemplo.com')

    def _pong(self, percent=25, school='conquer-blocks'):
        return self.client.post(
            '/f/api/video-progress/',
            data={'email': self.lead.email, 'percent': percent,
                  'school': school, 'region': 'latam'},
            content_type='application/json',
        )

    def test_la_respuesta_no_espera_al_crm(self):
        """El caso de FUNNELS-5C: el visitante y el worker, parados por un PATCH."""
        with patch('requests.patch', side_effect=_crm_lento), \
                patch('calendario.leads.tasks.process_supabase.delay'), \
                patch('calendario.leads.tasks.process_vsl_activecampaign.delay'), \
                patch('calendario.leads.tasks.process_vsl_crm.delay') as encolado:
            empezado = time.monotonic()
            respuesta = self._pong()
            tardado = time.monotonic() - empezado

        self.assertEqual(respuesta.status_code, 200)
        self.assertLess(
            tardado, ESPERA_DEL_CRM,
            'la vista se queda esperando al CRM: con el timeout real de 10s, '
            'eso es un worker de gunicorn inmovilizado diez segundos por ping',
        )
        # Y el dato no se pierde por el camino: queda encolado con lo mismo que
        # antes se mandaba a mano.
        encolado.assert_called_once_with('alguien@ejemplo.com', 'vsl_percent_cb', 25)

    def test_el_progreso_se_guarda_aunque_el_crm_no_conteste(self):
        """Lo que importa del ping es el dato local; el CRM es un extra."""
        with patch('requests.patch', side_effect=_crm_lento), \
                patch('calendario.leads.tasks.process_supabase.delay'), \
                patch('calendario.leads.tasks.process_vsl_activecampaign.delay'), \
                patch('calendario.leads.tasks.process_vsl_crm.delay'):
            self._pong(percent=50)

        self.lead.refresh_from_db()
        self.assertEqual(self.lead.vsl_percentage, 50)
        self.assertEqual(self.lead.vsl_percent_cb, 50)
