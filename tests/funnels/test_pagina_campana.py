# -*- coding: utf-8 -*-
"""Páginas de evento de campaña, empezando por la Coding Week.

Se diferencian de las pantallas de evento en que son de una campaña concreta y
conviven varias por marca, así que se resuelven por la ruta y no por el dominio.
"""
from pathlib import Path

from django.test import TestCase

from calendario.funnels.evento_views import EVENTOS, PAGINAS_DE_CAMPANA
from calendario.leads.models import Lead
from calendario.leads.services.utils import es_lead_de_lanzamiento

PLANTILLAS = Path(__file__).resolve().parents[2] / 'calendario' / '_templates' / 'pages' / 'public' / 'evento'


class LaPaginaSeSirveTest(TestCase):

    def _html(self, pais='ES'):
        r = self.client.get('/evento/evento-coding-week-eu',
                            HTTP_HOST='www.conquerblocks.com', HTTP_CF_IPCOUNTRY=pais)
        self.assertEqual(r.status_code, 200)
        return r.content.decode()

    def test_responde_y_es_la_de_coding_week(self):
        html = self._html()
        self.assertIn('Evento Coding Week - Conquer Blocks EU', html)
        self.assertIn('Consigue trabajo 100% remoto', html)

    def test_una_ruta_que_no_existe_da_404(self):
        self.assertEqual(
            self.client.get('/evento/evento-inventado/', HTTP_HOST='www.conquerblocks.com',
                            follow=True).status_code,
            404)

    def test_no_se_cachea(self):
        # Mismo motivo que la pantalla de evento: el prefijo depende de quien mire.
        r = self.client.get('/evento/evento-coding-week-eu', HTTP_HOST='www.conquerblocks.com')
        self.assertIn('no-store', r.headers.get('Cache-Control', ''))
        self.assertIn('CF-IPCountry', r.headers.get('Vary', ''))

    def test_lleva_el_gtm_de_blocks_y_su_consentimiento(self):
        html = self._html()
        self.assertIn("st = '5PK5LTG'", html)
        self.assertIn('id="cqx-consent"', html)

    def test_el_registro_pasa_a_la_de_gracias_sin_recargar(self):
        html = self._html()
        self.assertIn('id="evento-contenido"', html)
        self.assertIn('id="gracias-evento"', html)
        self.assertIn('/evento/gracias\\u002Dcomunidad', html)


class ElCodigoDeFunnelTest(TestCase):
    """Va fijo en la página, y el lead tiene que tratarse como de evento.

    Su código no lleva "lanzamiento" —es `cb-codingweek5-eu`—, así que sin
    declararlo se iría por el pipeline completo del funnel: Supabase,
    NeverBounce, Respond.io y conversiones. En Make consume las mismas dos
    operaciones que un lanzamiento, webhook e ingest, y nada más.
    """

    def test_la_pagina_lo_manda_fijo(self):
        html = self.client.get('/evento/evento-coding-week-eu',
                               HTTP_HOST='www.conquerblocks.com').content.decode()
        self.assertIn('cb\\u002Dcodingweek5\\u002Deu', html)

    def test_el_lead_cuenta_como_de_evento(self):
        self.assertTrue(es_lead_de_lanzamiento(Lead(funnel='cb-codingweek5-eu')))

    def test_los_del_funnel_normal_siguen_sin_serlo(self):
        for codigo in ('cb-eu', 'cl-latam', 'fi-us'):
            self.assertFalse(es_lead_de_lanzamiento(Lead(funnel=codigo)), codigo)

    def test_todos_los_codigos_configurados_cuentan(self):
        # Las que no recogen datos no declaran funnel y no tienen nada que
        # enrutar; se comprueban aparte.
        codigos = [p['funnel'] for p in PAGINAS_DE_CAMPANA.values() if p.get('funnel')]
        self.assertTrue(codigos, 'alguna página debería declarar funnel')
        for codigo in codigos:
            self.assertTrue(es_lead_de_lanzamiento(Lead(funnel=codigo)), codigo)


class ElTelefonoYaNoSePierdeTest(TestCase):
    """El original pide el teléfono y lo tira.

    Su campo oculto se llama `phone` y el escenario de Make mapea `lead_phone`,
    así que llega vacío: de los 12.722 leads de coding week que hay en el CRM,
    CERO tienen teléfono. Aquí se manda con el nombre que espera el ingest.
    """

    def test_el_formulario_usa_el_componente_que_manda_lead_phone(self):
        html = self.client.get('/evento/evento-coding-week-eu',
                               HTTP_HOST='www.conquerblocks.com').content.decode()
        self.assertIn('id="phoneLocal"', html)
        self.assertIn('name="lead_phone_prefix"', html)
        js = (Path(__file__).resolve().parents[2]
              / 'calendario' / 'static' / 'js' / 'evento-registro.js').read_text(encoding='utf-8')
        self.assertIn('lead_phone: tel', js)
        # Y el aviso de error se busca por id, no por clase.
        self.assertIn('id="aviso"', html)


class NingunaPaginaEnQuirksModeTest(TestCase):
    """Sin doctype el navegador cambia el modelo de caja por debajo.

    Las páginas de gracias se sirvieron una temporada así, y no se vio porque
    el CSS ya fija `box-sizing`; pero es una bomba de relojería para cualquier
    regla que dependa del modelo estándar.
    """

    RUTAS = (
        ('www.conquerblocks.com', '/evento/evento-online'),
        ('www.conquerblocks.com', '/evento/gracias-comunidad'),
        ('www.conquerblocks.com', '/evento/evento-coding-week-eu'),
        ('www.conquerlanguages.com', '/cl-evento'),
        ('www.conquerlanguages.com', '/grupos-comunidad'),
    )

    def test_todas_declaran_documento(self):
        for host, ruta in self.RUTAS:
            html = self.client.get(ruta, HTTP_HOST=host).content.decode().lstrip()
            self.assertTrue(html.lower().startswith('<!doctype html>'), f'{host}{ruta}')
            self.assertIn('<html lang="es">', html, f'{host}{ruta}')

    def test_las_plantillas_sueltas_no_pierden_el_doctype(self):
        for nombre in ('paperboard', 'languages', 'gracias-paperboard',
                       'gracias-languages', 'codingweek'):
            texto = (PLANTILLAS / f'{nombre}.html').read_text(encoding='utf-8')
            self.assertIn('<!DOCTYPE html>', texto, nombre)


class SaleEnElPanelDeFunnelsTest(TestCase):
    """El panel /funnels/ es donde se mira qué hay publicado.

    Si una página no sale ahí, existe pero nadie la encuentra.

    Las de campaña y las pantallas de lanzamiento comparten tabla: son la misma
    clase de cosa —páginas de evento sin funnel detrás— y separarlas las hacía
    parecer dos mundos distintos. El orden es el de migración, no alfabético ni
    por escuela.
    """

    def _tabla(self):
        html = self.client.get('/funnels/').content.decode()
        tabla = html[html.index('Páginas de evento</h2>'):]
        return tabla[:tabla.index('</table>')]

    def test_tienen_tabla(self):
        self.assertIn('Páginas de evento</h2>',
                      self.client.get('/funnels/').content.decode())

    def test_lista_la_coding_week_con_su_funnel(self):
        tabla = self._tabla()
        self.assertIn('Evento Coding Week', tabla)
        self.assertIn('cb-codingweek5-eu', tabla)
        self.assertIn('evento/evento-coding-week-eu', tabla)

    def test_van_todas_las_configuradas(self):
        tabla = self._tabla()
        for ruta, datos in PAGINAS_DE_CAMPANA.items():
            self.assertIn(datos['titulo_pagina'], tabla, ruta)

    def test_y_tambien_las_pantallas_de_lanzamiento_de_cada_marca(self):
        tabla = self._tabla()
        for escuela, datos in EVENTOS.items():
            self.assertIn(datos['titulo_pagina'], tabla, escuela)

    def test_salen_en_el_orden_en_que_se_migraron(self):
        tabla = self._tabla()
        titulos = [d['titulo_pagina'] for d in
                   sorted(list(EVENTOS.values()) + list(PAGINAS_DE_CAMPANA.values()),
                          key=lambda d: d['orden'])]
        posiciones = [tabla.index(t) for t in titulos]
        self.assertEqual(posiciones, sorted(posiciones), titulos)

    def test_cada_pagina_declara_su_turno_y_no_lo_repite(self):
        # Dos con el mismo número dejarían el orden al azar del diccionario.
        ordenes = [d['orden'] for d in
                   list(EVENTOS.values()) + list(PAGINAS_DE_CAMPANA.values())]
        self.assertEqual(len(ordenes), len(set(ordenes)), ordenes)


class ElRecorridoAcabaEnElGrupoTest(TestCase):
    """Registrarse lleva a la de gracias, y esa salta al grupo de WhatsApp.

    No hay pantalla nueva que construir: el original manda a
    `conquerblocks.com/evento/gracias-comunidad`, que es la misma que ya
    replicamos para la pantalla de evento de Blocks.
    """

    def test_manda_a_la_de_gracias_de_blocks(self):
        html = self.client.get('/evento/evento-coding-week-eu',
                               HTTP_HOST='www.conquerblocks.com').content.decode()
        # `escapejs` escapa hasta los guiones, de ahí la cadena cruda.
        self.assertIn(r'/evento/gracias\u002Dcomunidad', html)

    def test_y_esa_trae_el_grupo_y_el_salto(self):
        # Va embebida en la propia página, oculta, para el cambio sin recarga.
        html = self.client.get('/evento/evento-coding-week-eu',
                               HTTP_HOST='www.conquerblocks.com').content.decode()
        self.assertIn('cb.conquerx.com/1Qt1ef', html)
        self.assertIn('iniciarSaltoWhatsApp', html)
        self.assertIn('15000', html)

    def test_la_de_gracias_tambien_responde_por_su_cuenta(self):
        r = self.client.get('/evento/gracias-comunidad', HTTP_HOST='www.conquerblocks.com')
        self.assertEqual(r.status_code, 200)


class LasPaginasSinFormularioTest(TestCase):
    """Testimonios y bitácora no recogen datos.

    En el original, el único `<form>` de testimonios es un residuo de la
    plantilla de Webflow —sin destino ni código de funnel— y bitácora no tiene
    ninguno. Así que aquí no hay lead que crear, ni pantalla de gracias, ni
    salto a WhatsApp: montar todo eso sería inventarse un comportamiento.
    """

    PAGINAS = (
        ('www.conquerblocks.com', '/evento/evento-testimonios'),
        ('www.conquerlanguages.com', '/eventos/bitacora'),
    )

    def test_responden(self):
        for host, ruta in self.PAGINAS:
            self.assertEqual(self.client.get(ruta, HTTP_HOST=host).status_code, 200, f'{host}{ruta}')

    def test_no_traen_formulario_ni_pantalla_de_gracias(self):
        for host, ruta in self.PAGINAS:
            html = self.client.get(ruta, HTTP_HOST=host).content.decode()
            # Se mira el cierre: `<form` aparece también en el comentario que
            # explica por qué no lo hay.
            self.assertNotIn('</form>', html, f'{host}{ruta}')
            self.assertNotIn('id="formEvento"', html, f'{host}{ruta}')
            self.assertNotIn('id="gracias-evento"', html, f'{host}{ruta}')
            self.assertNotIn('iniciarSaltoWhatsApp', html, f'{host}{ruta}')

    def test_no_declaran_funnel(self):
        for clave in ('evento-testimonios', 'bitacora'):
            self.assertIsNone(PAGINAS_DE_CAMPANA[clave]['funnel'], clave)

    def test_llevan_su_gtm_y_su_consentimiento(self):
        # Que no recojan datos no las exime de medir ni de pedir permiso.
        for host, ruta, st in (('www.conquerblocks.com', '/evento/evento-testimonios', '5PK5LTG'),
                               ('www.conquerlanguages.com', '/eventos/bitacora', 'MPB7S5C7')):
            html = self.client.get(ruta, HTTP_HOST=host, HTTP_CF_IPCOUNTRY='ES').content.decode()
            self.assertIn(f"st = '{st}'", html, f'{host}{ruta}')
            self.assertIn('id="cqx-consent"', html, f'{host}{ruta}')

    def test_declaran_documento(self):
        for host, ruta in self.PAGINAS:
            html = self.client.get(ruta, HTTP_HOST=host).content.decode().lstrip()
            self.assertTrue(html.lower().startswith('<!doctype html>'), f'{host}{ruta}')


class TestimoniosLlevaSusVideosYSuBotonTest(TestCase):

    def _html(self):
        return self.client.get('/evento/evento-testimonios',
                               HTTP_HOST='www.conquerblocks.com').content.decode()

    def test_los_trece_testimonios_mas_el_principal(self):
        html = self._html()
        # 8 apaisados + 5 verticales + el de cabecera.
        self.assertEqual(html.count('iframe.mediadelivery.net/embed/135359/'), 14)

    def test_el_boton_lleva_a_agendar_con_sus_utm(self):
        html = self._html()
        self.assertEqual(html.count('agendar.conquerblocks.com'), 3)
        self.assertIn('utm_medium=testimonios', html)

    def test_las_nueve_resenas(self):
        self.assertEqual(self._html().count('img/eventos/testimonios/resena-'), 9)

    def test_los_videos_no_se_cargan_de_golpe(self):
        # Catorce iframes a la vez hunden la carga en móvil.
        html = self._html()
        self.assertEqual(html.count('loading="lazy"'), html.count('<iframe') + 10)


class BitacoraTest(TestCase):

    def _html(self):
        return self.client.get('/eventos/bitacora',
                               HTTP_HOST='www.conquerlanguages.com').content.decode()

    def test_lleva_su_video_de_su_biblioteca(self):
        # Languages tiene su propia biblioteca en Bunny, distinta de la de Blocks.
        self.assertIn('iframe.mediadelivery.net/embed/348662/879ce1c6', self._html())

    def test_esta_su_copia(self):
        html = self._html()
        self.assertIn('Bienvenidos a La Clase 0', html)
        self.assertIn('English Week', html)

    def test_la_sirve_en_eventos_en_plural(self):
        # Es la única así: las demás cuelgan de /evento/.
        self.assertEqual(self.client.get('/evento/bitacora',
                                         HTTP_HOST='www.conquerlanguages.com',
                                         follow=True).status_code, 404)
