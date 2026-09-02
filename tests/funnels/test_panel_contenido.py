# -*- coding: utf-8 -*-
"""La pantalla del panel donde se escriben los textos de las páginas de evento.

Lo que se comprueba aquí es la promesa del borrador: se puede escribir y mirar
cómo queda sin que la página pública cambie, y solo Publicar la cambia.
"""
import json
import tempfile

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase, override_settings

from calendario.funnels.models import ContenidoDeEvento
from calendario.permisos.models import Permiso, PermisoXRol, Rol, RolXUsuario

User = get_user_model()

LISTA = '/panel/contenido/'
EDITOR = '/panel/contenido/coding-week/'
GUARDAR = '/panel/contenido/coding-week/guardar/'
PUBLICAR = '/panel/contenido/coding-week/publicar/'
SUBIR = '/panel/contenido/coding-week/subir-imagen/'
DESCARTAR = '/panel/contenido/coding-week/descartar/'
PAGINA = '/evento/evento-coding-week-eu'
HOST = 'www.conquerblocks.com'


def _usuario(email, *codenames):
    user = User.objects.create_user(username=email, email=email, password='x')
    rol, _ = Rol.objects.get_or_create(nombre=f'rol-test-{user.pk}', defaults={'descripcion': 'test'})
    for codename in codenames:
        permiso, _ = Permiso.objects.get_or_create(codename=codename, defaults={'nombre': codename})
        PermisoXRol.objects.get_or_create(rol=rol, permiso=permiso)
    RolXUsuario.objects.get_or_create(usuario=user, rol=rol)
    return user


class PermisosTest(TestCase):

    def test_sin_permiso_no_se_entra(self):
        self.client.force_login(_usuario('nadie@test.com'))
        self.assertEqual(self.client.get(LISTA).status_code, 403)
        self.assertEqual(self.client.get(EDITOR).status_code, 403)

    def test_quien_solo_puede_ver_no_puede_guardar(self):
        self.client.force_login(_usuario('mirona@test.com', 'contenido_eventos.ver'))
        self.assertEqual(self.client.get(EDITOR).status_code, 200)
        r = self.client.post(GUARDAR, data=json.dumps({'txt__titular': 'Nuevo'}),
                             content_type='application/json')
        self.assertEqual(r.status_code, 403)

    def test_sin_sesion_manda_a_la_pantalla_de_acceso(self):
        self.assertEqual(Client().get(LISTA).status_code, 302)


class BorradorTest(TestCase):

    def setUp(self):
        self.usuario = _usuario('editora@test.com', 'contenido_eventos.ver',
                                'contenido_eventos.editar')
        self.client.force_login(self.usuario)
        self.fila = ContenidoDeEvento.objects.get(clave='coding-week')

    def _guarda(self, url, **campos):
        return self.client.post(url, data=json.dumps(campos), content_type='application/json')

    def test_guardar_no_toca_la_pagina_publica(self):
        r = self._guarda(GUARDAR, txt__cierre_titulo='La Coding Week de Marzo')
        self.assertEqual(r.status_code, 200)
        self.fila.refresh_from_db()
        self.assertEqual(self.fila.borrador['cierre_titulo'], 'La Coding Week de Marzo')
        self.assertEqual(self.fila.textos, {})

        html = Client().get(PAGINA, HTTP_HOST=HOST).content.decode()
        self.assertNotIn('La Coding Week de Marzo', html)
        self.assertIn('La Coding Week', html)  # sigue el texto de siempre

    def test_la_vista_previa_enseña_el_borrador_solo_a_quien_edita(self):
        self._guarda(GUARDAR, txt__cierre_titulo='La Coding Week de Marzo')

        propia = self.client.get(PAGINA + '?borrador=1', HTTP_HOST=HOST).content.decode()
        self.assertIn('La Coding Week de Marzo', propia)

        # Sin sesión, `?borrador=1` no vale de nada: es una página pública.
        ajena = Client().get(PAGINA + '?borrador=1', HTTP_HOST=HOST).content.decode()
        self.assertNotIn('La Coding Week de Marzo', ajena)

    def test_publicar_pasa_el_borrador_a_la_pagina(self):
        r = self._guarda(PUBLICAR, txt__cierre_titulo='La Coding Week de Marzo')
        self.assertEqual(r.status_code, 200)
        self.fila.refresh_from_db()
        self.assertEqual(self.fila.textos['cierre_titulo'], 'La Coding Week de Marzo')
        self.assertEqual(self.fila.borrador, {})
        self.assertEqual(self.fila.publicado_por, self.usuario)
        self.assertIsNotNone(self.fila.publicado_en)

        html = Client().get(PAGINA, HTTP_HOST=HOST).content.decode()
        self.assertIn('La Coding Week de Marzo', html)

    def test_descartar_deja_la_pagina_como_estaba(self):
        self._guarda(GUARDAR, txt__cierre_titulo='Un titular que no convence')
        r = self.client.post(DESCARTAR, HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        self.assertEqual(r.status_code, 200)
        self.fila.refresh_from_db()
        self.assertEqual(self.fila.borrador, {})

    def test_no_se_guarda_html_peligroso(self):
        r = self._guarda(GUARDAR, txt__titular='<script>alert(1)</script>')
        self.assertEqual(r.status_code, 400)
        self.assertIn('txt__titular', r.json()['errores'])
        self.fila.refresh_from_db()
        self.assertEqual(self.fila.borrador, {})

    def test_el_editor_abre_con_el_borrador_y_no_con_lo_publicado(self):
        self._guarda(GUARDAR, txt__cierre_titulo='Lo que estaba escribiendo')
        html = self.client.get(EDITOR).content.decode()
        self.assertIn('Lo que estaba escribiendo', html)

    def test_la_lista_avisa_de_los_borradores_sin_publicar(self):
        self._guarda(GUARDAR, txt__cierre_titulo='A medias')
        self.assertIn('Borrador sin publicar', self.client.get(LISTA).content.decode())


PNG = b'\x89PNG\r\n\x1a\n' + b'\x00' * 64


@override_settings(MEDIA_ROOT=tempfile.mkdtemp())
class ImagenesTest(TestCase):
    """Subir una imagen desde el editor y usarla en la página."""

    def setUp(self):
        self.usuario = _usuario('fotografa@test.com', 'contenido_eventos.ver',
                                'contenido_eventos.editar')
        self.client.force_login(self.usuario)
        self.fila = ContenidoDeEvento.objects.get(clave='coding-week')

    def _sube(self, nombre='hero nueva.png', contenido=PNG):
        return self.client.post(SUBIR, {'archivo': SimpleUploadedFile(nombre, contenido)})

    def test_se_sube_y_devuelve_su_url(self):
        r = self._sube()
        self.assertEqual(r.status_code, 200, r.content)
        url = r.json()['url']
        self.assertTrue(url.startswith('/media/eventos/coding-week/hero-nueva-'), url)
        self.assertTrue(url.endswith('.png'), url)

    def test_la_imagen_subida_se_pinta_en_la_pagina(self):
        url = self._sube().json()['url']
        self.client.post(PUBLICAR, data=json.dumps({'txt__hero': url}),
                         content_type='application/json')
        html = Client().get(PAGINA, HTTP_HOST=HOST).content.decode()
        self.assertIn(f'src="{url}"', html)
        # Las que no se tocan siguen saliendo de los estáticos del repo.
        self.assertIn('/static/img/eventos/codingweek/logo-blanco.png', html)

    def test_vaciar_la_imagen_devuelve_la_original(self):
        url = self._sube().json()['url']
        self.client.post(PUBLICAR, data=json.dumps({'txt__hero': url}),
                         content_type='application/json')
        self.client.post(PUBLICAR, data=json.dumps({'txt__hero': ''}),
                         content_type='application/json')
        html = Client().get(PAGINA, HTTP_HOST=HOST).content.decode()
        self.assertIn('/static/img/eventos/codingweek/hero.avif', html)

    def test_no_admite_un_ejecutable_disfrazado(self):
        r = self._sube(nombre='troyano.png', contenido=b'MZ' + b'\x00' * 64)
        self.assertEqual(r.status_code, 400)
        self.assertIn('no parece una imagen', r.json()['mensaje'])

    def test_no_admite_svg(self):
        r = self._sube(nombre='logo.svg', contenido=b'<svg xmlns="http://www.w3.org/2000/svg"/>')
        self.assertEqual(r.status_code, 400)
        self.assertIn('Formato no admitido', r.json()['mensaje'])

    def test_no_admite_una_imagen_enorme(self):
        r = self._sube(nombre='enorme.png', contenido=PNG + b'\x00' * (9 * 1024 * 1024))
        self.assertEqual(r.status_code, 400)
        self.assertIn('8 MB', r.json()['mensaje'])

    def test_no_se_puede_apuntar_a_una_imagen_de_fuera(self):
        r = self.client.post(GUARDAR, data=json.dumps({'txt__hero': 'https://ajeno.com/x.png'}),
                             content_type='application/json')
        self.assertEqual(r.status_code, 400)
        self.assertIn('txt__hero', r.json()['errores'])

    def test_subir_pide_permiso(self):
        self.client.force_login(_usuario('mirona2@test.com', 'contenido_eventos.ver'))
        self.assertEqual(self._sube().status_code, 403)


GRACIAS = '/panel/contenido/gracias-blocks/'
GUARDAR_GRACIAS = '/panel/contenido/gracias-blocks/guardar/'
PUBLICAR_GRACIAS = '/panel/contenido/gracias-blocks/publicar/'
PAGINA_GRACIAS = '/evento/gracias-comunidad'


class EnlaceDelGrupoTest(TestCase):
    """El enlace del grupo de WhatsApp de la pantalla de gracias."""

    def setUp(self):
        self.client.force_login(_usuario('community@test.com', 'contenido_eventos.ver',
                                         'contenido_eventos.editar'))
        self.fila = ContenidoDeEvento.objects.get(clave='gracias-blocks')

    def _guarda(self, url, valor):
        return self.client.post(url, data=json.dumps({'txt__whatsapp': valor}),
                                content_type='application/json')

    def test_cambiarlo_cambia_el_boton_y_el_salto(self):
        nuevo = 'https://chat.whatsapp.com/edicion-de-marzo'
        self.assertEqual(self._guarda(PUBLICAR_GRACIAS, nuevo).status_code, 200)
        html = Client().get(PAGINA_GRACIAS, HTTP_HOST=HOST).content.decode()
        # El href de los tres botones y el destino del salto automático.
        self.assertEqual(html.count(f'href="{nuevo}"'), 3)
        self.assertIn(f'data-whatsapp="{nuevo}"', html)

    def test_vaciarlo_quita_el_boton_en_vez_de_volver_al_original(self):
        """Un enlace vacío es una decisión: el grupo de esa edición ya no vale."""
        self.assertEqual(self._guarda(PUBLICAR_GRACIAS, '').status_code, 200)
        self.fila.refresh_from_db()
        self.assertEqual(self.fila.textos['whatsapp'], '')
        html = Client().get(PAGINA_GRACIAS, HTTP_HOST=HOST).content.decode()
        self.assertNotIn('cb.conquerx.com', html)
        self.assertNotIn('Unirme a la Comunidad VIP', html)

    def test_no_admite_un_javascript(self):
        r = self._guarda(GUARDAR_GRACIAS, 'javascript:alert(1)')
        self.assertEqual(r.status_code, 400)
        self.assertIn('txt__whatsapp', r.json()['errores'])
        self.fila.refresh_from_db()
        self.assertEqual(self.fila.borrador, {})

    def test_el_borrador_del_enlace_no_toca_la_pagina_publica(self):
        self._guarda(GUARDAR_GRACIAS, 'https://chat.whatsapp.com/borrador')
        html = Client().get(PAGINA_GRACIAS, HTTP_HOST=HOST).content.decode()
        self.assertNotIn('chat.whatsapp.com/borrador', html)
        previa = self.client.get(PAGINA_GRACIAS + '?borrador=1', HTTP_HOST=HOST).content.decode()
        self.assertIn('chat.whatsapp.com/borrador', previa)
