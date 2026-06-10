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
}

# Alias sin guion (por si algún FunnelForm usa la forma de funnels).
GTM_CONFIG.update({
    'conquerblocks': GTM_CONFIG['conquer-blocks'],
    'conquerfinance': GTM_CONFIG['conquer-finance'],
    'conquerlanguages': GTM_CONFIG['conquer-languages'],
})


def get_gtm_config(escuela):
    """Devuelve la config del contenedor GTM/sGTM para una escuela, o {}."""
    if not escuela:
        return {}
    return GTM_CONFIG.get(str(escuela).strip().lower(), {})


def pixel_ids(request):
    """Defaults para que las variables existan en todos los templates.

    app_base_path lo fija AppBasePathMiddleware cuando el funnel se sirve bajo
    un prefijo (p.ej. /preview); por defecto '' (servido en la raíz).
    """
    return {
        'pixel_ids': {},
        'gtm': {},
        'app_base_path': getattr(request, 'app_base_path', ''),
    }
