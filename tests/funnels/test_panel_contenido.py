# -*- coding: utf-8 -*-
"""La pantalla del panel donde se escriben los textos de las páginas de evento.

Lo que se comprueba aquí es la promesa del borrador: se puede escribir y mirar
cómo queda sin que la página pública cambie, y solo Publicar la cambia.
"""
import json

from django.contrib.auth import get_user_model
from django.test import Client, TestCase

from calendario.funnels.models import ContenidoDeEvento
from calendario.permisos.models import Permiso, PermisoXRol, Rol, RolXUsuario

User = get_user_model()

LISTA = '/panel/contenido/'
EDITOR = '/panel/contenido/coding-week/'
GUARDAR = '/panel/contenido/coding-week/guardar/'
PUBLICAR = '/panel/contenido/coding-week/publicar/'
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
