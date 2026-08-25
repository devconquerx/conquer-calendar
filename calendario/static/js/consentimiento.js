/* Consentimiento de cookies propio, en sustitución de Cookiebot.
 *
 * Los valores por defecto de Consent Mode NO se ponen aquí: van en un script
 * síncrono en el <head> (_includes/_consentimiento.html), porque tienen que
 * estar antes de que cargue cualquier etiqueta de Google. Este fichero solo se
 * ocupa de la interfaz y de comunicar la decisión.
 *
 * Al decidir se hacen tres cosas, en este orden:
 *   1. `gtag('consent','update', …)` con las cuatro categorías traducidas a las
 *      claves de Consent Mode v2.
 *   2. Un `cookie_consent_<categoría>` al dataLayer por cada categoría
 *      aceptada, y un `cookie_consent_update` al final. Son exactamente los
 *      eventos que empuja la plantilla de Cookiebot en GTM, así que los
 *      triggers que ya existen en los contenedores siguen funcionando sin
 *      tocarlos.
 *   3. Se guarda la decisión en una cookie propia con su fecha y su versión.
 */
(function (w, d) {
  var COOKIE = 'cqx_consent';
  var cfg = w.__CONSENTIMIENTO__ || {};
  var caja = d.getElementById('cqx-consent');
  if (!caja) return;

  function gtag() { w.dataLayer = w.dataLayer || []; w.dataLayer.push(arguments); }

  // ---------------------------------------------------------------- guardado

  function leer() {
    var m = d.cookie.match('(^|;)\\s*' + COOKIE + '\\s*=\\s*([^;]+)');
    if (!m) return null;
    try {
      var v = JSON.parse(decodeURIComponent(m[2]));
      // Si las categorías o los textos han cambiado, lo que se aceptó ya no es
      // lo que hay, así que se vuelve a preguntar.
      return v && v.v === cfg.version ? v : null;
    } catch (e) { return null; }
  }

  function guardar(c) {
    var valor = encodeURIComponent(JSON.stringify({
      v: cfg.version, p: c.preferences ? 1 : 0, s: c.statistics ? 1 : 0,
      m: c.marketing ? 1 : 0, t: new Date().toISOString(),
    }));
    // Doce meses, que es lo que recomienda la AEPD y lo que hacía Cookiebot.
    var caduca = new Date(Date.now() + 365 * 24 * 60 * 60 * 1000).toUTCString();
    var seguro = location.protocol === 'https:' ? ';Secure' : '';
    d.cookie = COOKIE + '=' + valor + ';path=/;expires=' + caduca + ';SameSite=Lax' + seguro;
  }

  // ---------------------------------------------------------------- difusión

  function comunicar(c) {
    var conceder = function (b) { return b ? 'granted' : 'denied'; };
    gtag('consent', 'update', {
      ad_storage: conceder(c.marketing),
      ad_user_data: conceder(c.marketing),
      ad_personalization: conceder(c.marketing),
      analytics_storage: conceder(c.statistics),
      personalization_storage: conceder(c.preferences),
      functionality_storage: 'granted',
      security_storage: 'granted',
    });
    w.dataLayer = w.dataLayer || [];
    ['preferences', 'statistics', 'marketing'].forEach(function (k) {
      if (c[k]) w.dataLayer.push({ event: 'cookie_consent_' + k });
    });
    w.dataLayer.push({ event: 'cookie_consent_update' });
  }

  // -------------------------------------------------------------- interfaz

  var panel = d.getElementById('cqx-consent-panel');
  var casillas = {
    preferences: d.getElementById('cqx-c-preferences'),
    statistics: d.getElementById('cqx-c-statistics'),
    marketing: d.getElementById('cqx-c-marketing'),
  };
  var ultimoFoco = null;
  var icono = d.getElementById('cqx-consent-icono');

  /* El icono queda flotando en cuanto se cierra el modal, como el de Cookiebot.
     No es decorativo: es la única forma de volver a abrirlo y de retirar el
     permiso, y retirarlo tiene que ser tan fácil como darlo. Solo aparece donde
     se ha preguntado; donde no se pregunta no hay nada que reconsiderar. */
  function pintarIcono() {
    if (!icono) return;
    icono.hidden = !(cfg.aplica && caja.hidden);
  }

  function mostrar() {
    ultimoFoco = d.activeElement;
    caja.hidden = false;
    pintarIcono();
    var primero = caja.querySelector('button');
    if (primero) primero.focus();
  }

  function ocultar() {
    caja.hidden = true;
    pintarIcono();
    // Al cerrar, el foco va al icono: es donde acaba de quedar la acción, y
    // devolverlo al fondo de la página dejaría a quien navega con teclado sin
    // saber dónde está.
    if (icono && !icono.hidden) icono.focus();
    else if (ultimoFoco && ultimoFoco.focus) ultimoFoco.focus();
  }

  function decidir(c) {
    guardar(c);
    comunicar(c);
    ocultar();
  }

  function todas(valor) {
    return { preferences: valor, statistics: valor, marketing: valor };
  }

  function delPanel() {
    return {
      preferences: !!(casillas.preferences && casillas.preferences.checked),
      statistics: !!(casillas.statistics && casillas.statistics.checked),
      marketing: !!(casillas.marketing && casillas.marketing.checked),
    };
  }

  function pulsar(id, fn) {
    var b = d.getElementById(id);
    if (b) b.addEventListener('click', fn);
  }

  pulsar('cqx-aceptar', function () { decidir(todas(true)); });
  pulsar('cqx-rechazar', function () { decidir(todas(false)); });
  pulsar('cqx-personalizar', function () {
    var abierto = panel.hidden === false;
    panel.hidden = abierto;
    d.getElementById('cqx-personalizar').setAttribute('aria-expanded', String(!abierto));
  });
  pulsar('cqx-guardar', function () { decidir(delPanel()); });
  pulsar('cqx-consent-icono', function () { w.cqxConsent.abrir(); });

  // Sin botón de cerrar: cerrarlo sin elegir equivaldría a un consentimiento
  // que nadie ha dado. Escape tampoco lo cierra, por lo mismo.

  // Para el enlace de "configurar cookies" del pie: vuelve a abrirlo con lo que
  // haya guardado ya marcado, que es lo que exige poder retirar el permiso.
  w.cqxConsent = {
    abrir: function () {
      var y = leer();
      Object.keys(casillas).forEach(function (k) {
        if (casillas[k]) casillas[k].checked = y ? !!y[k[0]] : false;
      });
      panel.hidden = false;
      d.getElementById('cqx-personalizar').setAttribute('aria-expanded', 'true');
      mostrar();
    },
    estado: leer,
  };

  // ---------------------------------------------------------------- arranque

  var guardado = cfg.forzar ? null : leer();   // con ?debug=1 se ignora lo guardado
  if (guardado) {
    comunicar({ preferences: !!guardado.p, statistics: !!guardado.s, marketing: !!guardado.m });
    pintarIcono();
    return;
  }
  if (!cfg.aplica) {
    // Fuera de las regiones con normativa de consentimiento previo no se
    // pregunta y se da por implícito, que es lo que hace Cookiebot hoy
    // (`method: "implied"`). No se guarda cookie: no hay decisión que guardar.
    comunicar(todas(true));
    return;
  }
  mostrar();
})(window, document);
