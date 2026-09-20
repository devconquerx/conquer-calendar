"""Cada página del funnel declara el favicon de su marca.

Ninguna lo declaraba: el shell no emitía `<link rel="icon">` y el único que
ponía uno era React, desde el tema, para Conquer Legal. El navegador, sin link,
solo puede pedir `/favicon.ico` en la raíz del dominio — y eso responde 404 en
conquerblocks.com, conquerfinance.com y conquerlegal.com (ahí contesta la página
de error de Webflow). Resultado: pestaña con el icono en blanco en todo el
funnel de tres marcas, mientras las páginas de Webflow de esos mismos dominios
sí lo enseñaban, porque lo declaran en su propio head.

Se comprueba en el HTML servido, no en el tema: el fallo estaba justo en que el
tema lo tenía y la página no.
"""
import re
from pathlib import Path

from django.test import TestCase

from calendario.funnels.models import FunnelForm

# (URL, escuela, fichero esperado). Una por marca, más Conquer AI, que no es
# marca propia y lleva el icono de la suya.
PAGINAS = [
    ('/conquer-blocks/clase-online-gratuita-eu', 'conquer-blocks', 'conquer-blocks'),
    ('/conquer-ai/clase-online-gratuita-eu', 'conquer-ai', 'conquer-blocks'),
    ('/clase-online-gratuita-latam?escuela=conquer-finance', 'conquer-finance', 'conquer-finance'),
    ('/hub/registro-eu', 'conquer-legal', 'conquer-legal'),
]

LINK_ICON = re.compile(r'<link[^>]*rel="icon"[^>]*>', re.I)


class FaviconDelFunnelTest(TestCase):

    def _icono(self, url):
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200, url)
        encontrado = LINK_ICON.search(resp.content.decode())
        self.assertIsNotNone(encontrado, f'{url}: la página no declara favicon')
        return encontrado.group(0)

    def test_cada_marca_declara_el_suyo_en_el_html(self):
        for url, _escuela, fichero in PAGINAS:
            with self.subTest(url=url):
                self.assertIn(f'img/favicons/{fichero}', self._icono(url))

    def test_las_cuatro_etapas_lo_llevan(self):
        """El icono se pide una vez por documento, y cada etapa es un documento
        propio cuando se entra directo (anuncio, link compartido, recarga)."""
        for url in (
            '/conquer-blocks/clase-online-gratuita-eu',
            '/conquer-blocks/video-clase-eu/',
            '/agenda/fullstack/eu/',
            '/conquer-blocks/confirmacion-llamada-eu/',
        ):
            with self.subTest(url=url):
                self.assertIn('img/favicons/conquer-blocks', self._icono(url))

    def test_las_paginas_de_evento_tambien(self):
        """Las réplicas de Webflow se distinguían del original en la pestaña.

        El original declara su favicon en su propio head; la réplica no lo hacía
        en ninguna de sus quince páginas, así que salía con el icono en blanco.
        """
        # La escuela va en la query igual que arriba: sin el dominio de marca,
        # `testserver` no la resuelve por Host y la ruta responde 404.
        for url, fichero in (
            ('/evento/codingweek-evento-vitacora', 'conquer-blocks'),
            ('/evento/evento-online?escuela=conquer-finance', 'conquer-finance'),
        ):
            with self.subTest(url=url):
                self.assertIn(f'img/favicons/{fichero}', self._icono(url))

    def test_una_escuela_desconocida_no_pinta_un_link_roto(self):
        """Mejor sin icono que con un <link> que apunte a un 404."""
        FunnelForm.objects.create(
            key='MarcaRara', slug='marca-rara-latam', escuela='conquer-lo-que-sea',
            region='latam', nombre='Marca rara',
            config={'blocks': [], 'q_order': [], 'score_ranges': []},
        )
        resp = self.client.get('/conquer-lo-que-sea/clase-online-gratuita-latam')
        self.assertEqual(resp.status_code, 200)
        self.assertIsNone(LINK_ICON.search(resp.content.decode()))


class ElIconoVaDentroDelHeadTest(TestCase):
    """No basta con que el `<link>` esté en el HTML: tiene que estar en el head.

    Iba justo después del include del consentimiento, que pinta su banner —un
    `<div>`— ahí mismo. Al primer elemento de cuerpo el navegador cierra `<head>`
    y abre `<body>`, así que el `<link rel="icon">` acababa dentro del cuerpo,
    donde se ignora: la pestaña seguía en blanco con el link en el HTML.

    Se comprueba por orden en el texto, que es justo lo que decide el parser.
    """

    PLANTILLAS = (Path(__file__).resolve().parents[2] / 'calendario' / '_templates'
                  / 'pages' / 'public' / 'evento')

    def test_en_todas_las_plantillas_el_icono_va_antes_del_consentimiento(self):
        plantillas = [f for f in sorted(self.PLANTILLAS.glob('*.html'))
                      if '_favicon_evento.html' in f.read_text(encoding='utf-8')]
        self.assertTrue(plantillas, 'ninguna plantilla incluye el favicon')
        for f in plantillas:
            texto = f.read_text(encoding='utf-8')
            with self.subTest(plantilla=f.name):
                self.assertLess(texto.index('_favicon_evento.html'),
                                texto.index('_consentimiento.html'),
                                f'{f.name}: el favicon va después del banner y cae fuera del head')

    def test_y_en_la_pagina_servida_el_link_sale_antes_del_banner(self):
        for url in ('/evento/codingweek-evento-vitacora',
                    '/evento/evento-online?escuela=conquer-blocks',
                    '/eventos/bitacora?escuela=conquer-languages'):
            with self.subTest(url=url):
                html = self.client.get(url).content.decode()
                self.assertLess(html.index('rel="icon"'), html.index('id="cqx-consent"'), url)
