/* Selector de prefijo telefónico de las pantallas de evento.
 *
 * Réplica del componente del Webflow original: un botón con la bandera, el
 * prefijo y un chevron, pegado al campo del número, y un desplegable con
 * buscador.
 *
 * El país se resuelve en tres pasos. Primero el que manda el servidor en
 * `data-pais`, que sale de la cabecera de país que reenvía el Worker: cuando
 * llega es gratis e instantáneo. Si no viene —entrando directo por
 * calendar.conquerx.com, o en local— se pregunta por IP. Si eso también falla,
 * España.
 *
 * La consulta por IP va a geojs.io, que es la que usa el funnel
 * (`useGeoLocation`). El original de Webflow usaba ipapi.co, pero su plan
 * gratuito responde 429 a poco tráfico que haya, así que el respaldo no
 * respaldaba nada. Se lanza nada más cargar el fichero, en paralelo con la
 * lista de países, para que no haya que esperar una detrás de la otra.
 *
 * Las banderas salen de flagcdn.com, como en el original. Si no cargan, el
 * <img> queda vacío y el prefijo se sigue viendo: no se pierde funcionalidad.
 */
(function () {
  var raiz = document.querySelector('[data-prefijo]');
  if (!raiz) return;

  // Se dispara ya, sin esperar a la lista de países: cuando esta llegue, lo más
  // probable es que el país esté resuelto y el prefijo se pinte de una vez.
  var geo = fetch('https://get.geojs.io/v1/ip/country.json')
    .then(function (r) { return r.json(); })
    .then(function (d) { return (d && d.country ? String(d.country) : '').toUpperCase(); })
    .catch(function () { return ''; });

  var boton = raiz.querySelector('.prefijo-boton');
  var bandera = raiz.querySelector('.prefijo-bandera');
  var etiqueta = raiz.querySelector('.prefijo-valor');
  var panel = raiz.querySelector('.prefijo-panel');
  var buscador = raiz.querySelector('.prefijo-buscador');
  var lista = raiz.querySelector('.prefijo-lista');
  var oculto = document.getElementById('phonePrefix');
  var ocultoPais = document.getElementById('countryName');

  var paises = [];
  var elegido = null;

  function pintarElegido(p) {
    elegido = p;
    bandera.src = 'https://flagcdn.com/w40/' + p.iso2.toLowerCase() + '.png';
    bandera.alt = p.iso2;
    etiqueta.textContent = p.prefijo;
    oculto.value = p.prefijo;
    if (ocultoPais) ocultoPais.value = p.pais;
  }

  function pintarLista(filtro) {
    var texto = (filtro || '').trim().toLowerCase();
    var visibles = texto
      ? paises.filter(function (p) {
          return p.pais.toLowerCase().indexOf(texto) >= 0 || p.prefijo.indexOf(texto) >= 0;
        })
      : paises;
    lista.innerHTML = '';
    visibles.slice(0, 300).forEach(function (p) {
      var li = document.createElement('button');
      li.type = 'button';
      li.className = 'prefijo-opcion';
      li.innerHTML = '<img src="https://flagcdn.com/w40/' + p.iso2.toLowerCase() + '.png" alt="" width="24">' +
                     '<span class="prefijo-pais">' + p.pais + '</span>' +
                     '<span class="prefijo-codigo">' + p.prefijo + '</span>';
      li.addEventListener('click', function () { pintarElegido(p); cerrar(); });
      lista.appendChild(li);
    });
  }

  function abrir() {
    panel.hidden = false;
    boton.setAttribute('aria-expanded', 'true');
    buscador.value = '';
    pintarLista('');
    buscador.focus();
  }
  function cerrar() {
    panel.hidden = true;
    boton.setAttribute('aria-expanded', 'false');
  }

  boton.addEventListener('click', function () { panel.hidden ? abrir() : cerrar(); });
  buscador.addEventListener('input', function () { pintarLista(buscador.value); });
  document.addEventListener('click', function (ev) { if (!raiz.contains(ev.target)) cerrar(); });
  document.addEventListener('keydown', function (ev) { if (ev.key === 'Escape' && !panel.hidden) { cerrar(); boton.focus(); } });

  fetch(raiz.dataset.prefijo)
    .then(function (r) { return r.json(); })
    .then(function (datos) {
      paises = datos;
      // Reino Unido aparece cinco veces (Inglaterra, Escocia, Gales, Irlanda
      // del Norte y el propio Reino Unido), como en la lista del original, y
      // por orden alfabético la primera es Escocia. Para la preselección
      // automática manda el nombre del país, no la nación: en el histórico del
      // CRM hay 1.785 leads con prefijo +44 como «Reino Unido» y 43 como
      // «Scotland». En el desplegable se siguen viendo las cinco.
      var CANONICO = { GB: 'Reino Unido' };
      var porIso = function (iso) {
        var iguales = paises.filter(function (p) { return p.iso2 === iso; });
        if (iguales.length > 1 && CANONICO[iso]) {
          var c = iguales.filter(function (p) { return p.pais === CANONICO[iso]; })[0];
          if (c) return c;
        }
        return iguales[0];
      };
      pintarLista('');

      // Cloudflare manda `XX` cuando no sabe y `T1` para Tor; ninguno está en la
      // lista, así que caen solos al siguiente paso.
      var delServidor = porIso(raiz.dataset.pais || '');
      if (delServidor) { pintarElegido(delServidor); return; }

      // Mientras llega la respuesta por IP se deja España puesta, que es lo que
      // ya traen los campos ocultos del formulario.
      pintarElegido(porIso('ES') || paises[0]);
      return geo.then(function (iso) {
        var p = porIso(iso);
        if (p) pintarElegido(p);
      });
    })
    .catch(function () { /* sin geo se queda el país por defecto */ });
})();
