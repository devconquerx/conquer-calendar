import hashlib
import logging

logger = logging.getLogger(__name__)

CONVERSION_VALUES = {
    'lead': {'EU': 10, 'LATAM': 1, 'USA': 5},
    'schedule': {'EU': 100, 'LATAM': 10, 'USA': 50},
}

FUNNEL_REGION_MAP = {'latam': 'LATAM', 'eu': 'EU', 'us': 'USA'}
CAMPAIGN_REGION_MAP = {'LATAM': 'LATAM', 'Europe': 'EU', 'USA': 'USA'}

SCHOOL_PIXEL_META = {
    'cb': '921361326426436',
    'cl': '627205843180202',
    'cf': '1011283009921986',
    'fi': '1011283009921986',
}

SCHOOL_PIXEL_TIKTOK = {
    'cb': ('CTMK2ORC77U1LI1DFAD0', 'c75fa5e7a7791913563fab7a409e0d0b6998e9fb'),
    'cl': ('CVIQE0JC77U02UO7SEC0', '56b2583685c68af9b571771e5de59941688b1f3e'),
    'cf': ('D03U523C77U9QS83BBI0', 'e503e010cc127c0cabc2c70bb1a18c4370a0f198'),
    'fi': ('D03U523C77U9QS83BBI0', 'e503e010cc127c0cabc2c70bb1a18c4370a0f198'),
}

SCHOOL_CUSTOMER_GOOGLE = {
    'cb': '6193039470',
    'cl': '1164152552',
    'cf': '1192352539',
    'fi': '1192352539',
    'cg': '1328896929',  # Conquer Legal
}

SCHOOL_CONVERSION_ACTIONS = {
    'cb': {'registro-lead': 7478637099, 'llamada-agendada': 7478385997, 'venta': 7470233516},
    'cl': {'registro-lead': 7478389619, 'llamada-agendada': 7478647338, 'venta': 7470199894},
    'cf': {'registro-lead': 7478395177, 'llamada-agendada': 7478652894, 'venta': 7470245510},
    'fi': {'registro-lead': 7478395177, 'llamada-agendada': 7478652894, 'venta': 7470245510},
    # Conquer Legal: solo lead y schedule (la venta/reserva las envía el CRM).
    'cg': {'registro-lead': 7658662713, 'llamada-agendada': 7658662719},
}

SCHOOL_NAMES = {
    'cb': 'Blocks',
    'cl': 'Languages',
    'cf': 'Finance',
    'fi': 'Finance',
    'cg': 'Legal',
}

SCHOOL_VIDEO_URLS = {
    'cb': 'https://video.conquerblocks.com/',
    'cl': 'https://video.conquerlanguages.com/',
    'cf': 'https://video.conquerfinance.com/',
    'fi': 'https://video.conquerfinance.com/',
}

# Mapa de escuela (slug largo de conquer-calendar) → código de 2 letras.
# conquer-calendar usa 'conquer-blocks'/'conquer-finance'/'conquer-languages'
# (con guion); funnels usa 'conquerblocks' (sin guion) y códigos cb/cf/cl/fi.
SCHOOL_SLUG_TO_CODE = {
    'conquer-blocks': 'cb',
    'conquerblocks': 'cb',
    # Especialización es una variante de Conquer Blocks: usa las mismas tags (cb),
    # igual que el CRM (no existe una escuela/tag 'esp' separada).
    'conquer-blocks-esp': 'cb',
    'conquerblocksesp': 'cb',
    'conquer-finance': 'cf',
    'conquerfinance': 'cf',
    'conquer-languages': 'cl',
    'conquerlanguages': 'cl',
    # Languages for Kids es una variante de Conquer Languages: usa las tags (cl).
    'conquer-languages-kids': 'cl',
    'conquerlanguageskids': 'cl',
    'conquer-legal': 'cg',
    'conquerlegal': 'cg',
}


def hash_value(value):
    """SHA256 hash of lowercased, stripped string. Returns None if empty."""
    if not value:
        return None
    normalized = str(value).lower().strip()
    if not normalized:
        return None
    return hashlib.sha256(normalized.encode('utf-8')).hexdigest()


def normalize_phone(phone, prefix=None):
    """Combine prefix + phone, return digits only (E.164 without +)."""
    raw = ''
    if prefix:
        raw += str(prefix).strip()
    if phone:
        raw += str(phone).strip()
    return ''.join(c for c in raw if c.isdigit())


def hash_phone(phone, prefix=None):
    """Normalize phone and return SHA256 hash."""
    digits = normalize_phone(phone, prefix)
    return hash_value(digits) if digits else None


def get_school_code(lead):
    """Extract 2-letter school code from lead's funnel or school field."""
    school = (lead.school or '').lower().strip()

    if school in SCHOOL_SLUG_TO_CODE:
        return SCHOOL_SLUG_TO_CODE[school]

    # Already a code?
    if school in ('cb', 'cf', 'cl', 'fi', 'cg'):
        return school

    # Try funnel field (e.g., 'cb-eu', 'fi-latam', 'legal-eu')
    funnel = (lead.funnel or '').lower().strip()
    if '-' in funnel:
        code = funnel.split('-')[0]
        if code in ('cb', 'cf', 'cl', 'fi', 'cg'):
            return code
        # El slug del funnel de Conquer Legal es 'legal-<region>'.
        if code == 'legal':
            return 'cg'

    # Try mapping form keys to schools
    funnel_upper = lead.funnel or ''
    if funnel_upper.startswith('Full') or funnel_upper.startswith('Esp'):
        return 'cb'
    if funnel_upper.startswith('PropTrading'):
        return 'cf'
    if funnel_upper.startswith('English'):
        return 'cl'

    return None


def get_region_from_lead(lead):
    """Determine region (LATAM, EU, USA) from lead data. Default: LATAM."""
    funnel = (lead.funnel or '').strip()
    if funnel:
        funnel_lower = funnel.lower()
        if '-' in funnel_lower:
            # La región puede no ser el último segmento: slugs de variante
            # como 'cb-eu-2' (segundo experimento EU de Blocks) llevan un
            # sufijo extra después de la región ('2'), así que se prueban
            # TODOS los segmentos, no solo el último — si no, 'cb-eu-2' caía
            # al fallback de LATAM porque 'eu-2'.split('-')[-1] == '2'.
            for part in funnel_lower.split('-'):
                if part in FUNNEL_REGION_MAP:
                    return FUNNEL_REGION_MAP[part]
        for suffix, region in FUNNEL_REGION_MAP.items():
            if funnel_lower.endswith(suffix):
                return region

    campaign = (lead.utm_campaign or '').strip()
    if campaign and '_' in campaign:
        last_part = campaign.split('_')[-1]
        if last_part in CAMPAIGN_REGION_MAP:
            return CAMPAIGN_REGION_MAP[last_part]

    return 'LATAM'


def get_conversion_value(region, event_type='lead'):
    """Get EUR conversion value by region and event type."""
    return CONVERSION_VALUES.get(event_type, {}).get(region, 1)


def is_from_meta(lead):
    src = (lead.utm_source or '').lower()
    return src == 'metaads' or bool(lead.fbclid)


# Paridad con el pixel del navegador (misma regla que el CRM viejo): el pixel
# de Meta dispara Lead en estas landings para CUALQUIER fuente de tráfico, así
# que la API de conversiones debe enviar también todos esos leads — no solo los
# de MetaAds — para mantener la cobertura y la deduplicación por event_id.
PIXEL_LEAD_LANDING_PATTERNS = ('evento-online', 'clase-online-gratuita')


def fires_pixel_lead(lead):
    page_url = (lead.page_url or '').lower()
    return any(pattern in page_url for pattern in PIXEL_LEAD_LANDING_PATTERNS)


def is_from_tiktok(lead):
    src = (lead.utm_source or '').lower()
    return 'tiktok' in src or bool(lead.ttclid)


def is_from_google(lead):
    src = (lead.utm_source or '').lower()
    return src == 'googleads' or bool(lead.gclid) or bool(lead.gbraid) or bool(lead.wbraid)


def es_lead_de_lanzamiento(lead):
    """¿Es un lead de una pantalla de evento y no del funnel?

    Se mira el `funnel` porque es el discriminador que usaba el escenario viejo
    de Make y con el que el CRM los indexa.

    Dos formas de serlo. La mayoría lleva "lanzamiento" en el código
    (`cb-lanzamiento11`, `cl-lanzamiento9`, `cf-lanzamiento11`…). Las páginas de
    campaña no: la Coding Week manda `cb-codingweek5-eu`, y sin embargo en Make
    consume las mismas dos operaciones —webhook e ingest— que un lanzamiento,
    porque sus ramas de correo y Respond.io están apagadas igual. Por eso sus
    códigos se leen de la propia configuración de esas páginas, que es la única
    fuente que sabe cuáles son.
    """
    funnel = (getattr(lead, 'funnel', '') or '').lower()
    if not funnel:
        return False
    if 'lanzamiento' in funnel:
        return True
    # Import perezoso: `funnels` importa servicios de leads y al revés.
    from calendario.funnels.evento_views import PAGINAS_DE_CAMPANA
    codigos = set()
    for pagina in PAGINAS_DE_CAMPANA.values():
        # Hay páginas de campaña que no recogen datos y no declaran funnel.
        codigo = (pagina.get('funnel') or '').lower()
        if not codigo:
            continue
        codigos.add(codigo)
        # A las que tienen test A/B se les pega la letra de la variante al
        # código (`cf-tradingweek4-a`), y es esa la que llega al CRM: sin
        # incluirlas, el lead no se reconocería como de lanzamiento y se iría
        # por el pipeline completo del funnel.
        for variante in pagina.get('variantes') or ():
            codigos.add(f"{codigo}-{variante['codigo']}".lower())
    return funnel in codigos
