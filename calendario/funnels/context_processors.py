"""Pixel IDs por escuela para inyectar los scripts base (gtag, fbq, ttq) en la
plantilla del funnel. Réplica de funnels/apps/core/context_processors.py.

En conquer-calendar la escuela se resuelve desde el FunnelForm (no hay
middleware de detección por dominio), así que la vista del funnel pasa
`pixel_ids` explícitamente. Este context processor solo garantiza que las
variables existan por defecto en cualquier render.
"""

# Claves por escuela tal como se guardan en FunnelForm.escuela (con guion) y
# también los slugs sin guion por robustez.
PIXEL_CONFIG = {
    'conquer-blocks': {
        'meta': '921361326426436',
        'tiktok': 'CTMK2ORC77U1LI1DFAD0',
        'ga4': 'G-LNCT8EQRDT',
    },
    'conquer-finance': {
        'meta': '1011283009921986',
        'tiktok': 'D03U523C77U9QS83BBI0',
        'ga4': 'G-9PGHQW52XM',
    },
    'conquer-languages': {
        'meta': '627205843180202',
        'tiktok': 'CVIQE0JC77U02UO7SEC0',
        'ga4': 'G-FJBW5107MW',
    },
}

# Alias sin guion (por si algún FunnelForm usa la forma de funnels).
PIXEL_CONFIG.update({
    'conquerblocks': PIXEL_CONFIG['conquer-blocks'],
    # Conquer AI es una línea de Conquer Blocks bajo su propio prefijo de URL
    # (www.conquerblocks.com/conquer-ai/...): mismo dominio, misma cuenta de
    # anuncios y mismos píxeles. Lo que la distingue en los informes es el
    # código de funnel (ai-eu), no un píxel aparte.
    'conquer-ai': PIXEL_CONFIG['conquer-blocks'],
    'conquerai': PIXEL_CONFIG['conquer-blocks'],
    'conquerfinance': PIXEL_CONFIG['conquer-finance'],
    'conquerlanguages': PIXEL_CONFIG['conquer-languages'],
})


def get_pixel_ids(escuela):
    """Devuelve el dict de pixel IDs para una escuela, o {} si no se reconoce.

    NOTA: con la arquitectura sGTM (ver GTM_CONFIG más abajo) los píxeles ya no
    se cargan client-side; los dispara el contenedor GTM hacia el server-side
    GTM. Se mantiene por compatibilidad y como referencia de IDs.
    """
    if not escuela:
        return {}
    return PIXEL_CONFIG.get(str(escuela).strip().lower(), {})


# ---------------------------------------------------------------------------
# Server-side GTM (sGTM) — contenedor web por marca, cargado vía loader
# first-party en _includes/_sgtm_head.html (réplica exacta de Webflow).
#
#   id            → ID completo del contenedor web (para el <noscript> ns.html)
#   st            → ID sin el prefijo "GTM-" (lo que espera el loader: ?st=)
#   loader_domain → dominio first-party del sGTM (subdominio de la marca)
#   loader_path   → archivo "cloaked" que el vhost reescribe a gtm.js
#
# Fuente de la verdad de dominios/paths: repo sgtm → apache-vhosts/*.conf
# ---------------------------------------------------------------------------
GTM_CONFIG = {
    'conquer-blocks': {
        'id': 'GTM-5PK5LTG',
        'st': '5PK5LTG',
        'loader_domain': 'load.somos.conquerblocks.com',
        'loader_path': 'tiehtchn.js',
    },
    'conquer-languages': {
        'id': 'GTM-MPB7S5C7',
        'st': 'MPB7S5C7',
        'loader_domain': 'somos.conquerlanguages.com',
        'loader_path': 'esjbifyby.js',
    },
    'conquer-finance': {
        'id': 'GTM-MXTDVVBG',
        'st': 'MXTDVVBG',
        'loader_domain': 'load.somos.conquerfinance.com',
        'loader_path': '6mxiahxsef.js',
    },
    'conquer-legal': {
        'id': 'GTM-P3QS7P4F',
        'st': 'P3QS7P4F',
        'loader_domain': 'somos.conquerlegal.com',
        'loader_path': 'lgxbqmtv.js',
    },
}

# Alias sin guion (por si algún FunnelForm usa la forma de funnels).
GTM_CONFIG.update({
    'conquerblocks': GTM_CONFIG['conquer-blocks'],
    # Conquer AI: mismo contenedor que Blocks. El loader del sGTM es
    # first-party contra load.somos.conquerblocks.com, que es el dominio en el
    # que se sirve — uno propio no existiría.
    'conquer-ai': GTM_CONFIG['conquer-blocks'],
    'conquerai': GTM_CONFIG['conquer-blocks'],
    'conquerfinance': GTM_CONFIG['conquer-finance'],
    'conquerlanguages': GTM_CONFIG['conquer-languages'],
    'conquerlegal': GTM_CONFIG['conquer-legal'],
})


def get_gtm_config(escuela):
    """Devuelve la config del contenedor GTM/sGTM para una escuela, o {}."""
    if not escuela:
        return {}
    return GTM_CONFIG.get(str(escuela).strip().lower(), {})


# ---------------------------------------------------------------------------
# Píxeles a código para las pantallas de evento (lanzamientos).
#
# Estas páginas NO cargan el contenedor de GTM: su trigger de lead es el mismo
# que el del funnel y mandaba los registros de lanzamiento a la conversión de
# venta, que es justo lo que había que separar. En su lugar cargan aquí los tres
# píxeles y disparan su PROPIO evento al registrarse, contra acciones y eventos
# creados solo para esto.
#
#   ads            → ID de conversiones de la cuenta de Google Ads (AW-…)
#   ads_conversion → send_to completo de la acción "Lead Lanzamiento <XX> Web"
#   ga4            → measurement ID, para no perder la medición que daba GTM
#   meta / tiktok  → los mismos píxeles de siempre; cambia el evento, no el píxel
#   evento_meta / evento_tiktok → nombre del evento propio de lanzamiento
#
# Los eventos de Meta y TikTok van con nombre propio para que no caigan en la
# conversión de Lead del funnel. El de Google no necesita nombre: la acción de
# conversión es la que separa la señal.
# ---------------------------------------------------------------------------
PIXELES_EVENTO = {
    'conquer-blocks': {
        'ads': 'AW-725899560',
        'ads_conversion': 'AW-725899560/2YIZCL-Iz_QcEKiykdoC',
        'ga4': 'G-LNCT8EQRDT',
        'meta': '921361326426436',
        'tiktok': 'CTMK2ORC77U1LI1DFAD0',
    },
    'conquer-languages': {
        'ads': 'AW-16956085244',
        'ads_conversion': 'AW-16956085244/kERXCMKIz_QcEPynpZU_',
        'ga4': 'G-FJBW5107MW',
        'meta': '627205843180202',
        'tiktok': 'CVIQE0JC77U02UO7SEC0',
    },
    'conquer-finance': {
        'ads': 'AW-16625277654',
        'ads_conversion': 'AW-16625277654/bJU2CPmU0_QcENa1xvc9',
        'ga4': 'G-9PGHQW52XM',
        'meta': '1011283009921986',
        'tiktok': 'D03U523C77U9QS83BBI0',
    },
}

PIXELES_EVENTO.update({
    'conquerblocks': PIXELES_EVENTO['conquer-blocks'],
    'conquerlanguages': PIXELES_EVENTO['conquer-languages'],
    'conquerfinance': PIXELES_EVENTO['conquer-finance'],
})

# Nombre del evento de lanzamiento en Meta y en TikTok. Es el mismo para las
# tres marcas: cada una tiene su píxel, así que no hay forma de confundirlos, y
# un solo nombre deja el informe comparable entre escuelas.
EVENTO_META_LANZAMIENTO = 'LeadLanzamiento'
EVENTO_TIKTOK_LANZAMIENTO = 'LeadLanzamiento'


def get_pixeles_evento(escuela):
    """Píxeles a código de las pantallas de evento, o {} si no se reconoce."""
    if not escuela:
        return {}
    cfg = PIXELES_EVENTO.get(str(escuela).strip().lower())
    if not cfg:
        return {}
    return dict(cfg,
                evento_meta=EVENTO_META_LANZAMIENTO,
                evento_tiktok=EVENTO_TIKTOK_LANZAMIENTO)


# ---------------------------------------------------------------------------
# Favicon por marca (ruta relativa a STATIC_URL; la plantilla le pone {% static %}).
#
# Las páginas que sirve Django tienen que declararlo igual que lo declaraban las
# de Webflow, porque el navegador no tiene de dónde sacarlo si no: el
# `/favicon.ico` de la raíz —su único recurso automático— responde 404 en los
# cuatro dominios de marca. Sin este <link> la pestaña sale con el icono en
# blanco del navegador, que es lo que llevaba pasando en todo el funnel salvo en
# Conquer Legal (el único que lo inyectaba desde el tema de React).
#
# Los ficheros son los mismos iconos que sirve cada web, descargados del CDN de
# Webflow a `static/img/favicons/`: servirlos nosotros los deja versionados con
# el resto de estáticos y sin depender de un dominio del que estamos saliendo.
# ---------------------------------------------------------------------------
FAVICON_POR_ESCUELA = {
    'conquer-blocks': 'img/favicons/conquer-blocks.png',
    'conquer-finance': 'img/favicons/conquer-finance.png',
    'conquer-languages': 'img/favicons/conquer-languages.png',
    'conquer-legal': 'img/favicons/conquer-legal.png',
}

# Líneas que no son marca propia: llevan el icono de su marca madre, igual que
# comparten dominio, píxeles y contenedor de GTM.
FAVICON_POR_ESCUELA.update({
    'conquer-ai': FAVICON_POR_ESCUELA['conquer-blocks'],
    'conquer-blocks-esp': FAVICON_POR_ESCUELA['conquer-blocks'],
    'conquer-languages-kids': FAVICON_POR_ESCUELA['conquer-languages'],
    # Alias sin guion, como en los mapas de arriba.
    'conquerblocks': FAVICON_POR_ESCUELA['conquer-blocks'],
    'conquerai': FAVICON_POR_ESCUELA['conquer-blocks'],
    'conquerfinance': FAVICON_POR_ESCUELA['conquer-finance'],
    'conquerlanguages': FAVICON_POR_ESCUELA['conquer-languages'],
    'conquerlegal': FAVICON_POR_ESCUELA['conquer-legal'],
})


def get_favicon(escuela):
    """Ruta estática del favicon de una escuela, o '' si no se reconoce."""
    if not escuela:
        return ''
    return FAVICON_POR_ESCUELA.get(str(escuela).strip().lower(), '')


def pixel_ids(request):
    """Defaults para que las variables existan en todos los templates.

    app_base_path lo fija AppBasePathMiddleware cuando el funnel se sirve bajo
    un prefijo (p.ej. /preview); por defecto '' (servido en la raíz).
    """
    from django.conf import settings
    from . import consentimiento as consent
    return {
        'pixel_ids': {},
        'gtm': {},
        # Solo las pantallas de evento lo rellenan (ver funnels.evento_views).
        'pixeles': {},
        # Por defecto sin marca; las vistas que saben de qué escuela es lo
        # sobrescriben con su paleta.
        'consentimiento': consent.contexto(request),
        'app_base_path': getattr(request, 'app_base_path', ''),
        'calendar_public_origin': getattr(settings, 'CALENDAR_PUBLIC_ORIGIN', ''),
    }
