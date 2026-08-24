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
            self.assertEqual(html.count('<a class="button_wrap"'), 3, f'{host}{ruta}')

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
