"""
Las horas del panel se editan siempre en 24h.

El <input type="time"> nativo se pinta en AM/PM o en 24h según el idioma del
navegador, así que la misma pantalla se veía distinta según quién la abriera.
El panel usa inputs de texto marcados con js-hora24 (ver static/js/hora-24h.js),
que muestran y envían siempre HH:MM.
"""
from datetime import time

from django.test import Client, TestCase
from django.urls import reverse

from tests.factories import crear_disponibilidad, crear_host


class FormatoHora24hPanelTest(TestCase):

    def setUp(self):
        self.client = Client()
        self.host = crear_host(email='host.hora24@test.com')
        self.client.force_login(self.host)
        crear_disponibilidad(self.host, dia=0, inicio=time(9, 0), fin=time(17, 30))

    def test_el_panel_no_usa_inputs_de_hora_nativos(self):
        resp = self.client.get(reverse('panel_disponibilidad:bloque_list'))
        self.assertEqual(resp.status_code, 200)
        self.assertNotContains(resp, 'type="time"')

    def test_los_campos_de_hora_van_marcados_para_el_script(self):
        resp = self.client.get(reverse('panel_disponibilidad:bloque_list'))
        html = resp.content.decode()
        self.assertIn('js-hora24', html)
        self.assertIn('js/hora-24h.js', html)

    def test_las_horas_se_pintan_en_24h(self):
        resp = self.client.get(reverse('panel_disponibilidad:bloque_list'))
        html = resp.content.decode()
        self.assertIn('value="17:30"', html)
        self.assertNotIn('5:30 PM', html)
        self.assertNotIn('05:30 p', html)
