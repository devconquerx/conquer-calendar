# -*- coding: utf-8 -*-
"""Ninguna página pública puede servirse sin declarar documento.

Sin `<!DOCTYPE html>` el navegador entra en quirks mode y cambia el modelo de
caja por debajo: los anchos pasan a incluir padding y borde, y `box-sizing` deja
de comportarse como se espera. Las páginas de gracias se sirvieron así una
temporada —también en producción— y no se notó porque su CSS ya fija
`box-sizing` a mano, pero es un suelo movedizo para cualquier regla que dependa
del modelo estándar.
"""
from pathlib import Path

from django.test import TestCase

PLANTILLAS = (Path(__file__).resolve().parents[2] / 'calendario' / '_templates'
              / 'pages' / 'public' / 'evento')


class TodaPaginaDeclaraDocumentoTest(TestCase):

    RUTAS = (
        ('www.conquerblocks.com', '/evento/evento-online'),
        ('www.conquerblocks.com', '/evento/gracias-comunidad'),
        ('www.conquerfinance.com', '/evento/evento-online'),
        ('www.conquerfinance.com', '/evento/gracias-comunidad'),
        ('www.conquerlanguages.com', '/cl-evento'),
        ('www.conquerlanguages.com', '/grupos-comunidad'),
    )

    def test_lo_que_se_sirve_empieza_por_el_doctype(self):
        for host, ruta in self.RUTAS:
            html = self.client.get(ruta, HTTP_HOST=host).content.decode().lstrip()
            self.assertTrue(html.lower().startswith('<!doctype html>'), f'{host}{ruta}')

    def test_y_lleva_el_idioma_declarado(self):
        for host, ruta in self.RUTAS:
            html = self.client.get(ruta, HTTP_HOST=host).content.decode()
            self.assertIn('<html lang="es">', html, f'{host}{ruta}')

    def test_las_plantillas_que_se_sirven_solas_no_lo_pierden(self):
        # Se comprueba también en el fichero: es un descuido fácil de repetir al
        # crear una plantilla nueva copiando otra por la mitad.
        for nombre in ('paperboard', 'languages', 'gracias-paperboard', 'gracias-languages'):
            texto = (PLANTILLAS / f'{nombre}.html').read_text(encoding='utf-8')
            self.assertIn('<!DOCTYPE html>', texto, nombre)
