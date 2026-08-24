/* Registro de las pantallas de evento (lanzamiento).
 *
 * Crea el Lead en el calendario, que a su vez lo empuja al ingest del CRM por
 * Celery. Es el único destino, igual que en el escenario viejo de Make: los
 * leads de lanzamiento no pasan por Supabase, CAPI, Respond.io ni NeverBounce.
 *
 * Lo comparten las plantillas de las tres marcas, que solo se diferencian en el
 * diseño: Blocks abre el formulario en un popup y no tiene casilla de
 * privacidad; Languages lo lleva inline y la casilla es obligatoria. El script
 * se adapta a lo que encuentre en el DOM.
 */
(function () {
  var form = document.getElementById('formEvento');
  if (!form) return;

  var aviso = document.getElementById('aviso');
  var boton = form.querySelector('button[type=submit]');
  var privacidad = document.getElementById('privacidad');  // solo en Languages
  var enviado = false;

  function decir(texto, clase) {
    if (!aviso) return;
    aviso.className = 'aviso' + (clase ? ' ' + clase : '');
    aviso.textContent = texto;
  }

  function cookie(nombre) {
    var m = document.cookie.match('(^|;)\\s*' + nombre + '\\s*=\\s*([^;]+)');
    return m ? decodeURIComponent(m[2]) : '';
  }

  /* Los UTMs y los click ids viajan en la URL del anuncio; las cookies las
     dejan los píxeles. Se mandan solo los que traen valor, para no pisar en el
     CRM lo que ya tuviera ese lead de una visita anterior. */
  function atribucion() {
    var q = new URLSearchParams(location.search), datos = {};
    ['utm_source','utm_medium','utm_campaign','utm_content','utm_term','utm_idcampaign',
     'utm_adsetid','utm_adid','utm_title','gclid','gbraid','wbraid','fbclid','msclkid',
     'dclid','ttclid','gclsrc'].forEach(function (k) { if (q.get(k)) datos[k] = q.get(k); });
    ['_ga','_gid','_fbp','_fbc','_ttp'].forEach(function (k) {
      var v = cookie(k); if (v) datos[k] = v;
    });
    return datos;
  }

  /* Al registrarse, el original no se queda en la página: manda a la de
     "gracias", que es donde está el último paso de verdad —entrar al grupo de
     WhatsApp de los asistentes—. Quedarse aquí con un mensajito dejaba al
     registrado a medias y, si hay conversiones colgadas de esa página, sin
     registrar.

     Se replican los mismos parámetros que arrastra el original MENOS el nombre
     y el correo, que también viajaban en la URL: esa página no los lee, y los
     datos personales en una query string acaban en los logs del servidor, en
     el historial del navegador y en la cabecera Referer de cada recurso que
     cargue la página de destino. */
  function irAGracias() {
    var destino = window.__EVENTO__ && window.__EVENTO__.gracias;
    if (!destino) return;
    var q = new URLSearchParams(location.search);
    var p = new URLSearchParams({ v: '20250218' });
    ['utm_source','utm_medium','utm_campaign','utm_term','utm_content',
     'utm_idcampaign','utm_adsetid','utm_adid'].forEach(function (k) {
      if (q.get(k)) p.append(k, q.get(k));
    });
    if (window.__EVENTO__.funnel) p.append('funnel', window.__EVENTO__.funnel);
    window.location.href = destino + '?' + p.toString();
  }

  form.addEventListener('submit', function (ev) {
    ev.preventDefault();
    if (enviado) return;

    var nombre = form.fullname.value.trim();
    var email = form.email.value.trim();
    var tel = form.phoneLocal.value.replace(/\D/g, '');
    var prefijo = form.phonePrefix.value;
    // El país lo deja el selector de prefijo en un campo oculto.
    var campoPais = document.getElementById('countryName');
    var pais = campoPais ? campoPais.value : '';

    if (!nombre) { decir('Escribe tu nombre.', 'error'); form.fullname.focus(); return; }
    if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) { decir('Revisa el correo, no parece válido.', 'error'); form.email.focus(); return; }
    if (!tel) { decir('Escribe tu número de WhatsApp.', 'error'); form.phoneLocal.focus(); return; }
    if (privacidad && !privacidad.checked) { decir('Acepta la política de privacidad para continuar.', 'error'); privacidad.focus(); return; }

    var cuerpo = Object.assign(atribucion(), {
      name: nombre,
      email: email,
      lead_phone: tel,
      lead_phone_prefix: prefijo,
      lead_country: pais,
      funnel: window.__EVENTO__.funnel,
      url: location.href,
      user_agent: navigator.userAgent,
      conditions: 'Acepta las políticas: ' + new Date().toISOString()
    });

    enviado = true;
    if (boton) boton.disabled = true;
    decir('Enviando…');

    fetch('/f/api/lead/', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(cuerpo)
    })
      .then(function (r) { if (!r.ok) throw new Error(r.status); return r.json(); })
      .then(function () {
        decir('¡Listo! Te llevamos al último paso…', 'ok');
        form.reset();
        irAGracias();
      })
      .catch(function () {
        enviado = false;
        if (boton) boton.disabled = false;
        decir('No hemos podido registrarte. Inténtalo de nuevo en un momento.', 'error');
      });
  });
})();
