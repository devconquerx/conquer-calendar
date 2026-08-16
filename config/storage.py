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

    def hashed_name(self, name, content=None, filename=None):
        # Los archivos de frontend/dist/assets/ ya vienen con un hash de
        # contenido puesto por Vite (p.ej. funnel-Cl5WoCiK.js), y los chunks
        # lazy (VideoPage/Funnel/Confirmation) se importan entre sí por ESE
        # nombre exacto: Rollup graba el `import ... from "./funnel-Cl5WoCiK.js"`
        # tal cual en build time, y Django/WhiteNoise no reescriben imports de
        # JS (solo url() en CSS). Si además les ponemos NUESTRO hash encima,
        # el <script> de entrada (que sí pasa por aquí vía {% vite_asset %})
        # queda en una URL distinta a la que usan esos imports internos: el
        # navegador carga el mismo módulo dos veces bajo dos URLs → dos copias
        # de React → "Invalid hook call" (React #321) en cualquier hook de un
        # chunk lazy (useRouter en VideoPage, useTheme, etc.), en cualquier
        # escuela. Dejamos estos archivos tal cual: ya son inmutables por
        # contenido gracias al hash de Vite, el de Django es puro riesgo.
        if name.startswith('assets/'):
            return name
        return super().hashed_name(name, content=content, filename=filename)

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
