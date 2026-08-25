# -*- coding: utf-8 -*-
"""El consentimiento de cookies propio, en sustitución de Cookiebot.

Lo que se fija aquí no es el aspecto, es que se comporte como Cookiebot en lo
que importa: a quién se le pregunta, qué se le deniega a Google mientras no
conteste, y qué eventos recibe GTM. Cambiar cualquiera de esas tres cosas sin
darse cuenta significa o medir sin permiso, o dejar de medir del todo.
"""
from pathlib import Path

from django.test import TestCase

from calendario.funnels import consentimiento

JS = Path(__file__).resolve().parents[2] / 'calendario' / 'static' / 'js' / 'consentimiento.js'

# Las 5 páginas que sirve Django con GTM dentro.
PAGINAS = (
    ('www.conquerblocks.com', '/evento/evento-online'),
    ('www.conquerblocks.com', '/evento/gracias-comunidad'),
    ('www.conquerfinance.com', '/evento/evento-online'),
    ('www.conquerlanguages.com', '/cl-evento'),
    ('www.conquerlanguages.com', '/grupos-comunidad'),
)


class AQuienSeLePreguntaTest(TestCase):
    """Solo donde hay normativa de consentimiento previo, como Cookiebot hoy.

    Fuera de ahí Cookiebot no muestra nada y lo da por implícito
    (`gdprApplies:false`, `method:"implied"`); poner un banner en LATAM y US
    sería fricción nueva sobre la mayor parte del tráfico.
    """

    def _aplica(self, pais):
        return consentimiento.aplica(self.client.get(
            '/evento/evento-online', HTTP_HOST='www.conquerblocks.com',
            **({'HTTP_CF_IPCOUNTRY': pais} if pais else {})).wsgi_request)

    def test_se_pregunta_en_la_union_europea(self):
        for pais in ('ES', 'DE', 'FR', 'IT', 'PT', 'IE'):
            self.assertTrue(self._aplica(pais), pais)

    def test_y_tambien_donde_alcanza_el_rgpd_o_equivalente(self):
        # EEE, Reino Unido, Suiza y Brasil.
        for pais in ('NO', 'IS', 'LI', 'GB', 'CH', 'BR'):
            self.assertTrue(self._aplica(pais), pais)

    def test_no_se_pregunta_donde_no_aplica(self):
        for pais in ('VE', 'MX', 'CO', 'AR', 'US', 'PE'):
            self.assertFalse(self._aplica(pais), pais)

    def test_sin_cabecera_se_pregunta(self):
        # Fuera de Cloudflare o en local no sabemos dónde está: ante la duda,
        # pedir permiso es lo correcto y lo barato.
        self.assertTrue(self._aplica(None))

    def test_los_codigos_raros_de_cloudflare_tambien_preguntan(self):
        # XX = no lo sabe, T1 = Tor.
        for pais in ('XX', 'T1'):
            self.assertTrue(self._aplica(pais), pais)


class LoQueSeLeDiceAGoogleTest(TestCase):
    """Consent Mode v2 tiene que estar puesto antes de que exista una etiqueta."""

    def _html(self, pais, host='www.conquerblocks.com', ruta='/evento/evento-online'):
        return self.client.get(ruta, HTTP_HOST=host, HTTP_CF_IPCOUNTRY=pais).content.decode()

    def test_donde_se_pregunta_se_deniega_hasta_que_conteste(self):
        html = self._html('ES')
        self.assertIn("var inicial = (aplica && !guardado) ? 'denied' : 'granted'", html)
        self.assertIn('var aplica = true', html)

    def test_donde_no_se_pregunta_se_concede(self):
        self.assertIn('var aplica = false', self._html('VE'))

    def test_el_bloque_va_antes_que_gtm(self):
        # Si GTM cargara primero, esa primera medición se escaparía sin permiso.
        for host, ruta in PAGINAS:
            html = self.client.get(ruta, HTTP_HOST=host, HTTP_CF_IPCOUNTRY='ES').content.decode()
            self.assertLess(html.index("gtag('consent', 'default'"), html.index('gtm.start'),
                            f'{host}{ruta}')

    def test_estan_las_cinco_claves_de_consent_mode_v2(self):
        html = self._html('ES')
        for clave in ('ad_storage', 'ad_user_data', 'ad_personalization',
                      'analytics_storage', 'personalization_storage'):
            self.assertIn(clave, html)


class LosEventosQueRecibeGtmTest(TestCase):
    """Los mismos nombres que empuja la plantilla de Cookiebot.

    Los contenedores ya tienen triggers montados sobre ellos; cambiarlos
    obligaría a tocar los tres y dejaría de medir hasta que alguien se diera
    cuenta.
    """

    def test_son_los_de_cookiebot(self):
        js = JS.read_text(encoding='utf-8')
        self.assertIn("'cookie_consent_' + k", js)
        self.assertIn("event: 'cookie_consent_update'", js)
        for categoria in ('preferences', 'statistics', 'marketing'):
            self.assertIn(f"'{categoria}'", js)

    def test_marketing_manda_sobre_las_tres_claves_de_anuncios(self):
        js = JS.read_text(encoding='utf-8')
        bloque = js[js.index('function comunicar'):js.index('// ------', js.index('function comunicar'))]
        for clave in ('ad_storage', 'ad_user_data', 'ad_personalization'):
            self.assertIn(f'{clave}: conceder(c.marketing)', bloque)
        self.assertIn('analytics_storage: conceder(c.statistics)', bloque)
        self.assertIn('personalization_storage: conceder(c.preferences)', bloque)


class CookiebotNoSeCargaTest(TestCase):
    """En estas páginas manda el nuestro, así que el suyo no debe aparecer.

    No está en nuestro código: lo inyecta el contenedor de GTM, que también
    sirve las páginas de Webflow, así que no basta con no incluirlo.
    """

    def test_se_le_impide_cargar(self):
        for host, ruta in PAGINAS:
            html = self.client.get(ruta, HTTP_HOST=host, HTTP_CF_IPCOUNTRY='ES').content.decode()
            self.assertIn('cookiebot', html.lower(), f'{host}{ruta}')
            self.assertIn('document.createElement = function', html, f'{host}{ruta}')


class LaMarcaDeCadaPaginaTest(TestCase):

    def test_cada_escuela_pinta_su_acento(self):
        for host, ruta, acento in (
            ('www.conquerblocks.com', '/evento/evento-online', '#ff4000'),
            ('www.conquerfinance.com', '/evento/evento-online', '#3ac043'),
            ('www.conquerlanguages.com', '/cl-evento', '#15b961'),
        ):
            html = self.client.get(ruta, HTTP_HOST=host, HTTP_CF_IPCOUNTRY='ES').content.decode()
            self.assertIn(f'--acento:{acento}', html, f'{host}{ruta}')

    def test_la_politica_de_privacidad_es_la_de_la_marca(self):
        html = self.client.get('/cl-evento', HTTP_HOST='www.conquerlanguages.com',
                               HTTP_CF_IPCOUNTRY='ES').content.decode()
        self.assertIn('conquerlanguages.com/politica-de-privacidad', html)


class LasCuatroCategoriasTest(TestCase):

    def test_estan_las_mismas_que_en_cookiebot(self):
        html = self.client.get('/evento/evento-online', HTTP_HOST='www.conquerblocks.com',
                               HTTP_CF_IPCOUNTRY='ES').content.decode()
        self.assertIn('Necesarias', html)
        self.assertIn('Siempre activas', html)
        for id_ in ('cqx-c-preferences', 'cqx-c-statistics', 'cqx-c-marketing'):
            self.assertIn(id_, html)

    def test_no_hay_forma_de_cerrarlo_sin_elegir(self):
        # Cerrarlo sin decidir equivaldría a un consentimiento que nadie dio.
        html = self.client.get('/evento/evento-online', HTTP_HOST='www.conquerblocks.com',
                               HTTP_CF_IPCOUNTRY='ES').content.decode()
        caja = html[html.index('id="cqx-consent"'):html.index('id="cqx-consent-panel"')]
        self.assertNotIn('cerrar', caja.lower())

    def test_se_puede_volver_a_abrir_para_retirar_el_permiso(self):
        js = JS.read_text(encoding='utf-8')
        self.assertIn('w.cqxConsent = {', js)
        self.assertIn('abrir:', js)


class LaDecisionSeGuardaTest(TestCase):

    def test_con_version_para_poder_volver_a_preguntar(self):
        js = JS.read_text(encoding='utf-8')
        self.assertIn('v: cfg.version', js)
        self.assertIn('v.v === cfg.version', js)

    def test_la_cookie_es_de_primera_parte_y_dura_un_ano(self):
        js = JS.read_text(encoding='utf-8')
        self.assertIn('SameSite=Lax', js)
        self.assertIn('365 * 24 * 60 * 60 * 1000', js)
