# -*- coding: utf-8 -*-
"""Los textos de las páginas de evento se editan desde el admin.

Las tres reglas que importan:

- Sin nada guardado, cada página se sirve exactamente como estaba (los textos
  del código son la red de seguridad).
- Lo que se guarda en `ContenidoDeEvento` manda sobre el código.
- El esquema y las fichas del código no se pueden desincronizar: todo campo
  declarado tiene que tener su valor por defecto.
"""
from django.test import TestCase

from calendario.funnels import contenido
from calendario.funnels.admin import ContenidoDeEventoForm
from calendario.funnels.evento_views import EVENTOS, PAGINAS_DE_CAMPANA
from calendario.funnels.models import ContenidoDeEvento


class ElEsquemaCuadraConElCodigoTest(TestCase):
    """Cada texto declarado tiene que existir en la ficha que lo respalda."""

    def test_todos_los_campos_tienen_valor_por_defecto(self):
        for clave, pagina in contenido.PAGINAS.items():
            defectos = contenido.defectos_de(clave)
            for campo in pagina.campos:
                with self.subTest(pagina=clave, campo=campo.clave):
                    self.assertIsNotNone(
                        defectos.get(campo.clave),
                        f'{clave}.{campo.clave} no tiene valor por defecto en evento_views',
                    )

    def test_los_grupos_traen_sus_subcampos(self):
        for clave, pagina in contenido.PAGINAS.items():
            defectos = contenido.defectos_de(clave)
            for campo in pagina.campos:
                if campo.tipo != contenido.GRUPO:
                    continue
                fichas = defectos.get(campo.clave) or ()
                with self.subTest(pagina=clave, campo=campo.clave):
                    self.assertEqual(len(fichas), campo.filas)
                    for ficha in fichas:
                        for sub in campo.subcampos:
                            self.assertIn(sub.clave, ficha)

    def test_todas_las_paginas_tienen_su_fila(self):
        """La migración deja una fila por página conocida."""
        self.assertEqual(
            set(ContenidoDeEvento.objects.values_list('clave', flat=True)),
            set(contenido.PAGINAS),
        )


class SinEditarNadaSeSirveElTextoDelCodigoTest(TestCase):

    def test_pantalla_de_lanzamiento(self):
        html = self.client.get('/evento/evento-online',
                               HTTP_HOST='www.conquerblocks.com').content.decode()
        self.assertIn(EVENTOS['conquer-blocks']['titulo_grad'], html)
        self.assertIn('Introduce tu nombre', html)

    def test_pagina_de_campana(self):
        html = self.client.get('/evento/evento-coding-week-eu',
                               HTTP_HOST='www.conquerblocks.com').content.decode()
        self.assertIn('Consigue trabajo 100% remoto', html)
        self.assertIn('Bienvenido es Director de Educación Tecnológica', html)

    def test_pantalla_de_gracias(self):
        html = self.client.get('/evento/gracias-comunidad',
                               HTTP_HOST='www.conquerblocks.com').content.decode()
        self.assertIn('¡OBLIGATORIO!', html)
        self.assertIn('Clase Privada de Conquer Blocks.', html)


class LoGuardadoMandaTest(TestCase):

    def _guarda(self, clave, textos):
        fila = ContenidoDeEvento.objects.get(clave=clave)
        fila.textos = textos
        fila.save()

    def test_un_titular_editado_se_ve(self):
        self._guarda('lanzamiento-blocks', {'titulo_grad': 'Programador en 6 meses'})
        html = self.client.get('/evento/evento-online',
                               HTTP_HOST='www.conquerblocks.com').content.decode()
        self.assertIn('Programador en 6 meses', html)
        self.assertNotIn(EVENTOS['conquer-blocks']['titulo_grad'], html)

    def test_el_html_de_los_textos_no_se_escapa(self):
        self._guarda('lanzamiento-blocks',
                     {'subtitulo': 'Con <strong>negrita</strong> de verdad'})
        html = self.client.get('/evento/evento-online',
                               HTTP_HOST='www.conquerblocks.com').content.decode()
        self.assertIn('Con <strong>negrita</strong> de verdad', html)

    def test_los_bullets_editados_sustituyen_a_los_del_codigo(self):
        self._guarda('lanzamiento-blocks', {'bullets': ['Primero', 'Segundo']})
        html = self.client.get('/evento/evento-online',
                               HTTP_HOST='www.conquerblocks.com').content.decode()
        self.assertIn('Primero', html)
        self.assertIn('Segundo', html)
        self.assertNotIn(EVENTOS['conquer-blocks']['bullets'][0], html)

    def test_una_columna_editada_conserva_su_imagen(self):
        """En un grupo solo se pisan los textos; la imagen sigue siendo la del código."""
        self._guarda('trading-week', {'columnas': [
            {'titulo': 'Columna nueva', 'texto': 'Texto nuevo'}, {}, {}]})
        html = self.client.get('/trading-week-2025',
                               HTTP_HOST='www.conquerfinance.com').content.decode()
        self.assertIn('Columna nueva', html)
        self.assertIn('curso-1', html)  # la imagen de la primera columna

    def test_el_texto_de_la_tarjeta_lo_pone_la_pildora_enlazada(self):
        self._guarda('pildora-1', {'texto_tarjeta': 'TITULAR NUEVO DE LA PRIMERA'})
        html = self.client.get('/evento/pildoras-evento-2',
                               HTTP_HOST='www.conquerfinance.com').content.decode()
        self.assertIn('TITULAR NUEVO DE LA PRIMERA', html)

    def test_editar_no_toca_las_fichas_del_codigo(self):
        """`con_textos` devuelve una copia: las fichas son de módulo."""
        original = PAGINAS_DE_CAMPANA['evento-coding-week-eu']['titular']
        self._guarda('coding-week', {'titular': 'Otro titular'})
        self.client.get('/evento/evento-coding-week-eu', HTTP_HOST='www.conquerblocks.com')
        self.assertEqual(PAGINAS_DE_CAMPANA['evento-coding-week-eu']['titular'], original)


class ElFormularioDelAdminTest(TestCase):

    def test_pinta_un_campo_por_texto_con_lo_que_se_ve_hoy(self):
        fila = ContenidoDeEvento.objects.get(clave='lanzamiento-blocks')
        form = ContenidoDeEventoForm(instance=fila)
        self.assertIn('txt__titulo_grad', form.fields)
        self.assertEqual(form.fields['txt__titulo_grad'].initial,
                         EVENTOS['conquer-blocks']['titulo_grad'])
        # Los bullets se editan uno por línea.
        self.assertEqual(form.fields['txt__bullets'].initial.count('\n'),
                         len(EVENTOS['conquer-blocks']['bullets']) - 1)

    def test_guardar_vuelca_los_campos_al_json(self):
        fila = ContenidoDeEvento.objects.get(clave='bitacora')
        form = ContenidoDeEventoForm(instance=fila, data={
            **{n: '' for n in ContenidoDeEventoForm(instance=fila).fields},
            'txt__titular': 'Titular nuevo',
            'txt__parrafos': 'Uno\nDos',
        })
        self.assertTrue(form.is_valid(), form.errors)
        form.save()
        fila.refresh_from_db()
        self.assertEqual(fila.textos['titular'], 'Titular nuevo')
        self.assertEqual(fila.textos['parrafos'], ['Uno', 'Dos'])
        # Lo que se deja en blanco no se guarda: sigue sirviéndose el original.
        self.assertNotIn('antetitulo', fila.textos)

    def test_vaciar_un_campo_devuelve_el_texto_original(self):
        fila = ContenidoDeEvento.objects.get(clave='bitacora')
        fila.textos = {'antetitulo': 'Otro antetítulo'}
        fila.save()
        form = ContenidoDeEventoForm(instance=fila, data={
            n: '' for n in ContenidoDeEventoForm(instance=fila).fields})
        self.assertTrue(form.is_valid(), form.errors)
        form.save()
        fila.refresh_from_db()
        self.assertEqual(fila.textos, {})
        html = self.client.get('/eventos/bitacora',
                               HTTP_HOST='www.conquerlanguages.com').content.decode()
        self.assertIn('Bienvenidos a La Clase 0', html)

    def test_no_admite_scripts(self):
        fila = ContenidoDeEvento.objects.get(clave='bitacora')
        form = ContenidoDeEventoForm(instance=fila, data={
            **{n: '' for n in ContenidoDeEventoForm(instance=fila).fields},
            'txt__titular': 'Hola <script>alert(1)</script>',
        })
        self.assertFalse(form.is_valid())
        self.assertIn('txt__titular', form.errors)


class LaBitacoraDeLaCodingWeekSeEditaEnteraTest(TestCase):
    """De la bitácora de la Coding Week no queda nada escrito a código.

    Es la última página migrada, y la prueba de que una página nueva llega
    entera al panel: se le cambia cada campo declarado y todos salen en la
    página, incluidos el vídeo y las tres imágenes.
    """

    CLAVE = 'bitacora-coding-week'
    RUTA = '/evento/codingweek-evento-vitacora'
    HOST = 'www.conquerblocks.com'

    # Un valor reconocible por campo y lo que tiene que aparecer en el HTML.
    # `solo_v1` marca los que la segunda versión no usa: el logo lo pone el
    # sistema paperboard —el negro sobre papel, no el blanco de la primera— y el
    # fondo y la rejilla los sustituye su papel con textura. Siguen editándose,
    # pero solo se ven en `?v=1`.
    NUEVOS = {
        'chapa': ('EVENTO <strong>NUEVO</strong>', 'EVENTO <strong>NUEVO</strong>'),
        'antetitulo': ('LA CLASE 9', 'LA CLASE 9'),
        'titular': ('OTRO TITULAR', 'OTRO TITULAR'),
        'parrafos': (['Párrafo uno', 'Párrafo dos'], 'Párrafo uno<br><br>Párrafo dos'),
        'titulo_pagina': ('Otra pestaña', '<title>Otra pestaña</title>'),
        'video_principal': ('11111111-2222-3333-4444-555555555555',
                            '11111111-2222-3333-4444-555555555555'),
        'biblioteca': ('999999', 'embed/999999/'),
        'logo': ('/media/eventos/logo-nuevo.png', '/media/eventos/logo-nuevo.png'),
        'fondo': ('/media/eventos/fondo-nuevo.svg', '/media/eventos/fondo-nuevo.svg'),
        'rejilla': ('/media/eventos/rejilla-nueva.avif', '/media/eventos/rejilla-nueva.avif'),
    }

    def test_el_esquema_no_declara_nada_que_no_se_pruebe_aqui(self):
        """Si mañana se añade un campo, este test avisa en vez de mirar a otro lado."""
        self.assertEqual(
            {campo.clave for campo in contenido.campos_de(self.CLAVE)},
            set(self.NUEVOS),
        )
        self.assertTrue(self.SOLO_V1 < set(self.NUEVOS))

    SOLO_V1 = {'logo', 'fondo', 'rejilla'}
    # Los párrafos se ven en las dos, pero no con la misma marca: la réplica los
    # une con saltos dobles y la nueva los separa con margen, un <p> cada uno.
    EN_LA_NUEVA = {'parrafos': '<p>Párrafo uno</p>'}

    def _publica_todo(self):
        fila = ContenidoDeEvento.objects.get(clave=self.CLAVE)
        fila.textos = {clave: valor for clave, (valor, _) in self.NUEVOS.items()}
        fila.save()

    def test_cambiarlo_todo_desde_el_panel_cambia_la_pagina(self):
        """La primera versión, la réplica: usa todos los campos."""
        self._publica_todo()
        html = self.client.get(self.RUTA + '?v=1', HTTP_HOST=self.HOST).content.decode()
        for clave, (_, esperado) in self.NUEVOS.items():
            with self.subTest(campo=clave):
                self.assertIn(esperado, html)
        # Y ya no queda nada de lo que traía el código.
        self.assertNotIn('EL SENTIDO COMÚN', html)
        self.assertNotIn('104554f0', html)

    def test_y_la_que_ve_el_trafico_tambien(self):
        """La segunda, que es la que se sirve por defecto desde que se aprobó.

        Las tres imágenes no: el envoltorio las pone el sistema paperboard.
        """
        self._publica_todo()
        html = self.client.get(self.RUTA, HTTP_HOST=self.HOST).content.decode()
        for clave, (_, esperado) in self.NUEVOS.items():
            if clave in self.SOLO_V1:
                continue
            with self.subTest(campo=clave):
                self.assertIn(self.EN_LA_NUEVA.get(clave, esperado), html)
        self.assertNotIn('EL SENTIDO COMÚN', html)
        self.assertNotIn('104554f0', html)
