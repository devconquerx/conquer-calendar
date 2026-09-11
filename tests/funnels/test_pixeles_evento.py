# -*- coding: utf-8 -*-
"""Los píxeles a código de las pantallas de evento (lanzamientos).

El registro de un lanzamiento se contaba como un lead de venta: estas páginas
cargaban el contenedor de la marca, cuyo trigger de lead es el del funnel, así
que Google, Meta y TikTok recibían la misma conversión por la que pujan las
campañas de venta. Lo que se fija aquí es la separación: quién lleva contenedor
y quién píxeles, contra qué acción de conversión dispara cada marca, y que el
identificador del registro viaje al CRM y a los píxeles a la vez — sin él, el
evento del navegador y el de la API de conversiones se cuentan dos veces.
"""
from pathlib import Path

from django.test import TestCase

RAIZ = Path(__file__).resolve().parents[2]
JS = (RAIZ / 'calendario' / 'static' / 'js' / 'pixeles-evento.js').read_text(encoding='utf-8')
REGISTRO = (RAIZ / 'calendario' / 'static' / 'js' / 'evento-registro.js').read_text(encoding='utf-8')

# Las acciones "Lead Lanzamiento <XX> Web" de cada cuenta, creadas solo para
# estas pantallas. Si alguien las cambia por las del funnel, el problema vuelve.
CONVERSIONES = {
    'conquer-blocks': ('AW-725899560', 'AW-725899560/2YIZCL-Iz_QcEKiykdoC'),
    'conquer-languages': ('AW-16956085244', 'AW-16956085244/kERXCMKIz_QcEPynpZU_'),
    'conquer-finance': ('AW-16625277654', 'AW-16625277654/bJU2CPmU0_QcENa1xvc9'),
}

# Página que recoge registros de cada marca, con el contenedor que llevaba antes.
PANTALLAS = (
    ('www.conquerblocks.com', '/evento/evento-online', 'conquer-blocks', '5PK5LTG'),
    ('www.conquerfinance.com', '/evento/evento-online', 'conquer-finance', 'MXTDVVBG'),
    ('www.conquerlanguages.com', '/cl-evento', 'conquer-languages', 'MPB7S5C7'),
)


class LasQueRecogenDatosNoLlevanContenedorTest(TestCase):

    def test_pantallas_de_lanzamiento(self):
        for host, ruta, escuela, st in PANTALLAS:
            html = self.client.get(ruta, HTTP_HOST=host).content.decode()
            ads, conversion = CONVERSIONES[escuela]
            self.assertNotIn(f"st = '{st}'", html, f'{host}{ruta}')
            self.assertIn(f"ads: '{ads}'", html, f'{host}{ruta}')
            self.assertIn(f"ads_conversion: '{conversion}'", html, f'{host}{ruta}')

    def test_paginas_de_gracias(self):
        # Se llega a ellas sin recargar, pero también responden por su URL: si
        # llevaran contenedor, una visita directa dispararía el lead del funnel.
        for host, ruta, escuela in (('www.conquerblocks.com', '/evento/gracias-comunidad', 'conquer-blocks'),
                                    ('www.conquerlanguages.com', '/grupos-comunidad', 'conquer-languages')):
            html = self.client.get(ruta, HTTP_HOST=host).content.decode()
            self.assertNotIn('gtm.start', html, f'{host}{ruta}')
            self.assertIn(f"ads: '{CONVERSIONES[escuela][0]}'", html, f'{host}{ruta}')

    def test_las_informativas_tampoco(self):
        # El corte es "página de evento", no "página con formulario": ninguna de
        # las diez lleva contenedor. No tienen registro que disparar, pero sus
        # píxeles mantienen GA4, Meta y TikTok midiendo el tráfico.
        for host, ruta, escuela in (('www.conquerblocks.com', '/evento/evento-testimonios', 'conquer-blocks'),
                                    ('www.conquerlanguages.com', '/eventos/bitacora', 'conquer-languages'),
                                    ('www.conquerfinance.com', '/evento/pildoras-evento-1', 'conquer-finance'),
                                    ('www.conquerfinance.com', '/evento/pildoras-evento-2', 'conquer-finance'),
                                    ('www.conquerfinance.com', '/evento/pildoras-evento-3', 'conquer-finance')):
            html = self.client.get(ruta, HTTP_HOST=host).content.decode()
            self.assertNotIn('gtm.start', html, f'{host}{ruta}')
            self.assertIn(f"ads: '{CONVERSIONES[escuela][0]}'", html, f'{host}{ruta}')

    def test_las_paginas_de_campana_con_formulario(self):
        for host, ruta, escuela in (('www.conquerblocks.com', '/evento/evento-coding-week-eu', 'conquer-blocks'),
                                    ('www.conquerfinance.com', '/trading-week-2025', 'conquer-finance')):
            html = self.client.get(ruta, HTTP_HOST=host).content.decode()
            self.assertNotIn('gtm.start', html, f'{host}{ruta}')
            self.assertIn(f"ads_conversion: '{CONVERSIONES[escuela][1]}'", html, f'{host}{ruta}')

    def test_el_funnel_conserva_su_contenedor(self):
        # Fuera de las páginas de evento no cambia nada: el corte es solo este.
        from calendario.funnels.context_processors import get_gtm_config
        self.assertEqual(get_gtm_config('conquer-blocks')['id'], 'GTM-5PK5LTG')


class CadaMarcaConSuPixelTest(TestCase):

    def test_no_se_cruzan_los_pixeles_entre_marcas(self):
        esperado = {
            'conquer-blocks': ('921361326426436', 'CTMK2ORC77U1LI1DFAD0'),
            'conquer-finance': ('1011283009921986', 'D03U523C77U9QS83BBI0'),
            'conquer-languages': ('627205843180202', 'CVIQE0JC77U02UO7SEC0'),
        }
        for host, ruta, escuela, _ in PANTALLAS:
            html = self.client.get(ruta, HTTP_HOST=host).content.decode()
            meta, tiktok = esperado[escuela]
            self.assertIn(f"meta: '{meta}'", html, f'{host}{ruta}')
            self.assertIn(f"tiktok: '{tiktok}'", html, f'{host}{ruta}')
            for otra, (m, t) in esperado.items():
                if otra != escuela:
                    self.assertNotIn(f"meta: '{m}'", html, f'{host}{ruta}')
                    self.assertNotIn(f"tiktok: '{t}'", html, f'{host}{ruta}')

    def test_ga4_sigue_midiendo_sin_el_contenedor(self):
        # Quitar GTM no puede sacar estas páginas de los informes.
        for host, ruta, ga4 in (('www.conquerblocks.com', '/evento/evento-online', 'G-LNCT8EQRDT'),
                                ('www.conquerfinance.com', '/evento/evento-online', 'G-9PGHQW52XM'),
                                ('www.conquerlanguages.com', '/cl-evento', 'G-FJBW5107MW')):
            html = self.client.get(ruta, HTTP_HOST=host).content.decode()
            self.assertIn(f"ga4: '{ga4}'", html, f'{host}{ruta}')


class ElEventoDeLanzamientoEsPropioTest(TestCase):

    def test_meta_y_tiktok_no_usan_el_evento_del_funnel(self):
        for host, ruta, _, _ in PANTALLAS:
            html = self.client.get(ruta, HTTP_HOST=host).content.decode()
            self.assertIn("evento_meta: 'LeadLanzamiento'", html, f'{host}{ruta}')
            self.assertIn("evento_tiktok: 'LeadLanzamiento'", html, f'{host}{ruta}')
        # El del funnel es `Lead` en Meta y `SubmitForm` en TikTok: con
        # `trackCustom` y un nombre propio no hay forma de caer en ellos.
        self.assertIn("fbq('trackCustom', CFG.evento_meta", JS)
        self.assertNotIn("'Lead'", JS)
        self.assertNotIn("'SubmitForm'", JS)

    def test_el_mismo_identificador_va_al_crm_y_a_los_pixeles(self):
        # Es lo que deduplica el evento del navegador contra el que manda la
        # API de conversiones desde el servidor.
        self.assertIn('event_id: eventId', REGISTRO)
        self.assertIn('window.cqxPixeles.lead(', REGISTRO)
        self.assertIn('transaction_id: datos.event_id', JS)
        self.assertIn('eventID: datos.event_id', JS)
        self.assertIn('event_id: datos.event_id', JS)

    def test_la_conversion_se_dispara_antes_de_cambiar_de_pantalla(self):
        # Si fallara al pintar la de gracias, el registro ya está contado.
        cuerpo = REGISTRO[REGISTRO.index("decir('¡Listo!"):]
        self.assertLess(cuerpo.index('cqxPixeles'), cuerpo.index('irAGracias()'))


class MetaYTikTokEsperanAlPermisoTest(TestCase):
    """Consent Mode solo lo entienden las etiquetas de Google."""

    def test_no_se_cargan_hasta_que_hay_marketing(self):
        # Se cargan dentro de `concederMarketing`, y a esa solo se llega con el
        # permiso dado.
        cuerpo = JS[JS.index('function concederMarketing'):JS.index('// ----------------------------------------------------- carga diferida')]
        self.assertIn('cargarMeta();', cuerpo)
        self.assertIn('cargarTikTok();', cuerpo)
        self.assertIn("w.addEventListener('cqx:consent'", JS)

    def test_el_consentimiento_avisa_a_quien_no_pasa_por_gtm(self):
        consent_js = (RAIZ / 'calendario' / 'static' / 'js' / 'consentimiento.js').read_text(encoding='utf-8')
        self.assertIn("new CustomEvent('cqx:consent'", consent_js)

    def test_los_eventos_pendientes_no_se_pierden(self):
        # Si alguien se registra antes de aceptar, el evento sale en cuanto
        # acepte en vez de perderse.
        self.assertIn('pendientes.push(fn)', JS)
        self.assertIn('cola.forEach', JS)


class NoSeCargaEnElHeadTest(TestCase):
    """El LCP de estas landings es la tarjeta del formulario."""

    def test_los_scripts_se_inyectan_al_primer_gesto_o_en_idle(self):
        self.assertIn('requestIdleCallback', JS)
        self.assertIn("'pointerdown', 'keydown', 'touchstart', 'scroll', 'mousemove'", JS)

    def test_el_include_no_es_sincrono(self):
        html = self.client.get('/evento/evento-online', HTTP_HOST='www.conquerblocks.com').content.decode()
        self.assertIn("js/pixeles-evento.js", html)
        bloque = html[html.index('js/pixeles-evento.js') - 200:html.index('js/pixeles-evento.js') + 100]
        self.assertIn('defer', bloque)
