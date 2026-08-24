"""Middleware del embebido en el LMS."""
from .embed import PARAM, AccesoDenegado, leer_token


class EmbedCsrfMiddleware:
    """Exime del CSRF a las peticiones que traen un token válido del LMS.

    Por qué hace falta: dentro de un iframe de otro dominio el navegador trata
    las cookies como de terceros. Con el `SameSite=Lax` que Django pone por
    defecto no manda la cookie `csrftoken`, así que el POST de la reserva
    fallaría con un 403 incomprensible. Y poner `SameSite=None` tampoco
    resuelve: Safari bloquea las cookies de terceros de todas formas.

    Por qué es seguro quitarlo aquí: el CSRF protege de que un tercero use la
    sesión de la víctima sin que ella lo sepa. Este flujo no usa sesión ni
    cookie ninguna —la identidad va dentro del token—, así que no hay nada que
    suplantar. Y el token mismo hace de prueba de origen: sin el secreto
    compartido con el LMS no se puede fabricar uno.

    Solo se exime cuando la firma valida de verdad; un `?t=` cualquiera no
    abre la puerta. Se lee únicamente del querystring a propósito: tocar
    `request.POST` desde un middleware consume el cuerpo de la petición y le
    rompe `request.body` a las vistas que lo necesitan (los webhooks, las
    subidas de archivos del panel).
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.method == 'POST' and request.GET.get(PARAM):
            try:
                leer_token(request.GET[PARAM].strip())
            except AccesoDenegado:
                pass
            else:
                request._dont_enforce_csrf_checks = True
        return self.get_response(request)
