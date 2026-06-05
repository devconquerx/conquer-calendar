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
    """Devuelve el dict de pixel IDs para una escuela, o {} si no se reconoce."""
    if not escuela:
        return {}
    return PIXEL_CONFIG.get(str(escuela).strip().lower(), {})


def pixel_ids(request):
    """Defaults para que las variables existan en todos los templates."""
    return {'pixel_ids': {}, 'app_base_path': ''}
