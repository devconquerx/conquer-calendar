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
