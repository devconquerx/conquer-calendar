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


class SacarloAManoParaVerloTest(TestCase):
    """`?debug=1` lo saca aunque no toque.

    Desde LATAM o US no se muestra —y ahí trabajamos casi siempre—, así que sin
    esto no hay forma de repasar cómo queda en cada marca sin fingir una IP
    europea.
    """

    def _html(self, query='', pais='VE'):
        return self.client.get('/evento/evento-online' + query,
                               HTTP_HOST='www.conquerblocks.com',
                               HTTP_CF_IPCOUNTRY=pais).content.decode()

    def test_sin_el_no_sale_fuera_de_la_ue(self):
        self.assertIn('var aplica = false', self._html())

    def test_con_el_sale(self):
        self.assertIn('var aplica = true', self._html('?debug=1'))
        self.assertIn('var forzar = true', self._html('?debug=1'))

    def test_ignora_lo_ya_decidido(self):
        # Si no, aceptaría una vez y no volvería a salir en ese navegador.
        js = JS.read_text(encoding='utf-8')
        self.assertIn('cfg.forzar ? null : leer()', js)
        self.assertIn("&& !forzar", self._html('?debug=1'))

    def test_y_deniega_mientras_no_conteste(self):
        # Forzado no puede significar "sácalo pero mide igual".
        html = self._html('?debug=1')
        self.assertIn('var inicial = (aplica && !guardado)', html)

    def test_otro_valor_no_lo_saca(self):
        for q in ('?debug=0', '?debug=true', '?debug='):
            self.assertIn('var aplica = false', self._html(q), q)


class CadaMarcaHablaSuIdiomaVisualTest(TestCase):
    """Blocks y Finance van en cartón y con el CTA pixelado; Languages no.

    Es lo que fallaba en Cookiebot: el mismo recuadro blanco genérico sobre tres
    marcas que no se parecen en nada.
    """

    def _html(self, host, ruta):
        return self.client.get(ruta, HTTP_HOST=host, HTTP_CF_IPCOUNTRY='ES').content.decode()

    def test_blocks_y_finance_van_en_carton(self):
        for host, ruta in (('www.conquerblocks.com', '/evento/evento-online'),
                           ('www.conquerfinance.com', '/evento/evento-online')):
            bloque = self._html(host, ruta).split('#cqx-consent .tarjeta{')[2]
            self.assertIn('paperboard-texture', bloque, f'{host}{ruta}')
            self.assertIn('background-size:auto,216px', bloque, f'{host}{ruta}')

    def test_y_su_cta_lleva_el_borde_pixelado_y_su_degradado(self):
        for host, ruta, g1, g2 in (
            ('www.conquerblocks.com', '/evento/evento-online', '#ff4000', '#ff9800'),
            ('www.conquerfinance.com', '/evento/evento-online', '#aed916', '#3ac043'),
        ):
            html = self._html(host, ruta)
            self.assertIn('clip-path:var(--pixel-clip)', html, f'{host}{ruta}')
            self.assertIn(f'linear-gradient(135deg,{g1},{g2})', html, f'{host}{ruta}')

    def test_languages_se_queda_liso_y_redondeado(self):
        html = self._html('www.conquerlanguages.com', '/cl-evento')
        # Su fondo es una foto y sus botones píldoras: ni cartón ni píxeles.
        self.assertNotIn('paperboard-texture', html.split('id="cqx-consent"')[0].split('<style>')[-1])
        self.assertNotIn('clip-path:var(--pixel-clip)', html)
        self.assertIn('--radio:20px', html)

    def test_el_pixelado_no_deja_el_foco_sin_marcar(self):
        # `outline` se recorta junto con el botón, así que se marca por dentro.
        html = self._html('www.conquerblocks.com', '/evento/evento-online')
        self.assertIn('button.principal:focus-visible{outline:none;box-shadow:inset', html)


class ElIconoQueQuedaDespuesTest(TestCase):
    """Tras decidir queda un icono flotante, como el de Cookiebot.

    No es decoración: retirar el consentimiento tiene que ser tan fácil como
    darlo, y sin una forma visible de volver a abrirlo no lo es.
    """

    def _html(self, host='www.conquerblocks.com', ruta='/evento/evento-online', pais='ES'):
        return self.client.get(ruta, HTTP_HOST=host, HTTP_CF_IPCOUNTRY=pais).content.decode()

    def test_esta_en_la_pagina_y_empieza_oculto(self):
        html = self._html()
        self.assertIn('id="cqx-consent-icono"', html)
        marca = html[html.index('id="cqx-consent-icono"'):]
        self.assertIn('hidden', marca[:marca.index('>')])

    def test_solo_aparece_cuando_el_modal_esta_cerrado(self):
        js = JS.read_text(encoding='utf-8')
        self.assertIn('icono.hidden = !(cfg.aplica && caja.hidden)', js)

    def test_no_aparece_donde_no_se_pregunta(self):
        # Donde no se pregunta no hay nada que reconsiderar; el propio guard de
        # `cfg.aplica` lo cubre, y aquí se fija que la página lo declare así.
        self.assertIn('var aplica = false', self._html(pais='VE'))

    def test_al_pulsarlo_se_reabre(self):
        js = JS.read_text(encoding='utf-8')
        self.assertIn("pulsar('cqx-consent-icono', function () { w.cqxConsent.abrir(); });", js)

    def test_el_foco_va_al_icono_al_cerrar(self):
        # Devolverlo al fondo de la página dejaría a quien navega con teclado
        # sin saber dónde ha quedado.
        js = JS.read_text(encoding='utf-8')
        self.assertIn('if (icono && !icono.hidden) icono.focus();', js)

    def test_tiene_nombre_accesible(self):
        html = self._html()
        marca = html[html.index('id="cqx-consent-icono"'):]
        self.assertIn('aria-label="Configurar cookies"', marca[:marca.index('>')])

    def test_en_las_marcas_pixeladas_no_es_un_circulo(self):
        # Un círculo desentonaría al lado de un CTA de esquina pixelada.
        self.assertIn('#cqx-consent-icono{border-radius:0', self._html())
        self.assertNotIn('#cqx-consent-icono{border-radius:0',
                         self._html('www.conquerlanguages.com', '/cl-evento'))
