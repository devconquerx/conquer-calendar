"""
Un intento fallido contra un servicio caído no es un error en Sentry: la tarea
lo reintenta 24 h y, si al final lo da por perdido, avisa el fallo de la tarea.
Antes un corte de 2 minutos del CRM eran cientos de issues (FUNNELS-7T/6A/C).
"""
import logging
from unittest.mock import Mock, patch

import requests
from django.test import SimpleTestCase, override_settings

from calendario.core.resiliencia import nivel_de_fallo
from calendario.leads.services import crm


def _http_error(status):
    return requests.HTTPError(response=Mock(status_code=status))


class NivelDeFalloTest(SimpleTestCase):

    def test_lo_que_se_reintenta_es_warning(self):
        for caso in (dict(status=502), dict(status=429), dict(exc=requests.ReadTimeout()),
                     dict(exc=requests.ConnectionError()), dict(exc=_http_error(503))):
            with self.subTest(**{k: repr(v) for k, v in caso.items()}):
                self.assertEqual(nivel_de_fallo(**caso), logging.WARNING)

    def test_lo_que_es_nuestro_es_error(self):
        for caso in (dict(status=400), dict(status=404), dict(exc=_http_error(400)),
                     dict(exc=ValueError('dato raro')), dict()):
            with self.subTest(**{k: repr(v) for k, v in caso.items()}):
                self.assertEqual(nivel_de_fallo(**caso), logging.ERROR)


@override_settings(CRM_API_KEY='k', CRM_BASE_URL='https://crm.test')
class VslProgressReintentoTest(SimpleTestCase):
    """FUNNELS-5C/C: el PATCH se tragaba el fallo y el hito se perdía."""

    def test_un_5xx_lanza_para_que_la_tarea_reintente(self):
        resp = Mock(status_code=502, text='<html>')
        resp.raise_for_status.side_effect = _http_error(502)
        with patch('requests.patch', return_value=resp):
            with self.assertRaises(requests.HTTPError):
                crm.push_vsl_progress('a@b.com', 'vsl_percent_cb', 50)

    def test_un_timeout_lanza_para_que_la_tarea_reintente(self):
        with patch('requests.patch', side_effect=requests.ReadTimeout()):
            with self.assertRaises(requests.ReadTimeout):
                crm.push_vsl_progress('a@b.com', 'vsl_percent_cb', 50)

    def test_un_4xx_no_se_reintenta(self):
        with patch('requests.patch', return_value=Mock(status_code=400, text='malo')):
            crm.push_vsl_progress('a@b.com', 'vsl_percent_cb', 50)
