# -*- coding: utf-8 -*-
"""Los leads de evento (lanzamiento) van SOLO al CRM.

No es una decisión de diseño nueva, es lo que hacía el escenario de Make: sus
ramas de correo, Respond.io y CAPI están apagadas, y se comprueba en el log de
ejecuciones —un evento de Blocks consume 2 operaciones (webhook + CRM) y uno de
Languages con teléfono 3 (webhook + CRM + FunnelChat)—. Si salieran correos o
Respond.io habría 5 o más, y no hay ninguna ejecución por encima de 4 en
150.969 registros.

Tampoco pasan por NeverBounce: Make postea directo al ingest y valida el CRM.
"""
import json
import re
from pathlib import Path
from unittest.mock import patch

from django.test import TestCase
from django.urls import reverse

from calendario.leads.models import Lead
from calendario.funnels.evento_views import EVENTOS
from calendario.leads.tasks import es_lead_de_lanzamiento

RUTA = 'calendario.leads.tasks.'
SERVICIOS = ('process_supabase', 'process_meta_capi', 'process_tiktok_events',
             'process_google_ads', 'process_respondio', 'process_activecampaign',
             'process_neverbounce', 'process_funnelchat')


class DetectaLanzamientoTest(TestCase):
    def test_reconoce_los_codigos_de_edicion(self):
        for codigo in ('cb-lanzamiento11', 'cl-lanzamiento8', 'cf-lanzamiento9', 'CB-Lanzamiento12'):
            self.assertTrue(es_lead_de_lanzamiento(Lead(funnel=codigo)), codigo)

    def test_no_confunde_los_funnels_normales(self):
        for codigo in ('cb-eu', 'cl-latam', 'fi-us', 'cb-eu-2', '', None):
            self.assertFalse(es_lead_de_lanzamiento(Lead(funnel=codigo)), repr(codigo))


class DespachoDeLanzamientoTest(TestCase):
    """El alta de un lead dispara las tareas por signal, así que se crea el Lead
    de verdad y se comprueba qué se encoló."""

    def _crear(self, funnel):
        parches = {n: patch(RUTA + n) for n in SERVICIOS}
        parches['process_crm_send'] = patch(RUTA + 'process_crm_send')
        activos = {n: p.start() for n, p in parches.items()}
        try:
            Lead.objects.create(email='lead@ejemplo.com', full_name='Ana', funnel=funnel)
            return {n: m.delay.called for n, m in activos.items()}
        finally:
            for p in parches.values():
                p.stop()

    def test_el_de_evento_solo_va_al_crm(self):
        llamadas = self._crear('cb-lanzamiento11')
        self.assertTrue(llamadas['process_crm_send'], 'el CRM debe recibirlo')
        for servicio in SERVICIOS:
            self.assertFalse(llamadas[servicio], f'{servicio} no debería dispararse')

    def test_el_del_funnel_sigue_disparando_todo(self):
        llamadas = self._crear('cb-eu')
        self.assertTrue(llamadas['process_supabase'])
        self.assertTrue(llamadas['process_respondio'])
        self.assertTrue(llamadas['process_neverbounce'])
        # El CRM le llega encadenado desde NeverBounce, no directo.
        self.assertFalse(llamadas['process_crm_send'])


class AltaDesdeLaPantallaDeEventoTest(TestCase):
    """El formulario del evento postea al mismo endpoint que el resto de leads."""

    def test_guarda_el_lead_con_el_codigo_de_la_edicion(self):
        cuerpo = {
            'name': 'Ana Pérez', 'email': 'ana@ejemplo.com',
            'lead_phone': '600111222', 'lead_phone_prefix': '+34',
            'lead_country': 'España', 'funnel': 'cb-lanzamiento11',
            'url': 'https://www.conquerblocks.com/evento/evento-online?utm_source=ActiveCampaign',
            'utm_source': 'ActiveCampaign', 'utm_campaign': 'cb-lanzamiento11',
        }
        with patch(RUTA + 'process_crm_send') as crm:
            resp = self.client.post(reverse('funnels:register_lead'),
                                    data=json.dumps(cuerpo), content_type='application/json')
        self.assertEqual(resp.status_code, 200)
        lead = Lead.objects.get()
        self.assertEqual(lead.funnel, 'cb-lanzamiento11')
        self.assertEqual(lead.full_name, 'Ana Pérez')
        self.assertEqual(lead.lead_phone_prefix, '+34')
        self.assertEqual(lead.utm_campaign, 'cb-lanzamiento11')
        self.assertTrue(crm.delay.called)


class CodigoDeEdicionEnLaPantallaTest(TestCase):
    """La edición viaja en la campaña, como en Webflow.

    `getFunnelValue()` de la página de Webflow copiaba `utm_campaign` en el
    campo `funnel` al enviar; por eso en el CRM conviven `cf-lanzamiento10` y
    `cf-lanzamiento11` sin orden cronológico. Si aquí se quedara fijo el código
    del código fuente, cada lanzamiento nuevo se archivaría bajo la edición
    anterior hasta que alguien se acordara de desplegar.
    """

    def _funnel_renderizado(self, query):
        resp = self.client.get('/evento/evento-online' + query,
                               HTTP_HOST='www.conquerblocks.com')
        self.assertEqual(resp.status_code, 200)
        html = resp.content.decode()
        marca = 'window.__EVENTO__ = { funnel: "'
        inicio = html.index(marca) + len(marca)
        crudo = html[inicio:html.index('"', inicio)]
        # `escapejs` escapa hasta los guiones (`cb\\u002Dlanzamiento11`).
        return re.sub(r'\\u([0-9a-fA-F]{4})', lambda m: chr(int(m.group(1), 16)), crudo)

    def test_la_campana_manda_sobre_el_codigo_del_codigo_fuente(self):
        self.assertEqual(
            self._funnel_renderizado('?utm_campaign=cb-lanzamiento12'),
            'cb-lanzamiento12')

    def test_sin_campana_cae_al_codigo_configurado(self):
        # Webflow mandaba el campo vacío; un `funnel` vacío no pasa por
        # `es_lead_de_lanzamiento` y el lead se iría por el pipeline completo.
        self.assertEqual(self._funnel_renderizado(''), EVENTOS['conquer-blocks']['funnel'])

    def test_una_campana_que_no_es_de_lanzamiento_no_secuestra_el_codigo(self):
        obtenido = self._funnel_renderizado('?utm_campaign=black-friday')
        self.assertEqual(obtenido, EVENTOS['conquer-blocks']['funnel'])
        self.assertTrue(es_lead_de_lanzamiento(Lead(funnel=obtenido)))


class FunnelChatEnLanzamientosTest(TestCase):
    """De los lanzamientos, solo Languages con teléfono dispara FunnelChat.

    En Make ese módulo cuelga de la rama de Languages, que filtra `funnel` por
    'cl'. Blocks no tiene módulo y Finance tampoco entra: su rama filtra por
    'fi' y los códigos de lanzamiento de Finance son 'cf-lanzamientoN'.
    """

    def _crear(self, funnel, telefono='600111222'):
        with patch(RUTA + 'process_crm_send'), patch(RUTA + 'process_funnelchat') as fc:
            Lead.objects.create(email='lead@ejemplo.com', full_name='Ana',
                                funnel=funnel, lead_phone=telefono)
            return fc.delay.called

    def test_languages_con_telefono_si(self):
        self.assertTrue(self._crear('cl-lanzamiento9'))

    def test_languages_sin_telefono_no(self):
        self.assertFalse(self._crear('cl-lanzamiento9', telefono=''))

    def test_blocks_no(self):
        self.assertFalse(self._crear('cb-lanzamiento11'))

    def test_finance_no(self):
        # 'cf-lanzamiento11' no contiene 'fi', así que en Make nunca entró.
        self.assertFalse(self._crear('cf-lanzamiento11'))


class TriggersDeFunnelChatTest(TestCase):
    """Los triggers tienen que ser exactamente los dos del escenario de Make."""

    def test_languages_y_finance_apuntan_a_su_trigger(self):
        from calendario.leads.services.funnelchat import SCHOOL_FUNNELCHAT_TRIGGER as T
        cl = 'https://flows-api.funnelchat.app/api/v1/users/3231/triggers/7db0da3a-27df-4ae9-919a-0beabc5b1250'
        fi = 'https://flows-api.funnelchat.app/api/v1/users/3231/triggers/db9c763c-6af4-4119-b953-ff238b87a321'
        self.assertEqual(T.get('cl'), cl)
        self.assertEqual(T.get('cf'), fi)
        self.assertEqual(T.get('fi'), fi)
        self.assertIsNone(T.get('cb'), 'Blocks no tiene módulo de FunnelChat en Make')

    def test_se_manda_como_multipart(self):
        from calendario.leads.services import funnelchat
        lead = Lead(pk=1, email='a@b.com', full_name='Ana', funnel='cl-eu',
                    lead_phone='600111222', lead_phone_prefix='+34')
        with patch.object(funnelchat, 'requests') as req:
            req.post.return_value.status_code = 200
            funnelchat.push_lead(lead)
        _, kwargs = req.post.call_args
        self.assertIn('files', kwargs, 'Make lo mandaba como multipart')
        self.assertEqual(kwargs['files']['phone'], (None, '+34600111222'))


class LaPantallaNoSeCacheaTest(TestCase):
    """El HTML cambia por visitante, así que no puede quedarse cacheado.

    El código de la edición sale de `utm_campaign` y el prefijo preseleccionado
    de `CF-IPCountry`: una copia compartida le daría a un visitante la campaña
    o el país de otro. Los navegadores embebidos de TikTok e Instagram ya
    hicieron justo eso con el HTML del funnel.
    """

    def _get(self, q='', pais='ES'):
        return self.client.get('/evento/evento-online' + q,
                               HTTP_HOST='www.conquerblocks.com', HTTP_CF_IPCOUNTRY=pais)

    def test_prohibe_cachear(self):
        self.assertIn('no-store', self._get().headers.get('Cache-Control', ''))

    def test_varia_por_pais(self):
        self.assertIn('CF-IPCountry', self._get().headers.get('Vary', ''))

    def test_el_html_de_verdad_cambia_con_el_pais(self):
        # Si esto dejara de ser cierto, las cabeceras de arriba sobrarían.
        self.assertNotEqual(self._get(pais='MX').content, self._get(pais='ES').content)

    def test_una_campana_larga_no_se_pinta_mas_ancha_que_el_campo(self):
        from calendario.leads.models import Lead
        ancho = Lead._meta.get_field('funnel').max_length
        r = self._get('?utm_campaign=lanzamiento' + 'x' * 5000)
        html = r.content.decode()
        marca = 'window.__EVENTO__ = { funnel: "'
        i = html.index(marca) + len(marca)
        self.assertLessEqual(len(html[i:html.index('"', i)]), ancho)


class RedireccionDeGraciasTest(TestCase):
    """Tras registrarse hay que ir a la página de gracias, como en el original.

    Ahí está el último paso real —entrar al grupo de WhatsApp de asistentes—,
    así que quedarse en la pantalla dejaba al registrado a medias.
    """

    def _gracias(self, host, ruta='/evento/evento-online'):
        html = self.client.get(ruta, HTTP_HOST=host).content.decode()
        marca = 'gracias: "'
        i = html.index(marca) + len(marca)
        crudo = html[i:html.index('"', i)]
        return re.sub(r'\\u([0-9a-fA-F]{4})', lambda m: chr(int(m.group(1), 16)), crudo)

    def test_cada_marca_va_a_su_propia_pagina(self):
        # Ruta relativa a propósito: sirve para cualquier host sin tener que
        # resolver el dominio público de cada marca.
        self.assertEqual(self._gracias('www.conquerblocks.com'), '/evento/gracias-comunidad')
        self.assertEqual(self._gracias('www.conquerfinance.com'), '/evento/gracias-comunidad')
        self.assertEqual(self._gracias('www.conquerlanguages.com', '/cl-evento'), '/grupos-comunidad')

    def test_la_pagina_de_gracias_responde_en_cada_dominio(self):
        for host, ruta in (('www.conquerblocks.com', '/evento/gracias-comunidad'),
                           ('www.conquerfinance.com', '/evento/gracias-comunidad'),
                           ('www.conquerlanguages.com', '/grupos-comunidad')):
            resp = self.client.get(ruta, HTTP_HOST=host)
            self.assertEqual(resp.status_code, 200, f'{host}{ruta}')
            html = resp.content.decode()
            self.assertIn('comunidad vip', html.lower())
            # El grupo se enlaza tres veces, una por tarjeta, como en el
            # original: `button_wrap` sale además en el CSS, así que se cuentan
            # los enlaces.
            self.assertEqual(html.count('<a class="boton"'), 3, f'{host}{ruta}')

    def test_salta_sola_al_grupo_a_los_15_segundos(self):
        html = self.client.get('/evento/gracias-comunidad',
                               HTTP_HOST='www.conquerblocks.com').content.decode()
        self.assertIn('15000', html)
        self.assertIn('cb.conquerx.com', html)

    def test_cada_marca_pinta_su_titular_degradado(self):
        # `.conquer-gradient` no es la pareja del CTA: en Finance el titular es
        # verde aunque el CTA también lo sea, y en Blocks naranja. Medido sobre
        # las páginas originales.
        cb = self.client.get('/evento/gracias-comunidad',
                             HTTP_HOST='www.conquerblocks.com').content.decode()
        cf = self.client.get('/evento/gracias-comunidad',
                             HTTP_HOST='www.conquerfinance.com').content.decode()
        self.assertIn('--titular-1:#ff4000', cb)
        self.assertIn('--titular-2:#ff9800', cb)
        self.assertIn('--titular-1:#3ac043', cf)
        self.assertIn('--titular-2:#aed916', cf)

    def test_languages_enlaza_su_grupo_y_no_el_de_blocks(self):
        html = self.client.get('/grupos-comunidad',
                               HTTP_HOST='www.conquerlanguages.com').content.decode()
        self.assertIn('cl.conquerx.com', html)
        self.assertNotIn('cb.conquerx.com', html)

    def test_no_se_mandan_datos_personales_en_la_url(self):
        js = (Path(__file__).resolve().parents[2]
              / 'calendario' / 'static' / 'js' / 'evento-registro.js').read_text(encoding='utf-8')
        destino = js[js.index('function irAGracias'):js.index('form.addEventListener')]
        for campo in ('fullname', 'email', 'lead_phone', 'name'):
            self.assertNotIn(f"'{campo}'", destino,
                             f'{campo} no puede viajar en la query de la redirección')


class DeteccionDePaisTest(TestCase):
    """El prefijo tiene que salir preseleccionado con el país del visitante.

    La cadena es: cabecera de Cloudflare → consulta por IP → España. El punto
    delicado es el primer eslabón: si la vista rellena España cuando la cabecera
    no viene, el cliente no puede distinguir «Cloudflare dice España» de
    «Cloudflare no ha dicho nada» y nunca llega a preguntar por IP. Hoy esa
    cabecera NO llega en calendar.conquerx.com, así que sin esto todo el mundo
    se quedaba con +34.
    """

    def _data_pais(self, **extra):
        html = self.client.get('/evento/evento-online',
                               HTTP_HOST='www.conquerblocks.com', **extra).content.decode()
        return html.split('data-pais="')[1].split('"')[0]

    def test_usa_la_cabecera_de_cloudflare_cuando_viene(self):
        self.assertEqual(self._data_pais(HTTP_CF_IPCOUNTRY='mx'), 'MX')

    def test_sin_cabecera_lo_deja_vacio_para_que_el_cliente_pregunte(self):
        self.assertEqual(self._data_pais(), '')

    def test_el_respaldo_por_ip_es_el_mismo_que_usa_el_funnel(self):
        # ipapi.co, que es lo que usaba el Webflow original, responde 429 con
        # muy poco tráfico: el respaldo no respaldaba nada.
        js = (Path(__file__).resolve().parents[2]
              / 'calendario' / 'static' / 'js' / 'evento-prefijo.js').read_text(encoding='utf-8')
        hook = (Path(__file__).resolve().parents[2]
                / 'frontend' / 'src' / 'hooks' / 'useGeoLocation.js').read_text(encoding='utf-8')
        self.assertIn('get.geojs.io/v1/ip/country.json', js)
        self.assertIn('get.geojs.io/v1/ip/country.json', hook)
        # Se comprueba la llamada, no la palabra: ipapi.co se sigue nombrando
        # en el comentario que explica por qué ya no se usa.
        self.assertNotIn("fetch('https://ipapi.co", js)


class GtmEnLasPantallasTest(TestCase):
    """Cada marca carga su contenedor en la pantalla del evento y en la de gracias.

    Blocks y Languages son los que ya llevaba Webflow. Finance no llevaba
    ninguno —sus lanzamientos estaban sin medir— y se le enchufa el suyo, que es
    lo único que se aparta del original a propósito.
    """

    CASOS = (
        ('www.conquerblocks.com', '/evento/evento-online', '5PK5LTG'),
        ('www.conquerblocks.com', '/evento/gracias-comunidad', '5PK5LTG'),
        ('www.conquerlanguages.com', '/cl-evento', 'MPB7S5C7'),
        ('www.conquerlanguages.com', '/grupos-comunidad', 'MPB7S5C7'),
        ('www.conquerfinance.com', '/evento/evento-online', 'MXTDVVBG'),
        ('www.conquerfinance.com', '/evento/gracias-comunidad', 'MXTDVVBG'),
    )

    def test_cada_marca_carga_su_contenedor(self):
        for host, ruta, st in self.CASOS:
            html = self.client.get(ruta, HTTP_HOST=host).content.decode()
            self.assertIn(f"st = '{st}'", html, f'{host}{ruta}')

    def test_ninguna_carga_el_de_otra(self):
        for host, ruta, st in self.CASOS:
            html = self.client.get(ruta, HTTP_HOST=host).content.decode()
            for otro in {c[2] for c in self.CASOS} - {st}:
                self.assertNotIn(otro, html, f'{host}{ruta} carga {otro}')


class EmailEnMinusculasTest(TestCase):
    """El correo se guarda en minúsculas, como lo mandaba Make.

    El CRM compara correos tal cual —dedup de prellamadas, cruce con
    ActiveCampaign y Respond.io— y Postgres distingue mayúsculas, así que un
    "Juan@Gmail.com" no casaría con el "juan@gmail.com" que ese contacto ya
    tuviera de otra entrada.
    """

    def _alta(self, email):
        with patch(RUTA + 'process_crm_send'), patch(RUTA + 'process_supabase'), \
             patch(RUTA + 'process_respondio'), patch(RUTA + 'process_activecampaign'), \
             patch(RUTA + 'process_neverbounce'), patch(RUTA + 'process_funnelchat'):
            resp = self.client.post(
                reverse('funnels:register_lead'),
                data=json.dumps({'name': 'Ana', 'email': email, 'funnel': 'cb-lanzamiento11'}),
                content_type='application/json')
        self.assertEqual(resp.status_code, 200)
        return Lead.objects.order_by('-pk').first().email

    def test_baja_las_mayusculas(self):
        self.assertEqual(self._alta('Juan.Perez@Gmail.COM'), 'juan.perez@gmail.com')

    def test_no_toca_los_que_ya_venian_bien(self):
        self.assertEqual(self._alta('ana@ejemplo.com'), 'ana@ejemplo.com')


class LaRedireccionFuncionaEnLosDosSitiosTest(TestCase):
    """El salto a la página de gracias tiene que funcionar antes y después de
    que Cloudflare enrute los dominios de marca.

    En los dominios de marca la escuela sale del Host. En el canónico
    (calendar.conquerx.com) NO, viene en `?escuela=`, y si no se arrastra la
    página de gracias responde 404 y no hay forma de probar el recorrido entero
    antes de encender el enrutado.
    """

    def _destino(self, ruta, host):
        html = self.client.get(ruta, HTTP_HOST=host).content.decode()
        marca = 'gracias: "'
        i = html.index(marca) + len(marca)
        crudo = html[i:html.index('"', i)]
        return re.sub(r'\\u([0-9a-fA-F]{4})', lambda m: chr(int(m.group(1), 16)), crudo)

    def test_en_los_dominios_de_marca_va_pelada(self):
        for host, ruta, esperado in (
            ('www.conquerblocks.com', '/evento/evento-online', '/evento/gracias-comunidad'),
            ('www.conquerfinance.com', '/evento/evento-online', '/evento/gracias-comunidad'),
            ('www.conquerlanguages.com', '/cl-evento', '/grupos-comunidad'),
        ):
            self.assertEqual(self._destino(ruta, host), esperado, host)

    def test_en_el_canonico_arrastra_la_escuela(self):
        for escuela, esperado in (
            ('conquer-blocks', '/evento/gracias-comunidad?escuela=conquer-blocks'),
            ('conquer-finance', '/evento/gracias-comunidad?escuela=conquer-finance'),
        ):
            destino = self._destino(f'/evento/evento-online?escuela={escuela}', 'calendar.conquerx.com')
            self.assertEqual(destino, esperado)
            # Y ese destino tiene que responder de verdad, no 404.
            ruta, _, query = destino.partition('?')
            resp = self.client.get(ruta + '?' + query, HTTP_HOST='calendar.conquerx.com')
            self.assertEqual(resp.status_code, 200, destino)

    def test_el_separador_de_la_query_lo_decide_el_destino(self):
        js = (Path(__file__).resolve().parents[2]
              / 'calendario' / 'static' / 'js' / 'evento-registro.js').read_text(encoding='utf-8')
        self.assertIn("destino.indexOf('?') === -1 ? '?' : '&'", js)


class TransicionSinRecargaTest(TestCase):
    """De la pantalla del evento a la de gracias sin recargar.

    El bloque de gracias viaja embebido y oculto en la propia pantalla, así que
    al registrarse solo hay que intercambiarlos. La URL se cambia con pushState
    a la de gracias, que sigue existiendo como página propia para quien entre
    directo, recargue o comparta el enlace.
    """

    RUTAS = (('www.conquerblocks.com', '/evento/evento-online'),
             ('www.conquerfinance.com', '/evento/evento-online'),
             ('www.conquerlanguages.com', '/cl-evento'))

    def test_la_pantalla_del_evento_ya_trae_la_de_gracias_oculta(self):
        for host, ruta in self.RUTAS:
            html = self.client.get(ruta, HTTP_HOST=host).content.decode()
            self.assertIn('id="evento-contenido"', html, host)
            self.assertIn('id="gracias-evento"', html, host)
            self.assertIn('hidden', html.split('id="gracias-evento"')[1][:120], host)
            # Los tres botones al grupo, ya presentes aunque no se vean.
            self.assertEqual(html.count('<a class="boton"'), 3, host)

    def test_el_css_de_gracias_va_acotado_para_no_pisar_al_del_evento(self):
        # Embebidas comparten documento; sin acotar, el CTA del evento y el de
        # gracias se pisarían.
        html = self.client.get('/cl-evento', HTTP_HOST='www.conquerlanguages.com').content.decode()
        estilos = html.split('<div id="gracias-evento"')[0]
        bloque = estilos[estilos.rindex('<style>'):]
        for linea in bloque.splitlines():
            linea = linea.strip()
            if linea.startswith('.') or linea.startswith('#evento'):
                self.assertTrue(linea.startswith('#gracias-evento') or linea.startswith('#evento-contenido'),
                                f'regla sin acotar: {linea[:60]}')

    def test_avisa_al_gtm_con_el_mismo_evento_que_el_funnel(self):
        js = (Path(__file__).resolve().parents[2]
              / 'calendario' / 'static' / 'js' / 'evento-registro.js').read_text(encoding='utf-8')
        pixel = (Path(__file__).resolve().parents[2]
                 / 'frontend' / 'src' / 'lib' / 'pixelEvents.js').read_text(encoding='utf-8')
        # Sin recarga no hay page_view del contenedor; lo sustituye el mismo
        # evento virtual que ya usa el funnel al cambiar de etapa.
        self.assertIn("event: 'virtual_page_view'", js)
        self.assertIn("event: 'virtual_page_view'", pixel)
        for campo in ('page_location', 'page_path'):
            self.assertIn(campo, js)
        # Y se empuja DESPUÉS del pushState, o el trigger leería la URL vieja.
        # Se mira dentro de la función, no en todo el fichero: la palabra sale
        # antes en el comentario que explica por qué está.
        cuerpo = js[js.index('function irAGracias'):js.index("window.addEventListener('popstate'")]
        self.assertLess(cuerpo.index('history.pushState'), cuerpo.index("event: 'virtual_page_view'"))

    def test_al_volver_atras_se_devuelve_el_titulo(self):
        js = (Path(__file__).resolve().parents[2]
              / 'calendario' / 'static' / 'js' / 'evento-registro.js').read_text(encoding='utf-8')
        vuelta = js[js.index("window.addEventListener('popstate'"):]
        self.assertIn('document.title = tituloEvento', vuelta,
                      'sin esto queda el título de gracias con el formulario delante')

    def test_si_no_hay_pushstate_navega_de_toda_la_vida(self):
        js = (Path(__file__).resolve().parents[2]
              / 'calendario' / 'static' / 'js' / 'evento-registro.js').read_text(encoding='utf-8')
        salto = js[js.index('function irAGracias'):js.index("window.addEventListener('popstate'")]
        self.assertIn('window.location.href', salto,
                      'sin respaldo, un navegador sin pushState dejaría al registrado sin último paso')


class LaUrlQueDejaElPushStateSeAguantaTest(TestCase):
    """La URL que queda en la barra tras registrarse tiene que responder.

    Con la transición sin recarga esa URL NO se pide al pasar de pantalla, pero
    sí en cuanto alguien recarga, la comparte o la guarda. Si no responde, el
    registrado se encuentra un 404 justo después de haberse apuntado.

    Se prueban las dos etapas: los dominios de marca (donde la escuela sale del
    Host) y el canónico de la migración (donde viaja en la query).
    """

    CASOS = (
        ('www.conquerblocks.com', '/evento/evento-online', None),
        ('www.conquerfinance.com', '/evento/evento-online', None),
        ('www.conquerlanguages.com', '/cl-evento', None),
        ('calendar.conquerx.com', '/evento/evento-online', 'conquer-blocks'),
        ('calendar.conquerx.com', '/evento/evento-online', 'conquer-finance'),
        ('calendar.conquerx.com', '/cl-evento', 'conquer-languages'),
    )

    def _url_tras_registrarse(self, host, ruta, escuela):
        """Reproduce lo que arma el JS: destino + separador + params()."""
        q = '?escuela=' + escuela if escuela else ''
        html = self.client.get(ruta + q, HTTP_HOST=host).content.decode()
        marca = 'gracias: "'
        i = html.index(marca) + len(marca)
        destino = re.sub(r'\\u([0-9a-fA-F]{4})', lambda m: chr(int(m.group(1), 16)),
                         html[i:html.index('"', i)])
        sep = '?' if '?' not in destino else '&'
        return destino + sep + 'v=20250218&utm_source=meta&funnel=cb-lanzamiento11'

    def test_la_url_responde_en_las_dos_etapas(self):
        for host, ruta, escuela in self.CASOS:
            url = self._url_tras_registrarse(host, ruta, escuela)
            resp = self.client.get(url, HTTP_HOST=host)
            self.assertEqual(resp.status_code, 200, f'{host}{url}')
            # Y lo que sale es la pantalla de gracias de esa marca, no otra.
            self.assertIn('id="gracias-evento"', resp.content.decode(), f'{host}{url}')

    def test_los_parametros_de_campana_no_estorban(self):
        # La página de gracias no los lee, pero llegan igual; que no rompan.
        url = self._url_tras_registrarse('www.conquerblocks.com', '/evento/evento-online', None)
        self.assertIn('v=20250218', url)
        self.assertEqual(
            self.client.get(url, HTTP_HOST='www.conquerblocks.com').status_code, 200)

    def test_en_el_canonico_la_escuela_sobrevive_a_los_parametros(self):
        url = self._url_tras_registrarse('calendar.conquerx.com', '/evento/evento-online',
                                         'conquer-finance')
        self.assertIn('escuela=conquer-finance', url)
        html = self.client.get(url, HTTP_HOST='calendar.conquerx.com').content.decode()
        # La de Finance, no la de Blocks: se distinguen por el contenedor GTM.
        self.assertIn("st = 'MXTDVVBG'", html)


class ElSaltoAlGrupoNoSeCancelaTest(TestCase):
    """El temporizador de 15 s tiene que correr pase lo que pase.

    Hubo un intento de cancelarlo con `visibilitychange` para no reenviar a
    quien ya se había ido al grupo por su cuenta, pero el efecto era el
    contrario: bastaba cambiar de pestaña un segundo mientras esperabas para
    matarlo, y ya no saltaba nunca. El original no cancela nada.
    """

    def _salto(self, ruta, host):
        html = self.client.get(ruta, HTTP_HOST=host).content.decode()
        return html[html.index('window.iniciarSaltoWhatsApp = '):]

    def test_no_hay_nada_que_lo_cancele(self):
        js = self._salto('/grupos-comunidad', 'www.conquerlanguages.com')
        cuerpo = js[:js.index('</script>')]
        self.assertIn('15000', cuerpo)
        self.assertNotIn('clearTimeout', cuerpo)
        self.assertNotIn('visibilitychange', cuerpo)

    def test_la_pagina_suelta_lo_arranca_al_cargar(self):
        html = self.client.get('/grupos-comunidad',
                               HTTP_HOST='www.conquerlanguages.com').content.decode()
        self.assertIn('window.iniciarSaltoWhatsApp();', html)

    def test_en_la_del_evento_no_arranca_hasta_registrarse(self):
        # Si arrancara al cargar, quien aún está rellenando el formulario se
        # iría a WhatsApp a los 15 segundos.
        html = self.client.get('/cl-evento', HTTP_HOST='www.conquerlanguages.com').content.decode()
        self.assertIn('window.iniciarSaltoWhatsApp = ', html)
        self.assertNotIn('window.iniciarSaltoWhatsApp();', html)
        js = (Path(__file__).resolve().parents[2]
              / 'calendario' / 'static' / 'js' / 'evento-registro.js').read_text(encoding='utf-8')
        self.assertIn('window.iniciarSaltoWhatsApp()', js)


class ElTelefonoSeVeComoUnSoloControlTest(TestCase):
    """Prefijo y número forman un control único, como el original.

    En Languages la regla del número dentro de `.tel-row` iba sin `[type=tel]`,
    así que perdía por especificidad contra `.campo input[type=tel]` y el número
    conservaba su propio borde y su radio: se veía un segundo recuadro dentro
    del control y el prefijo quedaba descolgado.
    """

    def test_la_regla_del_numero_gana_a_la_general(self):
        for ruta, host in (('/cl-evento', 'www.conquerlanguages.com'),
                           ('/evento/evento-online', 'www.conquerblocks.com')):
            html = self.client.get(ruta, HTTP_HOST=host).content.decode()
            self.assertIn('.tel-row input[type=tel]{', html, f'{host}{ruta}')
            # La general existe y es la que había que ganar.
            self.assertIn('.campo input[type=text],.campo input[type=email],.campo input[type=tel]',
                          html, f'{host}{ruta}')


class ElPrefijoDePruebaSeMantieneTest(TestCase):
    """Bajo /preview el salto tiene que quedarse dentro de /preview.

    Ese prefijo existe para probar en el dominio real sin tocar las páginas de
    Webflow: Cloudflare enruta solo /preview/* a Django. Si el destino saliera
    sin prefijo, al registrarse la barra acabaría en la página de Webflow, que
    es justo de lo que el prefijo sirve para escapar.
    """

    def _destino(self, ruta, host):
        html = self.client.get(ruta, HTTP_HOST=host).content.decode()
        i = html.index('gracias: "') + len('gracias: "')
        return re.sub(r'\\u([0-9a-fA-F]{4})', lambda m: chr(int(m.group(1), 16)),
                      html[i:html.index('"', i)])

    def test_bajo_preview_el_destino_lo_conserva(self):
        for host, ruta, esperado in (
            ('www.conquerblocks.com', '/preview/evento/evento-online',
             '/preview/evento/gracias-comunidad'),
            ('www.conquerfinance.com', '/preview/evento/evento-online',
             '/preview/evento/gracias-comunidad'),
            ('www.conquerlanguages.com', '/preview/cl-evento', '/preview/grupos-comunidad'),
        ):
            self.assertEqual(self._destino(ruta, host), esperado, f'{host}{ruta}')

    def test_y_esa_url_responde(self):
        resp = self.client.get('/preview/evento/gracias-comunidad',
                               HTTP_HOST='www.conquerblocks.com')
        self.assertEqual(resp.status_code, 200)
        self.assertIn('id="gracias-evento"', resp.content.decode())

    def test_sin_prefijo_sigue_yendo_a_la_raiz(self):
        self.assertEqual(self._destino('/evento/evento-online', 'www.conquerblocks.com'),
                         '/evento/gracias-comunidad')
