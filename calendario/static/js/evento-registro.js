/* Registro de las pantallas de evento (lanzamiento).
 *
 * Crea el Lead en el calendario, que a su vez lo empuja al ingest del CRM por
 * Celery. Es el único destino, igual que en el escenario viejo de Make: los
 * leads de lanzamiento no pasan por Supabase, CAPI, Respond.io ni NeverBounce.
 *
 * Lo comparten las plantillas de las tres marcas, que solo se diferencian en el
 * diseño: Blocks y Finance abren el formulario en un popup y Languages lo lleva
 * inline. Ninguna pide marcar una casilla de consentimiento; el aviso legal va
 * como texto, y el consentimiento se registra igual en `conditions`.
 */
(function () {
  var form = document.getElementById('formEvento');
  if (!form) return;

  var aviso = document.getElementById('aviso');
  var boton = form.querySelector('button[type=submit]');
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

  /* Al registrarse se pasa a la pantalla de "gracias" —donde está el último
     paso de verdad, entrar al grupo de WhatsApp— SIN recargar: el bloque ya
     viene en la página, oculto, y aquí solo se intercambia. La URL se cambia
     con pushState para que sea la de gracias, que además existe como página
     propia y responde si alguien recarga o la comparte.

     Como no hay carga de página, el contenedor de GTM no dispara su page_view,
     que es la señal con la que hasta ahora se contaba este paso. Se sustituye
     por `virtual_page_view`, el mismo evento que ya usa el funnel en sus
     cambios de etapa (frontend/src/lib/pixelEvents.js), con los mismos campos
     `page_location` y `page_path`, de modo que el trigger del contenedor sirve
     para los dos sitios. Se empuja DESPUÉS del pushState, para que la URL que
     lea el trigger sea la de gracias y no la del evento. */
  function alDataLayer(datos) {
    window.dataLayer = window.dataLayer || [];
    window.dataLayer.push(datos);
  }

  // Título de la pantalla del evento, para devolverlo si el visitante vuelve
  // atrás; si no, se quedaría el de la de gracias con el formulario delante.
  var tituloEvento = null;

  function irAGracias() {
    var destino = window.__EVENTO__ && window.__EVENTO__.gracias;
    var caja = document.getElementById('gracias-evento');
    var contenido = document.getElementById('evento-contenido');
    // Sin el bloque embebido —o sin soporte de pushState— se navega y ya está:
    // más vale una recarga que dejar al registrado sin su último paso.
    if (!caja || !contenido || !window.history || !history.pushState) {
      if (destino) window.location.href = destino + separador(destino) + params();
      return;
    }
    var url = destino ? destino + separador(destino) + params() : location.href;
    history.pushState({ gracias: true }, '', url);
    contenido.hidden = true;
    caja.hidden = false;
    window.scrollTo(0, 0);
    if (window.__EVENTO__.titulo_gracias) {
      tituloEvento = document.title;
      document.title = window.__EVENTO__.titulo_gracias;
    }
    alDataLayer({
      event: 'virtual_page_view',
      page_location: window.location.href,
      page_path: window.location.pathname,
    });
    if (window.iniciarSaltoWhatsApp) window.iniciarSaltoWhatsApp();
  }

  // Volver atrás devuelve al formulario en vez de dejar la pantalla de gracias
  // con la URL del evento en la barra.
  window.addEventListener('popstate', function () {
    var caja = document.getElementById('gracias-evento');
    var contenido = document.getElementById('evento-contenido');
    if (!caja || !contenido || caja.hidden) return;
    caja.hidden = true;
    contenido.hidden = false;
    if (tituloEvento) document.title = tituloEvento;
    window.scrollTo(0, 0);
  });

  function separador(destino) {
    // El destino ya puede traer query propia (la escuela, fuera de los dominios
    // de marca), así que el separador depende de eso.
    return destino.indexOf('?') === -1 ? '?' : '&';
  }

  /* Se replican los mismos parámetros que arrastra el original MENOS el nombre
     y el correo, que también viajaban en la URL: esa página no los lee, y los
     datos personales en una query string acaban en los logs del servidor, en
     el historial del navegador y en la cabecera Referer de cada recurso que
     cargue la página de destino. */
  function params() {
    var q = new URLSearchParams(location.search);
    var p = new URLSearchParams({ v: '20250218' });
    ['utm_source','utm_medium','utm_campaign','utm_term','utm_content',
     'utm_idcampaign','utm_adsetid','utm_adid'].forEach(function (k) {
      if (q.get(k)) p.append(k, q.get(k));
    });
    if (window.__EVENTO__.funnel) p.append('funnel', window.__EVENTO__.funnel);
    return p.toString();
  }

  form.addEventListener('submit', function (ev) {
    ev.preventDefault();
    if (enviado) return;

    var nombre = form.fullname.value.trim();
    var email = form.email.value.trim();
    // El teléfono es opcional: no todas las pantallas lo piden —la Trading Week
    // solo recoge nombre y correo—, así que si no está el campo no se valida ni
    // se manda, en vez de reventar al leerlo.
    var campoTel = form.phoneLocal || null;
    var tel = campoTel ? campoTel.value.replace(/\D/g, '') : '';
    var prefijo = form.phonePrefix ? form.phonePrefix.value : '';
    // El país lo deja el selector de prefijo en un campo oculto.
    var campoPais = document.getElementById('countryName');
    var pais = campoPais ? campoPais.value : '';

    if (!nombre) { decir('Escribe tu nombre.', 'error'); form.fullname.focus(); return; }
    if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) { decir('Revisa el correo, no parece válido.', 'error'); form.email.focus(); return; }
    if (campoTel && !tel) { decir('Escribe tu número de WhatsApp.', 'error'); campoTel.focus(); return; }

    var cuerpo = Object.assign(atribucion(), {
      name: nombre,
      email: email,
      funnel: window.__EVENTO__.funnel,
      url: location.href,
      user_agent: navigator.userAgent,
      conditions: 'Acepta las políticas: ' + new Date().toISOString()
    });
    if (campoTel) {
      cuerpo.lead_phone = tel;
      cuerpo.lead_phone_prefix = prefijo;
      cuerpo.lead_country = pais;
    }

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
