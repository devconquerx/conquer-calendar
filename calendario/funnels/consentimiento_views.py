# -*- coding: utf-8 -*-
"""Sirve el banner de consentimiento como un JavaScript suelto.

El dominio de cada marca está partido: los embudos y las páginas de evento los
sirve Django, y el resto Webflow. El banner solo existía en las plantillas de
Django, así que en la mitad de Webflow seguía saliendo el de Cookiebot, con otro
diseño y otra decisión guardada.

Esto lo empaqueta en un fichero que Webflow carga con una línea en su código
global, ANTES del snippet de GTM y sin `async` ni `defer`:

    <script src="https://www.conquerblocks.com/f/conquerx-cookies.js"></script>

Va bajo `/f/` a propósito: ese prefijo YA está enrutado a Django en los cuatro
dominios de marca (comprobado: devuelven 405 a un GET, o sea que la ruta existe
y llega), así que no hace falta tocar Cloudflare. Y como pasa por el Worker,
sigue llegando `X-Visitor-Country`, que es de donde sale saber si a ese visitante
hay que pedirle permiso previo o basta con informarle. Servirlo desde
calendar.conquerx.com habría sido más cómodo, pero esa cabecera se pierde y el
código asume Europa cuando no sabe el país: banner bloqueante para LATAM y
Estados Unidos, donde la ley no lo exige.

Parámetros de la URL:
    ?marca=conquer-blocks   QUÉ MARCA. Ponlo siempre (ver abajo).
    ?cookiebot=1            no impide que cargue Cookiebot (para comparar)
    ?debug=1                saca el banner aunque ya se haya decidido

`marca` hay que ponerla a mano, aunque el dominio ya lo diga. El Worker de
Cloudflare va con `PRESERVE_HOST = false`, así que reescribe el Host y Django ve
`calendar.conquerx.com` en vez de `www.conquerblocks.com`: deducir la marca del
dominio dejaría el banner con los colores neutros en las cuatro. La deducción se
mantiene como red de seguridad —funciona si algún día se preserva el Host, o si
alguien pide el fichero directamente al origen—, pero el snippet de Webflow debe
llevar `?marca=`, y como es uno por sitio tampoco cuesta nada.
"""
import logging
from pathlib import Path

from django.http import HttpResponse
from django.template.loader import render_to_string
from django.views.decorators.http import require_GET

from . import consentimiento as consent

logger = logging.getLogger(__name__)

# Dominio → escuela. Se busca por sufijo, así que cubre el ápice y cualquier
# subdominio (www, staging…). Sin coincidencia se usa la marca por defecto, que
# es la neutra de `consentimiento.MARCAS`.
DOMINIOS = (
    ('conquerblocks.com', 'conquer-blocks'),
    ('conquerfinance.com', 'conquer-finance'),
    ('conquerlanguages.com', 'conquer-languages'),
    ('conquerlegal.com', 'conquer-legal'),
)

# El comportamiento vive en el mismo fichero que usan las páginas de Django. Se
# lee del disco y se incrusta en el bundle en vez de enlazarlo: una segunda
# petición podría llegar tarde o fallar, y el diálogo se quedaría pintado pero
# muerto, con los botones sin responder.
_CONDUCTA = Path(__file__).resolve().parent.parent / 'static' / 'js' / 'consentimiento.js'


def _escuela_desde_dominio(host):
    host = (host or '').split(':')[0].lower()
    for dominio, escuela in DOMINIOS:
        if host == dominio or host.endswith('.' + dominio):
            return escuela
    return ''


@require_GET
def conquerx_cookies_js(request):
    escuela = (request.GET.get('marca') or '').strip() or _escuela_desde_dominio(
        request.headers.get('X-Forwarded-Host') or request.get_host()
    )
    if not escuela:
        # Sale con la paleta neutra, que funciona pero no es la de nadie. Casi
        # siempre significa que al snippet le falta `?marca=`.
        logger.warning(
            'conquerx-cookies.js sin marca (host=%s, referer=%s): se sirve la paleta neutra',
            request.get_host(), request.headers.get('Referer', '—'),
        )

    try:
        conducta = _CONDUCTA.read_text(encoding='utf-8')
    except OSError:
        # Sin el comportamiento no hay banner que valga: mejor no servir nada
        # que pintar un diálogo con los botones muertos.
        logger.exception('No se pudo leer %s', _CONDUCTA)
        return HttpResponse('/* consentimiento no disponible */',
                            content_type='application/javascript', status=500)

    ctx = {'consentimiento': consent.contexto(request, escuela)}
    cuerpo = render_to_string('js/conquerx-cookies.js', {
        **ctx,
        'css': render_to_string('_includes/_consentimiento_estilos.html', ctx, request),
        'markup': render_to_string('_includes/_consentimiento_markup.html', ctx, request),
        'conducta': conducta,
        'bloquear_cookiebot': request.GET.get('cookiebot') != '1',
    }, request)

    respuesta = HttpResponse(cuerpo, content_type='application/javascript; charset=utf-8')
    # La respuesta depende del país del visitante, así que no puede quedarse en
    # ninguna caché compartida: un visitante de Madrid serviría su banner
    # bloqueante a uno de Lima, y al revés.
    respuesta['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
    # Lo carga un dominio distinto del que lo sirve cuando se prueba desde otra
    # marca; un <script src> no necesita CORS, pero sí lo necesita quien quiera
    # depurarlo con fetch.
    respuesta['Access-Control-Allow-Origin'] = '*'
    return respuesta
