"""
Tracking desmedido: la reserva no puede caerse porque la URL de origen sea larga.

Caso real de producción (FUNNELS-67): el funnel viejo metía en el link de
/agenda/ un parámetro `url` con la URL entera de la landing dentro —incluido el
`ttclid` de TikTok, que solo él ocupa ~280 caracteres—, así que la URL acababa
conteniéndose a sí misma y pasaba de 1.500 caracteres. `Reserva.url` es
varchar(1500): Postgres rechazaba el INSERT con DataError, y como la vista solo
captura duplicado y slot-ocupado, el visitante se comía un 500 y se quedaba sin
reserva. Medido en prod: 20 de 1.472 prellamadas en 2 días llegan con esa forma.

El tracking es un dato de marketing, no puede tumbar una venta: se guarda lo que
quepa y se sigue adelante.
"""
import json
from unittest.mock import patch

from django.test import TestCase
from django.urls import reverse

from calendario.bookings.models import Reserva
from calendario.funnels.models import FunnelForm, Prellamada
from tests.factories import (
    crear_disponibilidad, crear_event_type, crear_host, slot_futuro,
)

EMAIL = 'lead@ejemplo.com'

# Un ttclid real de TikTok: 277 caracteres. Es la pieza que hace explotar la URL.
TTCLID = 'E_C_P_' + 'CuABkfjYgL07Yl1Zd3FFcg4LS7Zz' * 9 + 'EgR2Mi4w'


def url_del_funnel_viejo():
    """Reproduce la URL que generaba conquerx-funnels-new: la landing completa
    (con su ttclid) empotrada como parámetro `url` dentro de la URL de /agenda/,
    más el ttclid otra vez suelto."""
    from urllib.parse import quote
    landing = (
        'https://www.conquerlanguages.com/clase-online-gratuita-latam'
        '?utm_source=TikTokAds&utm_medium=TikTok&utm_id=1859197034934610'
        '&utm_content=AD%20%5BLATAM%5D%205-2%20%28M%29'
        '&utm_campaign=CL_TikTokAds_LATAM&utm_term=Open_Andy_LATAM_TT'
        '&utm_adid=1863096619341874&utm_adsetid=1859557378610177'
        '&utm_idcampaign=1859197034934610&ttclid=' + TTCLID
    )
    return (
        'https://www.conquerlanguages.com/agenda/english/latam/'
        '?v=20250120&event_id=1787252398622_yyykpp&journey_id=jrn_1787251361721_ogdo29'
        '&fullname=Jorge+Cristhian&last_name=&email=jorge.c.veras.n%40gmail.com'
        '&lead_phone_prefix=%2B34&lead_phone=&country_name=-'
        '&utm_source=TikTokAds&utm_medium=TikTok&utm_campaign=CL_TikTokAds_LATAM'
        '&utm_term=Open_Andy_LATAM_TT&utm_content=AD+%5BLATAM%5D+5-2+%28M%29'
        '&utm_idcampaign=1859197034934610&utm_adsetid=1859557378610177'
        '&utm_adid=1863096619341874&gclid=&gbraid=&wbraid=&fbclid=&msclkid='
        '&dclid=&_ga=&_gid=&_fbp=&gclsrc=&ip=38.250.131.45&funnel=cl-latam'
        '&url=' + quote(landing, safe='') + '&ttclid=' + TTCLID
    )


class TrackingLargoTest(TestCase):

    def setUp(self):
        self.host = crear_host()
        self.et = crear_event_type(self.host)
        for dia in range(5):
            crear_disponibilidad(self.host, dia=dia)
        self.funnel = FunnelForm.objects.create(
            key='TestFunnel', slug='test-funnel', escuela='conquer-languages',
            region='latam', nombre='Funnel de test', config={},
        )

    def _reservar(self, tracking):
        prellamada = Prellamada.objects.create(
            funnel=self.funnel, nombre='Lead', email=EMAIL,
            resultado=Prellamada.Resultado.CALENDARIO, event_type=self.et,
            tracking=tracking,
        )
        return self.client.post(
            reverse('funnels:reservar', kwargs={'slug': self.funnel.slug}),
            data=json.dumps({
                'prellamada_token': str(prellamada.token),
                'inicio_utc': slot_futuro().isoformat(),
                'tz': 'America/Lima',
                'nombre': 'Jorge Cristhian',
                'email': EMAIL,
            }),
            content_type='application/json',
        )

    @patch('calendario.funnels.views._avisar_si_es_nueva')
    @patch('calendario.bookings.services.hay_conflicto_calendario', return_value=False)
    @patch('calendario.bookings.services.crear_evento_google')
    def test_url_de_1700_caracteres_no_tumba_la_reserva(self, _ev, _conf, _mail):
        url = url_del_funnel_viejo()
        self.assertGreater(len(url), 1500, 'la URL de prueba debe pasarse del límite')

        resp = self._reservar({'url': url, 'journey_id': 'jrn_1', 'event_id': 'ev_1'})

        self.assertEqual(resp.status_code, 200)
        reserva = Reserva.objects.get(email_invitado=EMAIL)
        self.assertEqual(len(reserva.url), 1500)
        self.assertTrue(url.startswith(reserva.url), 'debe guardarse el principio, no otra cosa')
        # Lo que de verdad importa para atribuir sobrevive: está al principio.
        self.assertIn('utm_campaign=CL_TikTokAds_LATAM', reserva.url)
        self.assertIn('journey_id=jrn_1787251361721_ogdo29', reserva.url)

    @patch('calendario.funnels.views._avisar_si_es_nueva')
    @patch('calendario.bookings.services.hay_conflicto_calendario', return_value=False)
    @patch('calendario.bookings.services.crear_evento_google')
    def test_utm_desmedido_tampoco_la_tumba(self, _ev, _conf, _mail):
        """Los utm_* son varchar(255) y tienen el mismo agujero: en prod ya
        llegan utm_content de 102 caracteres."""
        resp = self._reservar({
            'utm_content': 'Ads_2025_04_ESP_Bienve_Evergreen_' * 20,   # 660
            'utm_term': 'Open_Bienvenido_EU_TT_' * 30,                  # 660
            'utm_form_variant': '5' * 700,                              # varchar(500)
        })

        self.assertEqual(resp.status_code, 200)
        reserva = Reserva.objects.get(email_invitado=EMAIL)
        self.assertEqual(len(reserva.utm_content), 255)
        self.assertEqual(len(reserva.utm_term), 255)
        self.assertEqual(len(reserva.utm_form_variant), 500)

    @patch('calendario.funnels.views._avisar_si_es_nueva')
    @patch('calendario.bookings.services.hay_conflicto_calendario', return_value=False)
    @patch('calendario.bookings.services.crear_evento_google')
    def test_el_tracking_normal_se_guarda_intacto(self, _ev, _conf, _mail):
        """El truncado no puede tocar lo que ya cabía."""
        url = 'https://www.conquerblocks.com/agenda/fullstack/latam/?utm_source=TikTokAds'
        resp = self._reservar({'url': url, 'utm_source': 'TikTokAds', 'setter': 'juan.perez'})

        self.assertEqual(resp.status_code, 200)
        reserva = Reserva.objects.get(email_invitado=EMAIL)
        self.assertEqual(reserva.url, url)
        self.assertEqual(reserva.utm_source, 'TikTokAds')
        self.assertEqual(reserva.setter, 'juan.perez')
