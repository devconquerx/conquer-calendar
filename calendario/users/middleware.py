from django.http import HttpResponsePermanentRedirect


class StripTrailingDotHostMiddleware:
    """
    Redirige 301 cualquier request cuyo Host termine en '.' a la versión sin punto.

    El punto final en el dominio (FQDN canonical) es válido en DNS pero los navegadores
    tratan 'host.tld.' y 'host.tld' como hosts distintos para cookies. Eso rompía el
    flujo OAuth: la cookie de sesión (con el state de allauth) quedaba bajo el host
    con punto y el callback de Google entraba al host sin punto, por lo que el state
    no se recuperaba y allauth abortaba con AuthError.UNKNOWN.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        host = request.get_host()
        if ":" in host:
            name, _, port = host.rpartition(":")
            port = ":" + port
        else:
            name, port = host, ""
        if name.endswith("."):
            scheme = "https" if request.is_secure() else "http"
            new_url = f"{scheme}://{name.rstrip('.')}{port}{request.get_full_path()}"
            return HttpResponsePermanentRedirect(new_url)
        return self.get_response(request)
