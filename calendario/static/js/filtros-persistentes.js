/**
 * Recuerda en localStorage los filtros aplicados en un listado del panel.
 *
 * Se carga al principio del contenido de la página (antes de pintar el
 * listado) para que la redirección no provoque parpadeo:
 *
 *   <script src="{% static 'js/filtros-persistentes.js' %}"
 *           data-clave="event_types"
 *           data-limpiar=".js-limpiar-filtros"></script>
 *
 * - Si la URL trae filtros, los guarda.
 * - Si la URL no trae ninguno y hay guardados, redirige a ellos.
 * - Al pulsar un enlace de "Limpiar" se borra lo guardado.
 */
(function () {
    var script = document.currentScript;
    if (!script) return;

    var clave = 'panel:filtros:' + (script.dataset.clave || window.location.pathname);
    var selectorLimpiar = script.dataset.limpiar || '';

    function leer() {
        try {
            return window.localStorage.getItem(clave);
        } catch (e) {
            return null;
        }
    }

    function guardar(valor) {
        try {
            if (valor) {
                window.localStorage.setItem(clave, valor);
            } else {
                window.localStorage.removeItem(clave);
            }
        } catch (e) { /* modo privado o storage lleno: se ignora */ }
    }

    if (selectorLimpiar) {
        document.addEventListener('click', function (ev) {
            var destino = ev.target;
            if (destino && destino.closest && destino.closest(selectorLimpiar)) {
                guardar(null);
            }
        });
    }

    // Se descarta 'page' (no es un filtro) y los valores vacíos que manda el
    // formulario al enviarse sin rellenar.
    var params = new URLSearchParams();
    new URLSearchParams(window.location.search).forEach(function (valor, nombre) {
        if (nombre !== 'page' && valor !== '') {
            params.append(nombre, valor);
        }
    });

    if (window.location.search.replace('?', '')) {
        guardar(params.toString());
        return;
    }

    var guardados = leer();
    if (guardados) {
        window.location.replace(window.location.pathname + '?' + guardados);
    }
})();
