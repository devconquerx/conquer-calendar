"""Almacenamiento de estáticos y utilidades de caché."""

from whitenoise.storage import CompressedManifestStaticFilesStorage


class TolerantManifestStaticFilesStorage(CompressedManifestStaticFilesStorage):
    """Versiona los estáticos por hash sin que una referencia rota tumbe el build.

    El hash en el nombre (`logo.46247ae7c3c1.png`) es lo que hace que al cambiar
    un archivo cambie su URL: el navegador pide la versión nueva sin que el
    usuario tenga que forzar la recarga.

    Los bundles de Metronic apuntan a sourcemaps `.map` que no vienen en el
    paquete. Sin esta tolerancia, `collectstatic` aborta y con él el arranque
    entero de producción, que lo ejecuta al inicio.
    """

    # Que falte una entrada en el manifiesto no debe reventar la página en runtime.
    manifest_strict = False

    def post_process(self, paths, dry_run=False, **options):
        for name, hashed_name, processed in super().post_process(paths, dry_run, **options):
            if isinstance(processed, Exception):
                # El archivo se copia igual, solo se queda sin reescribir sus
                # referencias internas.
                processed = False
            yield name, hashed_name, processed


class NoCacheStaticMiddleware:
    """Impide que el navegador cachee los estáticos en desarrollo.

    En producción no hace falta: allí los nombres llevan hash. Pero `runserver`
    los sirve sin `Cache-Control`, y entonces el navegador aplica su heurística
    y se queda con copias viejas durante días — de ahí el Ctrl+Shift+R.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        if request.path.startswith('/static/'):
            response['Cache-Control'] = 'no-store, must-revalidate'
        return response
