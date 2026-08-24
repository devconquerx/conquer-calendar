/* Selector de prefijo telefónico de las pantallas de evento.
 *
 * Réplica del componente del Webflow original: un botón con la bandera, el
 * prefijo y un chevron, pegado al campo del número, y un desplegable con
 * buscador.
 *
 * El país se resuelve en dos pasos. Primero el que manda el servidor en
 * `data-pais`, que sale de la cabecera CF-IPCountry: en producción llega
 * siempre y es gratis, sin llamadas externas ni parpadeo. Si no viene —fuera de
 * Cloudflare, o en local— se cae a ipapi.co, que es lo que usaba el original
 * (`setCountryByIP`). Si también falla, se queda España.
 *
 * Las banderas salen de flagcdn.com, como en el original. Si no cargan, el
 * <img> queda vacío y el prefijo se sigue viendo: no se pierde funcionalidad.
 */
(function () {
  var raiz = document.querySelector('[data-prefijo]');
  if (!raiz) return;

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
      var porIso = function (iso) {
        return paises.filter(function (p) { return p.iso2 === iso; })[0];
      };
      var delServidor = raiz.dataset.pais || '';
      var inicial = porIso(delServidor) || porIso('ES') || paises[0];
      if (inicial) pintarElegido(inicial);
      pintarLista('');

      // El servidor ya acertó: no hace falta molestar a nadie más.
      if (porIso(delServidor)) return;

      return fetch('https://ipapi.co/json/')
        .then(function (r) { return r.json(); })
        .then(function (d) {
          var p = porIso(d.country_code);
          if (p) pintarElegido(p);
        });
    })
    .catch(function () { /* sin geo se queda el país por defecto */ });
})();
