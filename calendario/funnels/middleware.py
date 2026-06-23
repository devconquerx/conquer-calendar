"""Middleware para servir el funnel público bajo un prefijo de path opcional
(p.ej. /preview) sin duplicar rutas.

Caso de uso: probar el funnel en un dominio cuyo tráfico raíz lo sirve otro
sistema (Webflow en www.conquerblocks.com) interceptando solo el prefijo en
Cloudflare y proxyándolo a este origen (Django). El Worker enruta /preview/*
—junto con los assets /static, la API /f y /media— hacia Django; aquí
detectamos el prefijo, lo retiramos de PATH_INFO para que el resolver case con
las rutas canónicas, y lo dejamos en request.app_base_path para que las vistas
del funnel antepongan ese prefijo a las URLs de navegación que emiten
(next_url, confirmation_url). Así el flujo encadenado (landing → vídeo →
stepform → confirmación) permanece dentro de /preview y las páginas reales de
Webflow quedan intactas.

Sin prefijo (p.ej. calendar.conquerx.com), app_base_path queda '' y todo se
comporta igual que hoy.
"""

from django.conf import settings


class AppBasePathMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response
        # Normaliza los prefijos configurados: con barra inicial, sin barra
        # final, descartando vacíos o la raíz.
        self.prefixes = []
        for raw in getattr(settings, 'FUNNEL_BASE_PATHS', ['/preview']) or []:
            prefix = '/' + raw.strip().strip('/')
            if prefix != '/':
                self.prefixes.append(prefix)

    def __call__(self, request):
        request.app_base_path = ''
        path = request.path_info
        for prefix in self.prefixes:
            if path == prefix or path.startswith(prefix + '/'):
                request.app_base_path = prefix
                # Retira el prefijo para que el resolver de URLs case con las
                # rutas canónicas. request.path conserva el original (útil para
                # logs y URIs absolutas).
                request.path_info = path[len(prefix):] or '/'
                break
        return self.get_response(request)


# Vistas que sirven las landings públicas del funnel donde se inyecta el GTM
# (landing, vídeo, stepform, calendario de reserva y confirmación de llamada).
# Son las únicas páginas que necesitan relajar el COOP (ver más abajo).
_PUBLIC_PAGE_VIEW_MODULES = (
    'calendario.funnels.views',          # FunnelClase/Video/Agenda/Confirmation
    'calendario.bookings.views_public',  # stepform y página de reserva
)
# Excepciones dentro de esos módulos que NO son landings públicas.
_PUBLIC_PAGE_VIEW_EXCLUDE = {'FunnelStatusView'}


class FunnelPublicCoopMiddleware:
    """Relaja Cross-Origin-Opener-Policy SOLO en las landings públicas del funnel.

    Django (SecurityMiddleware) sirve `Cross-Origin-Opener-Policy: same-origin`
    en todo el sitio. Eso aísla la ventana en su propio browsing-context-group y
    deja `window.opener` en null, lo que impide que el Preview de Google Tag
    Manager / Tag Assistant —que abre la página como popup y se comunica vía
    `window.opener`— establezca conexión ("the window was closed before a
    connection could be established").

    Solo las páginas públicas del funnel cargan GTM y necesitan depurarse, así
    que aquí las marcamos con `unsafe-none` (único valor que mantiene el vínculo
    con un opener de otro origen como tagassistant.google.com). El resto de la
    app —panel, reservas internas, admin— conserva la protección `same-origin`.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        if not response.get('Content-Type', '').startswith('text/html'):
            return response
        match = getattr(request, 'resolver_match', None)
        func = getattr(match, 'func', None) if match else None
        if func is None:
            return response
        module = getattr(func, '__module__', '')
        view_name = getattr(func, '__name__', '')
        view_class = getattr(func, 'view_class', None)
        if view_class is not None:
            view_name = view_class.__name__
        if module in _PUBLIC_PAGE_VIEW_MODULES and view_name not in _PUBLIC_PAGE_VIEW_EXCLUDE:
            response['Cross-Origin-Opener-Policy'] = 'unsafe-none'
        return response
