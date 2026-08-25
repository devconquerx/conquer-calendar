# -*- coding: utf-8 -*-
"""Consentimiento de cookies propio, en sustitución de Cookiebot.

Cookiebot lo inyecta el contenedor de GTM de cada marca, no este código, así que
en las páginas que sirve Django convivían dos cosas: su banner —con un diseño
que no encaja con ninguna de las tres marcas— y todo lo demás. Aquí se monta el
nuestro y se impide que el suyo se cargue en estas páginas.

Se replica su comportamiento, no solo su aspecto:

- Las mismas cuatro categorías: necesarias (siempre), preferencias,
  estadísticas y marketing.
- Solo se pregunta donde hay una normativa que lo exige. Fuera de ahí Cookiebot
  no muestra nada y da el consentimiento por implícito (`method: "implied"`,
  `gdprApplies: false`), y aquí igual: añadir un banner en LATAM y US, que es de
  donde viene la mayoría del tráfico, sería fricción nueva que hoy no existe.
- Google Consent Mode v2, con los mismos eventos al dataLayer que empuja su
  plantilla de GTM (`cookie_consent_<categoría>` por cada una aceptada y
  `cookie_consent_update` al final), para que los triggers que ya existen en los
  contenedores sigan funcionando sin tocarlos.

Lo que se pierde respecto a Cookiebot y conviene tener presente: su registro de
consentimientos como prueba ante una inspección, y el escaneo automático que
mantiene al día la tabla de cookies de la política de privacidad. Lo primero se
cubre guardando la decisión con fecha y versión; lo segundo pasa a ser trabajo
manual.
"""

# Países donde se pregunta antes de activar nada.
#
# Los 27 del EEE más Islandia, Liechtenstein y Noruega (RGPD por el acuerdo del
# Espacio Económico Europeo), Reino Unido (UK GDPR), Suiza (nLPD) y Brasil
# (LGPD, que también es de consentimiento previo).
#
# NO cubre California: la CCPA es de exclusión —basta un enlace de "no vendas
# mis datos", no un banner previo— y además `CF-IPCountry` da país, no estado,
# así que gatearla aquí significaría preguntar a todo Estados Unidos.
PAISES_CON_CONSENTIMIENTO_PREVIO = frozenset({
    # Unión Europea
    'AT', 'BE', 'BG', 'CY', 'CZ', 'DE', 'DK', 'EE', 'ES', 'FI', 'FR', 'GR',
    'HR', 'HU', 'IE', 'IT', 'LT', 'LU', 'LV', 'MT', 'NL', 'PL', 'PT', 'RO',
    'SE', 'SI', 'SK',
    # Resto del Espacio Económico Europeo
    'IS', 'LI', 'NO',
    # Reino Unido y Suiza
    'GB', 'CH',
    # Brasil
    'BR',
})

# Sube cuando cambien las categorías o los textos: un consentimiento guardado
# con una versión anterior se vuelve a pedir, porque ya no se dio sobre lo mismo.
VERSION = 1

# Paleta por marca. El banner es el mismo componente en las tres; lo único que
# cambia es el acento, la tipografía y el redondeo, para que no parezca —como el
# de Cookiebot— una pieza pegada de otro sitio.
MARCAS = {
    'conquer-blocks': {
        'politica_url': 'https://www.conquerblocks.com/politica-de-privacidad',
        'acento': '#ff4000',
        'acento_texto': '#ffffff',
        'fuente': "'Funnel Display',Arial,sans-serif",
        'radio': '8px',
    },
    'conquer-finance': {
        'politica_url': 'https://www.conquerfinance.com/politica-de-privacidad',
        'acento': '#3ac043',
        'acento_texto': '#ffffff',
        'fuente': "'Funnel Display',Arial,sans-serif",
        'radio': '8px',
    },
    'conquer-languages': {
        'politica_url': 'https://www.conquerlanguages.com/politica-de-privacidad',
        'acento': '#15b961',
        'acento_texto': '#ffffff',
        'fuente': 'Poppins,Arial,sans-serif',
        'radio': '20px',
    },
    'conquer-legal': {
        'politica_url': 'https://www.conquerlegal.com/politica-de-privacidad',
        'acento': '#1d4ed8',
        'acento_texto': '#ffffff',
        'fuente': 'Poppins,Arial,sans-serif',
        'radio': '10px',
    },
}

_POR_DEFECTO = {
    'politica_url': '/politica-de-privacidad',
    'acento': '#171717',
    'acento_texto': '#ffffff',
    'fuente': 'system-ui,-apple-system,Segoe UI,Roboto,Arial,sans-serif',
    'radio': '10px',
}


def aplica(request):
    """¿Hay que pedir consentimiento a quien está mirando?

    Se resuelve con `CF-IPCountry`, la misma cabecera con la que la pantalla de
    evento preselecciona el prefijo. Si no viene —fuera de Cloudflare o en
    local— se pregunta: ante la duda, pedir permiso es lo correcto y lo barato.
    """
    pais = (request.headers.get('CF-IPCountry') or '').upper()
    if not pais or pais in ('XX', 'T1', 'T2'):
        return True
    return pais in PAISES_CON_CONSENTIMIENTO_PREVIO


def marca(escuela):
    return MARCAS.get((escuela or '').strip().lower(), _POR_DEFECTO)


def contexto(request, escuela=None):
    m = marca(escuela)
    return {
        'aplica': aplica(request),
        'version': VERSION,
        'marca': m,
        'politica_url': m['politica_url'],
    }
