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


class ElPaisLlegaPorSuCabeceraTest(TestCase):
    """El país NO viaja en `CF-IPCountry`, y confundirse cuesta caro.

    Los dominios de marca entran por un Worker de Cloudflare que reenvía a
    `calendar.conquerx.com`, que está fuera de Cloudflare. Ahí `CF-IPCountry` no
    existe: Cloudflare solo la añade proxeando a orígenes de sus zonas, y un
    Worker no puede fijarla a mano porque los nombres `CF-` los gestiona ella.
    Se perdía por el camino y a TODO el mundo —LATAM incluido— le salía el aviso
    bloqueante de Europa, porque sin país se pide permiso por defecto.
    """

    def _modo(self, **cabeceras):
        html = self.client.get('/evento/evento-online', HTTP_HOST='www.conquerblocks.com',
                               **cabeceras).content.decode()
        return 'Al continuar navegando' in html and 'implicito' or 'explicito'

    def test_es_la_que_reenvia_el_worker(self):
        self.assertEqual(consentimiento.CABECERA_PAIS, 'X-Visitor-Country')

    def test_con_ella_latam_recibe_el_implicito(self):
        self.assertEqual(self._modo(HTTP_X_VISITOR_COUNTRY='VE'), 'implicito')

    def test_y_europa_el_explicito(self):
        self.assertEqual(self._modo(HTTP_X_VISITOR_COUNTRY='ES'), 'explicito')

    def test_se_sigue_aceptando_la_de_cloudflare(self):
        # Por si el origen acaba detrás de Cloudflare y la pone ella.
        self.assertEqual(self._modo(HTTP_CF_IPCOUNTRY='VE'), 'implicito')

    def test_la_suya_manda_sobre_la_de_cloudflare(self):
        self.assertEqual(self._modo(HTTP_X_VISITOR_COUNTRY='VE', HTTP_CF_IPCOUNTRY='ES'),
                         'implicito')

    def test_el_prefijo_del_telefono_sale_del_mismo_sitio(self):
        # Se preselecciona en servidor con el país; sin él, el JS acaba
        # preguntando por IP a un tercero.
        html = self.client.get('/evento/evento-online', HTTP_HOST='www.conquerblocks.com',
                               HTTP_X_VISITOR_COUNTRY='VE').content.decode()
        self.assertIn('data-pais="VE"', html)

    def test_la_respuesta_varia_con_ella(self):
        # Sin `Vary` una caché intermedia serviría a un venezolano la página
        # cacheada para un español.
        vary = self.client.get('/evento/evento-online',
                               HTTP_HOST='www.conquerblocks.com')['Vary']
        self.assertIn('X-Visitor-Country', vary)


class AQuienSeLePreguntaTest(TestCase):
    """Dos regímenes distintos, porque la ley no es la misma.

    En el EEE, Reino Unido, Suiza y Brasil hace falta permiso previo: hasta que
    no se pulsa, no se activa nada. En LATAM y Estados Unidos el consentimiento
    es implícito y no se exige banner —California y compañía son de exclusión,
    no de consentimiento previo—, así que no se muestra nada, igual que hace
    Cookiebot hoy.
    """

    def _peticion(self, pais):
        return self.client.get(
            '/evento/evento-online', HTTP_HOST='www.conquerblocks.com',
            **({'HTTP_CF_IPCOUNTRY': pais} if pais else {})).wsgi_request

    def _aplica(self, pais):
        return consentimiento.aplica(self._peticion(pais))

    def _modo(self, pais):
        return consentimiento.modo(self._peticion(pais))

    def test_se_pregunta_en_la_union_europea(self):
        for pais in ('ES', 'DE', 'FR', 'IT', 'PT', 'IE'):
            self.assertTrue(self._aplica(pais), pais)
            self.assertEqual(self._modo(pais), 'explicito', pais)

    def test_y_tambien_donde_alcanza_el_rgpd_o_equivalente(self):
        # EEE, Reino Unido, Suiza y Brasil (LGPD, que también pide consentimiento).
        for pais in ('NO', 'IS', 'LI', 'GB', 'CH', 'BR'):
            self.assertTrue(self._aplica(pais), pais)
            self.assertEqual(self._modo(pais), 'explicito', pais)

    def test_en_latam_y_estados_unidos_el_aviso_no_bloquea(self):
        # También se muestra, pero con el otro modelo: informa y no exige pulsar.
        for pais in ('VE', 'MX', 'CO', 'AR', 'US', 'PE'):
            self.assertEqual(self._modo(pais), 'implicito', pais)
            self.assertTrue(self._aplica(pais), pais)

    def test_se_puede_forzar_cada_modo_para_revisarlos(self):
        # Sin esto no hay forma de ver el de Europa sin fingir una IP.
        peticion = self.client.get('/evento/evento-online?consent=eu',
                                   HTTP_HOST='www.conquerblocks.com',
                                   HTTP_CF_IPCOUNTRY='VE').wsgi_request
        self.assertEqual(consentimiento.modo(peticion), 'explicito')
        peticion = self.client.get('/evento/evento-online?consent=row',
                                   HTTP_HOST='www.conquerblocks.com',
                                   HTTP_CF_IPCOUNTRY='ES').wsgi_request
        self.assertEqual(consentimiento.modo(peticion), 'implicito')

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

    def test_donde_hace_falta_permiso_se_deniega_hasta_que_conteste(self):
        html = self._html('ES')
        self.assertIn("var inicial = (explicito && !guardado) ? 'denied' : 'granted'", html)
        self.assertIn('var explicito = true', html)

    def test_donde_es_implicito_se_concede_desde_el_principio(self):
        html = self._html('VE')
        self.assertIn('var explicito = false', html)
        # El aviso sale igual, pero sin bloquear.
        self.assertIn('var aplica = true', html)
        self.assertIn('Al continuar navegando, aceptas su uso', html)

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
            ('www.conquerlanguages.com', '/cl-evento', '#3e7f92'),
        ):
            html = self.client.get(ruta, HTTP_HOST=host, HTTP_CF_IPCOUNTRY='ES').content.decode()
            self.assertIn(f'--acento:{acento}', html, f'{host}{ruta}')

    def test_la_politica_de_privacidad_es_la_de_la_marca(self):
        html = self.client.get('/cl-evento', HTTP_HOST='www.conquerlanguages.com',
                               HTTP_CF_IPCOUNTRY='ES').content.decode()
        self.assertIn('conquerlanguages.com/politica-de-privacidad', html)

    def test_legal_tambien_tiene_la_suya(self):
        # Legal entra por el funnel, no por una pantalla de evento, y es la que
        # se olvida al repasar «las tres escuelas».
        html = self.client.get('/hub/registro-eu', HTTP_HOST='www.conquerlegal.com',
                               HTTP_CF_IPCOUNTRY='ES').content.decode()
        self.assertIn('id="cqx-consent"', html)
        self.assertIn('--acento:#0040FF', html)

    def test_ninguna_apunta_a_una_url_que_no_existe(self):
        # La de Legal cuelga de /legal/; sin ese tramo da 404 y el enlace del
        # banner —que es el que ampara el consentimiento— lleva a ninguna parte.
        from calendario.funnels.consentimiento import MARCAS
        esperado = {
            'conquer-blocks': 'https://www.conquerblocks.com/legal/politica-de-privacidad',
            'conquer-finance': 'https://www.conquerfinance.com/legal/politica-de-privacidad',
            'conquer-languages': 'https://www.conquerlanguages.com/politica-de-privacidad',
            'conquer-legal': 'https://www.conquerlegal.com/legal/politica-de-privacidad',
            # La corporativa la cuelga de la raíz, sin /legal/ (comprobado: 200).
            'conquerx': 'https://www.conquerx.com/politica-de-privacidad',
        }
        self.assertEqual({e: m['politica_url'] for e, m in MARCAS.items()}, esperado)

    def test_la_tipografia_llega_entera_al_css(self):
        # 'Funnel Display' lleva comilla porque tiene un espacio, y el autoescape
        # de Django la convierte en `&#x27;`: la declaración se rompe entera y el
        # banner acaba con la fuente por defecto del navegador. Pasó en
        # producción en Blocks, Finance y Legal a la vez.
        for host, ruta in (('www.conquerblocks.com', '/evento/evento-online'),
                           ('www.conquerfinance.com', '/evento/evento-online'),
                           ('www.conquerlegal.com', '/hub/registro-eu')):
            html = self.client.get(ruta, HTTP_HOST=host, HTTP_CF_IPCOUNTRY='ES').content.decode()
            self.assertIn("font-family:'Funnel Display',Arial,sans-serif", html, f'{host}{ruta}')
            self.assertNotIn('font-family:&#x27;', html, f'{host}{ruta}')


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

    def test_fuera_de_la_ue_sale_el_implicito(self):
        html = self._html()
        self.assertIn('var explicito = false', html)
        self.assertIn('Al continuar navegando, aceptas su uso', html)
        self.assertIn('>Entendido<', html)

    def test_con_el_sale_aunque_ya_se_hubiera_decidido(self):
        self.assertIn('var forzar = true', self._html('?debug=1'))

    def test_ignora_lo_ya_decidido(self):
        # Si no, aceptaría una vez y no volvería a salir en ese navegador.
        js = JS.read_text(encoding='utf-8')
        self.assertIn('cfg.forzar ? null : leer()', js)
        self.assertIn("&& !forzar", self._html('?debug=1'))

    def test_y_deniega_mientras_no_conteste_si_toca_pedir_permiso(self):
        # Forzado no puede significar "sácalo pero mide igual". Desde fuera de
        # la UE el modo sigue siendo implícito, así que se fuerza el de Europa
        # para comprobar el bloqueo.
        html = self._html('?debug=1&consent=eu')
        self.assertIn("var inicial = (explicito && !guardado)", html)
        self.assertIn('var explicito = true', html)

    def test_otro_valor_no_activa_el_forzado(self):
        for q in ('?debug=0', '?debug=true', '?debug='):
            self.assertIn('var forzar = false', self._html(q), q)


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

    def test_legal_tambien_va_en_carton_y_pixelado(self):
        # Su tema declara `paperboard: true` y no anula `buttonClip`, así que su
        # CTA es el mismo botón recortado que el de Blocks, en azul.
        html = self._html('www.conquerlegal.com', '/hub/registro-eu')
        self.assertIn('paperboard-texture', html.split('#cqx-consent .tarjeta{')[2])
        self.assertIn('clip-path:var(--pixel-clip)', html)

    def test_el_degradado_de_legal_se_copia_entero(self):
        # Tres paradas y en horizontal: aproximarlo con dos a 135deg daba otro
        # azul y otro sentido de barrido que el «Ver vídeo» de al lado.
        html = self._html('www.conquerlegal.com', '/hub/registro-eu')
        self.assertIn('linear-gradient(90deg,#3E76FF 0%,#1845D6 42%,#031464 100%)', html)

    def test_y_su_cta_lleva_el_borde_pixelado_y_su_degradado(self):
        for host, ruta, g1, g2 in (
            ('www.conquerblocks.com', '/evento/evento-online', '#ff4000', '#ff9800'),
            ('www.conquerfinance.com', '/evento/evento-online', '#aed916', '#3ac043'),
        ):
            html = self._html(host, ruta)
            self.assertIn('clip-path:var(--pixel-clip)', html, f'{host}{ruta}')
            self.assertIn(f'linear-gradient(135deg,{g1},{g2})', html, f'{host}{ruta}')

    def test_languages_se_queda_liso_y_cuadrado(self):
        html = self._html('www.conquerlanguages.com', '/cl-evento')
        # Su fondo es una foto: ni cartón ni píxeles.
        self.assertNotIn('paperboard-texture', html.split('id="cqx-consent"')[0].split('<style>')[-1])
        self.assertNotIn('clip-path:var(--pixel-clip)', html)
        # Botones cuadrados: `--radio` solo alimenta el `calc(var(--radio) - 2px)`
        # de los botones, así que 2px los deja a 0. Antes iba a 20 (píldoras de
        # 18), que no lo usa ni su web (2px) ni su embudo (0px).
        self.assertIn('--radio:2px', html)

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

    def test_tambien_queda_donde_el_consentimiento_es_implicito(self):
        # Ahí el aviso se cierra al seguir navegando, así que el icono es la
        # única forma de volver a abrirlo.
        self.assertIn('var aplica = true', self._html(pais='VE'))

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


class EsUnaBarraPegadaAbajoTest(TestCase):
    """No es una tarjeta flotante: es una barra de lado a lado.

    Ocupando todo el ancho, el texto y los botones caben en una fila y la
    barra baja de unos 190px a unos 85px en escritorio, que era el problema:
    flotando y estrecha, se comía media pantalla.
    """

    def _html(self):
        return self.client.get('/evento/evento-online', HTTP_HOST='www.conquerblocks.com',
                               HTTP_CF_IPCOUNTRY='ES').content.decode()

    def test_va_pegada_a_los_tres_bordes(self):
        self.assertIn('inset:auto 0 0 0', self._html())

    def test_la_tarjeta_ocupa_todo_y_sin_esquinas(self):
        html = self._html()
        self.assertIn('border-radius:0', html.split('#cqx-consent .tarjeta{')[1][:400])
        self.assertIn('border-top:1px solid var(--borde)', html)

    def test_texto_y_botones_comparten_fila(self):
        html = self._html()
        self.assertIn('class="fila-barra"', html)
        self.assertIn('#cqx-consent .fila-barra{', html)
        # El texto se estira y los botones se quedan a su ancho.
        self.assertIn('#cqx-consent .copia{flex:1 1 ', html)
        self.assertIn('#cqx-consent button{\n  flex:0 0 auto', html.replace('\r', ''))

    def test_en_movil_los_botones_no_se_apilan(self):
        # Apilados la barra se comía un tercio de la pantalla.
        html = self._html()
        movil = html[html.index('@media (max-width:480px)'):]
        self.assertNotIn('flex:1 1 100%', movil[:400])

    def test_el_panel_no_se_sale_de_la_pantalla(self):
        self.assertIn('max-height:min(70vh,560px)', self._html())

    def test_el_contenido_y_los_botones_van_anchos(self):
        html = self._html()
        # El contenido llega a 1440px, no a los 1180 de antes.
        self.assertIn('max-width:1440px', html.split('.fila-barra{')[1][:200])
        self.assertIn('max-width:1440px', html.split('#cqx-consent .panel{')[1][:200])
        self.assertIn('min-width:158px', html)


class LosDosModelosTest(TestCase):
    """El aviso sale siempre; lo que cambia con la región es el modelo.

    Es la diferencia legal que pedía Alexis: en Europa el consentimiento tiene
    que ser explícito —hasta que no se pulsa, nada— y en el resto es implícito,
    basta con informar de que al continuar se acepta.
    """

    def _html(self, pais):
        return self.client.get('/evento/evento-online', HTTP_HOST='www.conquerblocks.com',
                               HTTP_CF_IPCOUNTRY=pais).content.decode()

    def test_el_de_europa_obliga_a_elegir(self):
        html = self._html('ES')
        self.assertIn('>Rechazar<', html)
        self.assertIn('>Personalizar<', html)
        self.assertIn('>Aceptar todas<', html)
        self.assertNotIn('Al continuar navegando', html)

    def test_el_del_resto_informa_y_no_bloquea(self):
        html = self._html('MX')
        self.assertIn('Al continuar navegando, aceptas su uso', html)
        self.assertIn('>Configurar<', html)
        self.assertIn('>Entendido<', html)
        # Sin «Rechazar»: ahí el modelo no es de permiso previo, y para
        # retirarlo está «Configurar» y el icono que queda después.
        self.assertNotIn('>Rechazar<', html)

    def test_solo_europa_arranca_denegando(self):
        self.assertIn("var explicito = true", self._html('ES'))
        self.assertIn("var explicito = false", self._html('MX'))
        # Y la regla que lo traduce a Consent Mode es la misma en las dos.
        for pais in ('ES', 'MX'):
            self.assertIn("var inicial = (explicito && !guardado) ? 'denied' : 'granted'",
                          self._html(pais), pais)

    def test_el_implicito_se_cierra_al_seguir_navegando(self):
        js = JS.read_text(encoding='utf-8')
        implicito = js[js.index('if (!cfg.explicito)'):]
        # Eso es literalmente lo que promete el texto: al continuar, aceptas.
        self.assertIn("addEventListener('scroll'", implicito)
        self.assertIn("addEventListener('click'", implicito)
        # Pero si abrió el panel a elegir, no se le cierra por debajo.
        self.assertIn('if (panel && !panel.hidden) return;', implicito)

    def test_el_explicito_no_se_cierra_solo(self):
        js = JS.read_text(encoding='utf-8')
        explicito = js[js.rindex('// Consentimiento explícito'):]
        self.assertNotIn('addEventListener', explicito)
