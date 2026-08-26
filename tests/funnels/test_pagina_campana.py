# -*- coding: utf-8 -*-
"""Páginas de evento de campaña, empezando por la Coding Week.

Se diferencian de las pantallas de evento en que son de una campaña concreta y
conviven varias por marca, así que se resuelven por la ruta y no por el dominio.
"""
import re
from pathlib import Path

from django.test import TestCase, override_settings

from calendario.funnels.evento_views import (
    EVENTOS, GRACIAS_TRADING_WEEK, MARCAS_V2, PAGINAS_DE_CAMPANA,
)
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
        self.assertIn('cuerpo.lead_phone = tel;', js)
        # Y el aviso de error se busca por id, no por clase.
        self.assertIn('id="aviso"', html)

    def test_y_sigue_mandandose_donde_si_se_pide(self):
        # El campo pasó a ser opcional para la Trading Week, que solo recoge
        # nombre y correo. La comprobación es que el teléfono siga viajando
        # donde sí se pide, que es lo que se rompería al hacerlo opcional.
        js = (Path(__file__).resolve().parents[2]
              / 'calendario' / 'static' / 'js' / 'evento-registro.js').read_text(encoding='utf-8')
        self.assertIn('if (campoTel) {', js)
        self.assertIn('cuerpo.lead_phone_prefix = prefijo;', js)
        self.assertIn('cuerpo.lead_country = pais;', js)


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
        ('www.conquerfinance.com', '/evento/pildoras-evento-1'),
        ('www.conquerfinance.com', '/evento/pildoras-evento-2'),
        ('www.conquerfinance.com', '/evento/pildoras-evento-3'),
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
        for clave in ('evento-testimonios', 'bitacora',
                      'pildoras-evento-1', 'pildoras-evento-2', 'pildoras-evento-3'):
            self.assertIsNone(PAGINAS_DE_CAMPANA[clave]['funnel'], clave)

    def test_llevan_su_gtm_y_su_consentimiento(self):
        # Que no recojan datos no las exime de medir ni de pedir permiso.
        for host, ruta, st in (('www.conquerblocks.com', '/evento/evento-testimonios', '5PK5LTG'),
                               ('www.conquerlanguages.com', '/eventos/bitacora', 'MPB7S5C7'),
                               ('www.conquerfinance.com', '/evento/pildoras-evento-2', 'MXTDVVBG')):
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


class LasTresPildorasTest(TestCase):
    """Las píldoras que precalientan la Trading Week de Finance.

    Se recuperaron de web.archive.org: el dominio devuelve 404 desde hace
    meses, así que el archivo es la única fuente. Estos tests fijan lo que se
    leyó de él, porque no hay original vivo contra el que volver a comparar.
    """

    RUTAS = ('/evento/pildoras-evento-1', '/evento/pildoras-evento-2',
             '/evento/pildoras-evento-3')

    def _html(self, n):
        return self.client.get(f'/evento/pildoras-evento-{n}',
                               HTTP_HOST='www.conquerfinance.com').content.decode()

    def test_cada_una_lleva_su_video(self):
        guids = ('1806c327-dbfa-4ac4-9c81-bcc8d6240572',
                 'd9f08fbc-1782-44e2-bbb8-5194b05db850',
                 'b4bb5c13-b44d-4cfe-8c45-efb329b15149')
        for n, guid in enumerate(guids, start=1):
            html = self._html(n)
            # Biblioteca 185796: la de Finance, distinta de las de Blocks (135359)
            # y Languages (348662).
            self.assertIn(f'iframe.mediadelivery.net/embed/185796/{guid}', html, n)
            self.assertEqual(html.count('iframe.mediadelivery.net/embed/'), 1, n)

    def test_van_numeradas_y_con_su_titular(self):
        for n, titular in ((1, 'DESCUBRE LA SITUACIÓN ECONÓMICA ACTUAL'),
                           (2, 'QUÉ ES EL TRADING'),
                           (3, 'LOS 3 PERFILES DE PERSONAS')):
            html = self._html(n)
            self.assertIn(f'Píldora Nº{n}', html, n)
            self.assertIn(titular, html, n)

    def test_cada_una_enlaza_a_las_otras_dos(self):
        for n in (2, 3):
            html = self._html(n)
            otras = [o for o in (1, 2, 3) if o != n]
            for o in otras:
                self.assertIn(f'href="/evento/pildoras-evento-{o}"', html, (n, o))
            # Dos tarjetas: la imagen enlazada y el botón, por cada una.
            self.assertEqual(html.count('YA DISPONIBLE'), 2, n)

    def test_la_primera_no_enseña_ninguna(self):
        # En el original su contenedor llevaba `display: none`, ya en el volcado
        # de abril. Se replica en vez de "arreglarlo": no sabemos si fue a
        # propósito, y añadir enlaces que nadie vio es inventar.
        html = self._html(1)
        self.assertNotIn('YA DISPONIBLE', html)
        self.assertEqual(PAGINAS_DE_CAMPANA['pildoras-evento-1']['tarjetas'], ())

    def test_los_parrafos_conservan_sus_negritas(self):
        # Van con `|safe` porque el texto trae `<strong>`; si se escapara, el
        # visitante leería las etiquetas.
        self.assertIn('<strong>Trading Week</strong>', self._html(1))
        self.assertNotIn('&lt;strong&gt;', self._html(1))

    def test_las_tarjetas_se_ven_aunque_no_haya_javascript(self):
        # La animación las oculta desde JS. Si se ocultaran en el HTML, un fallo
        # del script las dejaría invisibles para siempre.
        html = self._html(2)
        self.assertIn('<div class="tarjeta">', html)
        self.assertNotIn('<div class="tarjeta oculta">', html)

    def test_salen_en_el_panel(self):
        panel = self.client.get('/funnels/').content.decode()
        for n in (1, 2, 3):
            self.assertIn(f'Pildoras-evento-{n}', panel, n)


class LaTradingWeekTest(TestCase):
    """La landing de registro de la Trading Week de Finance.

    Recuperada de web.archive.org (volcado de junio de 2025); el dominio
    devuelve 404. Es la segunda de campaña que recoge datos, y la única con
    test A/B.
    """

    def _html(self, **extra):
        return self.client.get('/trading-week-2025', HTTP_HOST='www.conquerfinance.com',
                               **extra).content.decode()

    def test_responde_en_la_raiz_del_dominio(self):
        # No cuelga de /evento/ como las de Blocks: su URL era la de la raíz.
        r = self.client.get('/trading-week-2025', HTTP_HOST='www.conquerfinance.com')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(PAGINAS_DE_CAMPANA['trading-week-2025']['ruta'], 'trading-week-2025')

    def test_recoge_nombre_y_correo_pero_no_telefono(self):
        html = self._html()
        self.assertIn('id="formEvento"', html)
        self.assertIn('name="fullname"', html)
        self.assertIn('name="email"', html)
        # El original no lo pedía, y el script de registro tiene que aguantarlo.
        self.assertNotIn('id="phoneLocal"', html)

    def test_lleva_embebida_su_pantalla_de_gracias(self):
        # Se cambia sin recargar, así que el bloque viaja en la propia página.
        # A cuál va, en `LaGraciasDeLaTradingWeekTest`.
        self.assertIn('id="gracias-evento"', self._html())

    def test_el_titular_y_el_codigo_de_funnel_van_a_la_par(self):
        # El código lleva la letra de la variante pegada. Si se sortearan por
        # separado —el titular en servidor y la letra en cliente, como hacía el
        # original— el CRM podría acabar con un lead atribuido al titular que no
        # se enseñó.
        titulares = {'a': 'Convierte el trading en tu fuente de ingresos extra',
                     'b': 'Descubre el método de trading respaldado'}
        vistas = set()
        for _ in range(40):
            html = self._html()
            for letra, titular in titulares.items():
                if f'funnel: "cf\\u002DTradingWeek4\\u002D{letra}"' in html:
                    self.assertIn(titular, html, letra)
                    vistas.add(letra)
        # 40 tiradas a cara o cruz: que salgan las dos es prácticamente seguro.
        self.assertEqual(vistas, {'a', 'b'})

    def test_sus_leads_son_de_lanzamiento_con_variante_y_sin_ella(self):
        # Sin esto se irían por el pipeline completo del funnel: Supabase,
        # conversiones y todo lo que estas páginas no deben disparar.
        for codigo in ('cf-TradingWeek4', 'cf-TradingWeek4-a', 'cf-TradingWeek4-b'):
            self.assertTrue(es_lead_de_lanzamiento(Lead(funnel=codigo)), codigo)

    def test_no_arrastra_los_bloques_que_el_original_tenia_ocultos(self):
        # Dos secciones de la plantilla de Webflow iban con `display: none`: una
        # de beneficios con el Lorem Ipsum en inglés y otra de «Nos has visto
        # en…» con logos de ejemplo. La segunda, además, presumiría de
        # apariciones en medios que no existen.
        html = self._html()
        self.assertNotIn('This is some text inside of a div block', html)
        self.assertNotIn('Nos has visto en', html)
        self.assertNotIn('twitch-logo', html)

    def test_lleva_su_gtm_su_consentimiento_y_su_doctype(self):
        html = self._html(HTTP_CF_IPCOUNTRY='ES')
        self.assertIn("st = 'MXTDVVBG'", html)
        self.assertIn('id="cqx-consent"', html)
        self.assertTrue(html.lstrip().lower().startswith('<!doctype html>'))

    def test_sale_en_el_panel_con_su_gracias_y_sus_variantes(self):
        # El panel es donde se mira qué hay publicado. Las pantallas de gracias
        # no salían, y desde que hay dos distintas en `/grupos-comunidad` no
        # había forma de saber cuál mira cada página.
        panel = self.client.get('/funnels/').content.decode()
        self.assertIn('Registro Trading Week 2025', panel)
        self.assertIn('/grupos-comunidad?escuela=conquer-finance', panel)
        self.assertIn('/grupos-comunidad?escuela=conquer-languages', panel)
        # Y que el código lleva variante, que es lo que llega al CRM.
        self.assertIn('+ variante', panel)

    def test_el_panel_enseña_la_gracias_de_cada_pantalla_de_lanzamiento(self):
        panel = self.client.get('/funnels/').content.decode()
        self.assertIn('/evento/gracias-comunidad?escuela=conquer-blocks', panel)
        self.assertIn('/evento/gracias-comunidad?escuela=conquer-finance', panel)


class LaGraciasDeLaTradingWeekTest(TestCase):
    """La Trading Week NO acaba en la pantalla de gracias de Finance.

    El original mandaba a `conquerfinance.com/grupos-comunidad`, que era una
    página propia con el grupo de WhatsApp de esa edición —`chat.wapp.ly/eEZ90a`,
    no el de Blocks que reutilizan las pantallas de lanzamiento—. Hoy esa URL
    redirige a la home, así que se recuperó del archivo.
    """

    def _tw(self):
        return self.client.get('/trading-week-2025',
                               HTTP_HOST='www.conquerfinance.com').content.decode()

    def _gracias(self, host):
        return self.client.get('/grupos-comunidad', HTTP_HOST=host).content.decode()

    def test_la_landing_manda_a_grupos_comunidad(self):
        html = self._tw()
        self.assertIn(r'gracias: "/grupos\u002Dcomunidad"', html)
        # Y no a la de las pantallas de lanzamiento de Finance.
        self.assertNotIn(r'gracias: "/evento/gracias\u002Dcomunidad"', html)

    def test_no_manda_al_enlace_muerto_de_esa_edicion(self):
        # El grupo del volcado, `chat.wapp.ly/eEZ90a`, hoy redirige a winna.com,
        # un casino online: el acortador se reutilizó desde 2025. Mandar ahí a
        # quien acaba de registrarse en una escuela de finanzas es peor que no
        # mandarlo a ningún sitio.
        for html in (self._tw(), self._gracias('www.conquerfinance.com')):
            self.assertNotIn('wapp.ly', html)
            self.assertNotIn('winna.com', html)
            # Tampoco se le encasqueta el grupo de otra marca.
            self.assertNotIn('cb.conquerx.com/1Qt1ef', html)

    def test_sin_grupo_no_hay_boton_ni_salto_automatico(self):
        html = self._gracias('www.conquerfinance.com')
        self.assertNotIn('class="boton"', html)
        # El temporizador se arranca igual, pero se corta solo al no haber
        # destino; lo que no puede haber es un botón a ninguna parte.
        self.assertIn('if (!destino) return;', html)

    def test_pero_la_pantalla_se_sigue_sirviendo(self):
        r = self.client.get('/grupos-comunidad', HTTP_HOST='www.conquerfinance.com')
        self.assertEqual(r.status_code, 200)
        self.assertIn('Trading Week 2025', r.content.decode())

    def test_la_url_responde_por_su_cuenta(self):
        r = self.client.get('/grupos-comunidad', HTTP_HOST='www.conquerfinance.com')
        self.assertEqual(r.status_code, 200)
        self.assertIn('<title>Grupos Comunidad</title>', r.content.decode())

    def test_el_mismo_path_sigue_sirviendo_la_de_languages(self):
        # `/grupos-comunidad` lo comparten las dos marcas; se resuelve por
        # dominio. Si esto se rompe, Languages pierde su pantalla de gracias.
        html = self._gracias('www.conquerlanguages.com')
        self.assertIn('cl.conquerx.com/5P9e7L', html)
        self.assertNotIn('chat.wapp.ly/eEZ90a', html)

    def test_fuera_de_los_dominios_de_marca_sigue_saliendo_la_de_languages(self):
        # Es como se previsualiza (calendar.conquerx.com) y como estaba antes de
        # que Finance tuviera la suya: la ruta llevaba la escuela clavada. Si
        # esto pasa a 404, la pantalla de gracias de Languages deja de poder
        # verse fuera de su dominio.
        for host in ('calendar.conquerx.com', 'www.conquerblocks.com'):
            r = self.client.get('/grupos-comunidad', HTTP_HOST=host)
            self.assertEqual(r.status_code, 200, host)
            self.assertIn('cl.conquerx.com/5P9e7L', r.content.decode(), host)

    def test_salta_sola_al_grupo_a_los_quince_segundos(self):
        html = self._gracias('www.conquerfinance.com')
        self.assertIn('iniciarSaltoWhatsApp', html)
        self.assertIn('15000', html)

    def test_va_sobre_negro_para_que_se_vea_el_logo(self):
        # Su fondo es una textura de manchas azules pensada para ir sobre negro.
        # Sin el color de debajo queda casi blanca y el logo, que es blanco,
        # desaparece.
        html = self._gracias('www.conquerfinance.com')
        self.assertIn('background-color:#000', html)
        self.assertIn('fondo-blur.avif', html)

    def test_lleva_gtm_consentimiento_y_doctype(self):
        html = self.client.get('/grupos-comunidad', HTTP_HOST='www.conquerfinance.com',
                               HTTP_CF_IPCOUNTRY='ES').content.decode()
        self.assertIn("st = 'MXTDVVBG'", html)
        self.assertIn('id="cqx-consent"', html)
        self.assertTrue(html.lstrip().lower().startswith('<!doctype html>'))


@override_settings(FUNNEL_PUBLIC_BASE={
    'conquer-blocks': 'https://www.conquerblocks.com',
    'conquer-finance': 'https://www.conquerfinance.com',
    # Languages sigue detrás de /preview para las etapas del funnel.
    'conquer-languages': 'https://www.conquerlanguages.com/preview',
})
class ElPanelApuntaAlDominioDeCadaMarcaTest(TestCase):
    """Las páginas de evento van en la raíz del dominio, no bajo /preview.

    `FUNNEL_PUBLIC_BASE` lleva a Languages a `.../preview` porque sus etapas de
    funnel siguen ahí en Cloudflare. Sus páginas de evento no: se sirven en la
    raíz. El panel las listaba con el prefijo, así que llevaba a revisar una URL
    distinta de la que recibe el tráfico —y desde ahí la de gracias salía
    también con `/preview`, porque el prefijo se propaga solo.
    """

    def _enlaces(self):
        html = self.client.get('/funnels/').content.decode()
        tabla = html[html.index('Páginas de evento</h2>'):]
        return re.findall(r'href="([^"]+)"', tabla[:tabla.index('</table>')])

    def test_ninguna_pagina_de_evento_lleva_el_prefijo_del_funnel(self):
        for url in self._enlaces():
            self.assertNotIn('/preview', url, url)

    def test_cada_una_cuelga_del_dominio_de_su_marca(self):
        enlaces = self._enlaces()
        for esperado in ('https://www.conquerlanguages.com/cl-evento',
                         'https://www.conquerlanguages.com/eventos/bitacora',
                         'https://www.conquerfinance.com/trading-week-2025',
                         'https://www.conquerblocks.com/evento/evento-coding-week-eu'):
            self.assertIn(esperado, enlaces, esperado)

    def test_y_la_tabla_de_funnels_si_lo_conserva(self):
        # Ahí el prefijo es real: esas rutas SÍ están detrás de /preview.
        html = self.client.get('/funnels/').content.decode()
        funnels = html[:html.index('Páginas de evento</h2>')]
        self.assertIn('https://www.conquerlanguages.com/preview/', funnels)


class LaSegundaVersionTest(TestCase):
    """Las páginas de evento con el diseño de la web actual, en `?v=2`.

    Blocks y Finance rehicieron sus webs con el sistema "paperboard" —papel
    crema, rasgado a negro, CTA de canto pixelado—; estas páginas se migraron
    con la identidad anterior y desentonaban al lado del sitio. La primera
    versión NO se borra: se sigue sirviendo por defecto y `?v=2` enseña la
    nueva, para poder compararlas sin desplegar nada.

    Languages queda fuera a propósito: su web sigue con el diseño anterior, así
    que dársela la descolgaría de su propio sitio.
    """

    CON_SEGUNDA = (
        ('www.conquerblocks.com', '/evento/evento-coding-week-eu'),
        ('www.conquerblocks.com', '/evento/evento-testimonios'),
        ('www.conquerfinance.com', '/evento/pildoras-evento-1'),
        ('www.conquerfinance.com', '/evento/pildoras-evento-2'),
        ('www.conquerfinance.com', '/evento/pildoras-evento-3'),
        ('www.conquerfinance.com', '/trading-week-2025'),
        ('www.conquerfinance.com', '/grupos-comunidad'),
    )

    def test_sin_el_parametro_se_sirve_la_de_siempre(self):
        for host, ruta in self.CON_SEGUNDA:
            html = self.client.get(ruta, HTTP_HOST=host).content.decode()
            self.assertNotIn('--papel:#fafafa', html, f'{host}{ruta}')

    def test_con_v2_se_sirve_la_nueva(self):
        for host, ruta in self.CON_SEGUNDA:
            html = self.client.get(ruta + '?v=2', HTTP_HOST=host).content.decode()
            self.assertIn('--papel:#fafafa', html, f'{host}{ruta}')

    def test_la_nueva_no_arrastra_la_paleta_vieja(self):
        # Negro con verde lima en Blocks, negro con azul en Finance: es lo que
        # chocaba con la web nueva.
        for host, ruta, viejo in (
                ('www.conquerblocks.com', '/evento/evento-testimonios', '#c8f169'),
                ('www.conquerfinance.com', '/evento/pildoras-evento-2', '#02bdf8'),
                ('www.conquerfinance.com', '/trading-week-2025', '#2827d6')):
            html = self.client.get(ruta + '?v=2', HTTP_HOST=host).content.decode()
            self.assertNotIn(viejo, html, f'{host}{ruta}')

    def test_las_que_no_tienen_segunda_ignoran_el_parametro(self):
        # La bitácora es de Languages, y la pantalla de evento de Blocks ya va
        # en paperboard: ninguna declara `plantilla_v2`.
        for host, ruta in (('www.conquerlanguages.com', '/eventos/bitacora'),
                           ('www.conquerblocks.com', '/evento/evento-online')):
            con = self.client.get(ruta + '?v=2', HTTP_HOST=host)
            sin = self.client.get(ruta, HTTP_HOST=host)
            self.assertEqual(con.status_code, 200, f'{host}{ruta}')
            self.assertEqual(con.content, sin.content, f'{host}{ruta}')

    def test_languages_no_tiene_marca_nueva(self):
        self.assertEqual(set(MARCAS_V2), {'conquer-blocks', 'conquer-finance'})

    def test_la_nueva_conserva_el_formulario_y_su_codigo(self):
        # Lo que cambia es el envoltorio; el lead tiene que salir igual.
        html = self.client.get('/evento/evento-coding-week-eu?v=2',
                               HTTP_HOST='www.conquerblocks.com').content.decode()
        self.assertIn('id="formEvento"', html)
        self.assertIn('id="phoneLocal"', html)
        self.assertIn(r'funnel: "cb\u002Dcodingweek5\u002Deu"', html)
        self.assertIn('id="gracias-evento"', html)

    def test_y_en_la_trading_week_tambien_su_variante_y_su_gracias(self):
        html = self.client.get('/trading-week-2025?v=2',
                               HTTP_HOST='www.conquerfinance.com').content.decode()
        self.assertIn('id="formEvento"', html)
        self.assertRegex(html, r'funnel: "cf\\u002DTradingWeek4\\u002D[ab]"')
        self.assertIn(r'gracias: "/grupos\u002Dcomunidad"', html)

    def test_la_gracias_embebida_es_la_misma_que_la_de_su_url(self):
        # Se veían distintas: la página embebía la maqueta de Blocks y su URL
        # servía la de tres tarjetas. Cada versión tiene que casar consigo misma.
        # Se compara por el titular, que no depende de que haya grupo puesto.
        # En minúsculas porque cada versión escribe el «¡obligatorio!» distinto.
        marca = 'queda un último paso para reservar tu entrada'
        for sufijo in ('', '?v=2'):
            registro = self.client.get('/trading-week-2025' + sufijo,
                                       HTTP_HOST='www.conquerfinance.com').content.decode()
            suelta = self.client.get('/grupos-comunidad' + sufijo,
                                     HTTP_HOST='www.conquerfinance.com').content.decode()
            self.assertIn(marca, registro.lower(), sufijo)
            self.assertIn(marca, suelta.lower(), sufijo)
        self.assertEqual(GRACIAS_TRADING_WEEK['plantilla_v2'],
                         'pages/public/evento/gracias-v2.html')

    def test_las_pildoras_se_enlazan_entre_ellas_sin_salirse_de_la_version(self):
        # Si el enlace no llevara `?v=2`, pulsarlo devolvía a la versión vieja.
        html = self.client.get('/evento/pildoras-evento-2?v=2',
                               HTTP_HOST='www.conquerfinance.com').content.decode()
        self.assertIn('/evento/pildoras-evento-1?v=2', html)
        self.assertIn('/evento/pildoras-evento-3?v=2', html)

    def test_un_valor_raro_no_cuenta_como_segunda(self):
        for valor in ('3', 'dos', '', 'true'):
            html = self.client.get(f'/evento/evento-testimonios?v={valor}',
                                   HTTP_HOST='www.conquerblocks.com').content.decode()
            self.assertNotIn('--papel:#fafafa', html, valor)


class LaListaDePrefijosTest(TestCase):
    """El selector de prefijo del formulario se alimenta de un JSON.

    Traía tres errores que llegaban al visitante: dos banderas que no existen
    —y salían rotas en la lista— y dos prefijos con el `+` duplicado, que es lo
    que se guarda en `lead_phone_prefix` y viaja al CRM.
    """

    def _paises(self):
        import json
        ruta = (Path(__file__).resolve().parents[2] / 'calendario' / 'static' / 'js'
                / 'paises-evento.json')
        return json.loads(ruta.read_text(encoding='utf-8'))

    def test_ningun_prefijo_lleva_el_mas_repetido(self):
        malos = [p for p in self._paises() if p['prefijo'].count('+') != 1
                 or not p['prefijo'].startswith('+')]
        self.assertEqual(malos, [])

    def test_todos_los_codigos_son_iso_de_dos_letras(self):
        # La bandera se pide a flagcdn con este código: si no es de dos letras
        # —`SXM` en vez de `SX`— la imagen sale rota.
        malos = [p for p in self._paises()
                 if len(p['iso2']) != 2 or not p['iso2'].isalpha() or not p['iso2'].isupper()]
        self.assertEqual(malos, [])

    def test_no_quedan_paises_que_ya_no_existen(self):
        # Las Antillas Neerlandesas se disolvieron en 2010 y su +599 lo tiene
        # Curazao, que sigue en la lista.
        codigos = {p['iso2'] for p in self._paises()}
        self.assertNotIn('AN', codigos)
        self.assertIn('CW', codigos)


class NingunGrupoDeWhatsappRoto(TestCase):
    """Los enlaces de grupo que se sirven tienen que ser de WhatsApp.

    El de la Trading Week dejó de serlo —el acortador acabó apuntando a un
    casino— y estuvo a punto de irse a producción. Esta comprobación es de
    formato, no de red: fija que solo se sirven los acortadores propios, que son
    los que sí controlamos.
    """

    def test_solo_se_sirven_acortadores_propios(self):
        from calendario.funnels.evento_views import GRACIAS, GRACIAS_TRADING_WEEK
        for nombre, ficha in list(GRACIAS.items()) + [('trading-week', GRACIAS_TRADING_WEEK)]:
            url = ficha.get('whatsapp') or ''
            if not url:
                continue  # sin grupo configurado: la pantalla ya lo aguanta
            self.assertRegex(url, r'^https://(cb|cl|cf|cg)\.conquerx\.com/', nombre)
