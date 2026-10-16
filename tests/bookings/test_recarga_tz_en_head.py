"""
La recarga con la zona del navegador sale desde el principio del <head>.

Sin `?tz=` la página se recarga con la zona del navegador. Esa recarga estaba al
final del <body>: la primera visita bajaba la página entera —unos 6 MB de
estáticos sin comprimir— para tirarla y pedirla otra vez, y dentro del iframe de
la academia el calendario tardaba en aparecer. Tiene que ir antes de cualquier
hoja de estilo o script externo.
"""
from django.test import Client, TestCase
from django.urls import reverse

from tests.factories import crear_disponibilidad, crear_event_type, crear_host


class RecargaTzEnHeadTest(TestCase):

    def setUp(self):
        self.host = crear_host()
        crear_disponibilidad(self.host, dia=0)
        self.et = crear_event_type(self.host)
        url = reverse('public_booking:booking_page', kwargs={
            'user_slug': self.host.slug, 'event_type_slug': self.et.slug})
        self.html = Client().get(url).content.decode()

    def test_va_antes_de_cualquier_estilo_o_script_externo(self):
        recarga = self.html.index('window.location.replace')
        self.assertLess(recarga, self.html.index('<link'))
        self.assertLess(recarga, self.html.index('<script src'))
        self.assertLess(recarga, self.html.index('</head>'))

    def test_corta_la_carga_antes_de_recargar(self):
        """Si el `stop` fuera detrás del `replace`, cancelaría la propia recarga."""
        self.assertLess(self.html.index('window.stop()'), self.html.index('window.location.replace'))

    def test_solo_hay_una_recarga(self):
        self.assertEqual(self.html.count('window.location.replace'), 1)
