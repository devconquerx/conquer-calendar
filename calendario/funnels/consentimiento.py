# -*- coding: utf-8 -*-
"""Consentimiento de cookies propio, en sustitución de Cookiebot.

Cookiebot lo inyecta el contenedor de GTM de cada marca, no este código, así que
en las páginas que sirve Django convivían dos cosas: su banner —con un diseño
que no encaja con ninguna de las tres marcas— y todo lo demás. Aquí se monta el
nuestro y se impide que el suyo se cargue en estas páginas.

Se replica su comportamiento, no solo su aspecto:

- Las mismas cuatro categorías: necesarias (siempre), preferencias,
  estadísticas y marketing.
- Dos modos, según desde dónde se entre, porque la ley no es la misma:

  · EXPLÍCITO en el Espacio Económico Europeo, Reino Unido, Suiza y Brasil. El
    RGPD exige consentimiento previo e inequívoco: hasta que no se pulsa, no se
    activa nada. Es lo que hace el modo por defecto de Consent Mode.

  · IMPLÍCITO en el resto: LATAM (salvo Brasil) y Estados Unidos. Ahí el aviso
    también se muestra, pero no bloquea: informa de que «al continuar
    navegando, aceptas su uso», el consentimiento se concede desde el principio
    y se cierra solo al seguir navegando. California y los estados con leyes
    parecidas son de EXCLUSIÓN, así que lo que exigen no es permiso previo sino
    poder retirarlo, y para eso está el botón de configurar y el icono.

  El aviso sale SIEMPRE; lo que cambia es el modelo. Si se comprueba contra
  Cookiebot y en alguna región no aparece nada, mirar su configuración antes de
  tocar esto: tenía los países de LATAM desmarcados, y por eso no salía.
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

# Paleta por marca. El banner es el mismo componente en las tres, pero cada una
# tiene su propio lenguaje visual y hay que hablarlo, o vuelve a parecer —como
# el de Cookiebot— una pieza pegada de otro sitio:
#
#   papel → tarjeta de cartón con su textura, como el resto de tarjetas de
#           Blocks y Finance
#   pixel → CTA con el borde pixelado y el degradado de marca, el mismo del
#           «Ver vídeo gratis» del funnel
#
# Languages no usa ninguna de las dos: sus tarjetas son blancas y sus botones
# píldoras verdes, así que ahí el componente va liso y redondeado.
MARCAS = {
    'conquer-blocks': {
        'politica_url': 'https://www.conquerblocks.com/legal/politica-de-privacidad',
        'acento': '#ff4000',
        'acento_texto': '#ffffff',
        'fuente': "'Funnel Display',Arial,sans-serif",
        'radio': '10px',
        'papel': True,
        'pixel': True,
        'grad_1': '#ff4000',
        'grad_2': '#ff9800',
    },
    'conquer-finance': {
        'politica_url': 'https://www.conquerfinance.com/legal/politica-de-privacidad',
        'acento': '#3ac043',
        'acento_texto': '#ffffff',
        'fuente': "'Funnel Display',Arial,sans-serif",
        'radio': '10px',
        'papel': True,
        'pixel': True,
        'grad_1': '#aed916',
        'grad_2': '#3ac043',
    },
    'conquer-languages': {
        'politica_url': 'https://www.conquerlanguages.com/politica-de-privacidad',
        'acento': '#15b961',
        'acento_texto': '#ffffff',
        'fuente': 'Poppins,Arial,sans-serif',
        'radio': '20px',
    },
    'conquer-legal': {
        # Legal cuelga sus textos legales de /legal/; sin ese tramo la URL da
        # 404, no una redirección como en Blocks y Finance.
        'politica_url': 'https://www.conquerlegal.com/legal/politica-de-privacidad',
        'acento': '#0040FF',
        'acento_texto': '#ffffff',
        'fuente': "'Funnel Display',Arial,sans-serif",
        'radio': '10px',
        'papel': True,
        'pixel': True,
        # El CTA de Legal no es un degradado de dos paradas a 135deg como el de
        # Blocks: son tres, en horizontal, de periwinkle a navy. Se copia entero
        # en vez de aproximarlo con `grad_1`/`grad_2`.
        'gradiente': 'linear-gradient(90deg,#3E76FF 0%,#1845D6 42%,#031464 100%)',
    },
    # La corporativa del grupo. No es una escuela y no comparte su lenguaje:
    # fondo blanco liso, sin la textura de cartón, y el CTA es un rectángulo
    # gris oscuro casi sin redondear — nada de degradados ni de esquinas
    # pixeladas. Valores sacados del botón «Contacto» de www.conquerx.com:
    # `background rgb(51,51,51)`, `color #fff`, `border-radius 2px`, sin borde
    # y sin `clip-path`. Como los botones del banner se redondean con
    # `calc(var(--radio) - 2px)`, el radio va a 4px para que salgan a 2.
    'conquerx': {
        'politica_url': 'https://www.conquerx.com/politica-de-privacidad',
        'acento': '#333333',
        'acento_texto': '#ffffff',
        'fuente': "'Funnel Display',Arial,sans-serif",
        'radio': '4px',
    },
}

_POR_DEFECTO = {
    'politica_url': '/politica-de-privacidad',
    'acento': '#171717',
    'acento_texto': '#ffffff',
    'fuente': 'system-ui,-apple-system,Segoe UI,Roboto,Arial,sans-serif',
    'radio': '10px',
}


def modo(request):
    """`explicito` donde hace falta permiso previo; `implicito` en el resto.

    Se puede forzar con `?consent=eu` o `?consent=row` para poder revisar los
    dos sin fingir una IP, que es la única forma que había de verlos.
    """
    forzado_modo = (request.GET.get('consent') or '').lower()
    if forzado_modo in ('eu', 'explicito'):
        return 'explicito'
    if forzado_modo in ('row', 'implicito'):
        return 'implicito'
    return 'explicito' if _pide_permiso_previo(request) else 'implicito'


def forzado(request):
    """`?debug=1` saca el banner aunque no toque.

    Desde LATAM o US no se muestra —y ahí trabajamos casi siempre—, así que sin
    esto no hay forma de verlo ni de repasar cómo queda en cada marca sin
    fingir una IP europea. Además ignora la decisión ya guardada: si no,
    aceptaría una vez y no volvería a salir.
    """
    return request.GET.get('debug') == '1'


# Cabecera por la que llega el país del visitante.
#
# NO es `CF-IPCountry`. Cloudflare la reserva: el Worker que enruta los dominios
# de marca hacia Django corre en su red, y ahí los nombres que empiezan por
# `CF-` los gestiona Cloudflare —si el Worker intenta fijarla en la subpetición,
# se descarta—. Tampoco la pone Cloudflare por su cuenta, porque el origen
# (`calendar.conquerx.com`) no está detrás de Cloudflare: la añade al proxear
# hacia orígenes de sus propias zonas, y esta no lo es.
#
# Así que el Worker la reenvía con un nombre propio:
#
#     headers.set("X-Visitor-Country", request.cf?.country || "XX");
#
# Se sigue aceptando `CF-IPCountry` por si algún día el origen pasa a estar
# detrás de Cloudflare y la pone él.
CABECERA_PAIS = 'X-Visitor-Country'


def pais(request):
    """Código ISO del país del visitante, o cadena vacía si no se sabe."""
    return (request.headers.get(CABECERA_PAIS)
            or request.headers.get('CF-IPCountry')
            or '').upper()


def _pide_permiso_previo(request):
    """¿Está mirando desde un sitio donde hay que pedir permiso antes?

    Si no llega el país —fuera de Cloudflare, en local, o con la cabecera
    perdida por el camino— se asume que sí: ante la duda, pedir permiso es lo
    correcto y lo barato. El precio de equivocarse es enseñar el aviso
    bloqueante a quien no le tocaba; al revés sería medir sin permiso.
    """
    codigo = pais(request)
    if not codigo or codigo in ('XX', 'T1', 'T2'):
        return True
    return codigo in PAISES_CON_CONSENTIMIENTO_PREVIO


def aplica(request):
    """Siempre se enseña algo. Lo que cambia con la región es el modelo."""
    return True


def marca(escuela):
    return MARCAS.get((escuela or '').strip().lower(), _POR_DEFECTO)


def contexto(request, escuela=None):
    m = marca(escuela)
    return {
        'aplica': aplica(request),
        'modo': modo(request),
        'explicito': modo(request) == 'explicito',
        'forzado': forzado(request),
        'version': VERSION,
        'marca': m,
        'politica_url': m['politica_url'],
    }
