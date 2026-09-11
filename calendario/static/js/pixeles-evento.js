/* Píxeles de las pantallas de evento (lanzamientos), a código y sin GTM.
 *
 * Estas páginas no cargan el contenedor de la marca: su trigger de lead es el
 * mismo que el del funnel y mandaba los registros de lanzamiento a la
 * conversión de venta. Aquí se cargan los tres píxeles y el registro dispara su
 * propio evento, contra acciones creadas solo para esto.
 *
 * Dos reglas que se replican del contenedor y conviene no perder de vista:
 *
 *   Consentimiento. Google va con Consent Mode —se carga siempre y él decide si
 *   puede usar cookies—, pero Meta y TikTok no lo entienden, así que no se
 *   cargan hasta que hay permiso de marketing. En LATAM y Estados Unidos el
 *   permiso es implícito y llega en cuanto arranca consentimiento.js; en la UE
 *   espera al botón. Sin permiso no se manda nada por esos dos.
 *
 *   Carga diferida. Igual que `_sgtm_head.html`: los scripts se inyectan al
 *   primer gesto del visitante o, si no lo hay, en idle. Cargarlos en el <head>
 *   compite con el render y hunde el LCP en móvil, que en estas landings es la
 *   tarjeta del formulario.
 *
 * Expone `window.cqxPixeles.lead(datos)`, que llama evento-registro.js al
 * registrar. `datos.event_id` es el mismo identificador que viaja al CRM, y es
 * lo que deduplica este evento contra el que manda la API de conversiones desde
 * el servidor.
 */
(function (w, d) {
  var CFG = w.__PIXELES__;
  if (!CFG || !CFG.ads) return;

  w.dataLayer = w.dataLayer || [];
  function gtag() { w.dataLayer.push(arguments); }
  w.gtag = w.gtag || gtag;

  // ------------------------------------------------------------- Google

  var googleCargado = false;

  function cargarGoogle() {
    if (googleCargado) return;
    googleCargado = true;
    var s = d.createElement('script');
    s.async = true;
    s.src = 'https://www.googletagmanager.com/gtag/js?id=' + CFG.ads;
    d.head.appendChild(s);
    gtag('js', new Date());
    gtag('config', CFG.ads);
    if (CFG.ga4) gtag('config', CFG.ga4);
  }

  // --------------------------------------------------------------- Meta

  var metaCargado = false;

  function cargarMeta() {
    if (metaCargado || !CFG.meta) return;
    metaCargado = true;
    /* Snippet oficial de Meta: deja `fbq` encolando hasta que llega fbevents. */
    (function (f, b, e, v, n, t, s) {
      if (f.fbq) return; n = f.fbq = function () {
        n.callMethod ? n.callMethod.apply(n, arguments) : n.queue.push(arguments);
      };
      if (!f._fbq) f._fbq = n;
      n.push = n; n.loaded = true; n.version = '2.0'; n.queue = [];
      t = b.createElement(e); t.async = true; t.src = v;
      s = b.getElementsByTagName(e)[0]; s.parentNode.insertBefore(t, s);
    })(w, d, 'script', 'https://connect.facebook.net/en_US/fbevents.js');
    w.fbq('init', CFG.meta);
    w.fbq('track', 'PageView');
  }

  // ------------------------------------------------------------- TikTok

  var tiktokCargado = false;

  function cargarTikTok() {
    if (tiktokCargado || !CFG.tiktok) return;
    tiktokCargado = true;
    /* Snippet oficial de TikTok, recortado a lo que se usa aquí. */
    (function (win, doc, script) {
      win.TiktokAnalyticsObject = script;
      var ttq = win[script] = win[script] || [];
      ttq.methods = ['page', 'track', 'identify', 'instances', 'debug', 'on', 'off',
                     'once', 'ready', 'alias', 'group', 'enableCookie', 'disableCookie'];
      ttq.setAndDefer = function (t, e) {
        t[e] = function () { t.push([e].concat(Array.prototype.slice.call(arguments, 0))); };
      };
      for (var i = 0; i < ttq.methods.length; i++) ttq.setAndDefer(ttq, ttq.methods[i]);
      ttq.instance = function (t) {
        var e = ttq._i[t] || [];
        for (var n = 0; n < ttq.methods.length; n++) ttq.setAndDefer(e, ttq.methods[n]);
        return e;
      };
      ttq.load = function (e, n) {
        var r = 'https://analytics.tiktok.com/i18n/pixel/events.js';
        ttq._i = ttq._i || {}; ttq._i[e] = []; ttq._i[e]._u = r;
        ttq._t = ttq._t || {}; ttq._t[e] = +new Date();
        ttq._o = ttq._o || {}; ttq._o[e] = n || {};
        var o = doc.createElement('script');
        o.type = 'text/javascript'; o.async = true; o.src = r + '?sdkid=' + e + '&lib=' + script;
        var a = doc.getElementsByTagName('script')[0];
        a.parentNode.insertBefore(o, a);
      };
      ttq.load(CFG.tiktok);
      ttq.page();
    })(w, d, 'ttq');
  }

  // ------------------------------------------------- permiso de marketing

  var marketing = false;
  var pendientes = [];

  function conMarketing(fn) {
    if (marketing) { fn(); return; }
    pendientes.push(fn);
  }

  function concederMarketing() {
    if (marketing) return;
    marketing = true;
    cargarMeta();
    cargarTikTok();
    var cola = pendientes;
    pendientes = [];
    cola.forEach(function (fn) { fn(); });
  }

  /* consentimiento.js avisa con `cqx:consent` cada vez que hay decisión: la
     guardada al cargar, la implícita de LATAM/US y la del botón en la UE. */
  w.addEventListener('cqx:consent', function (ev) {
    if (ev.detail && ev.detail.marketing) concederMarketing();
  });
  // Por si la decisión ya estaba tomada antes de que este script se ejecutara.
  var yaDecidido = w.cqxConsent && w.cqxConsent.estado && w.cqxConsent.estado();
  if (yaDecidido && yaDecidido.m) concederMarketing();

  // ----------------------------------------------------- carga diferida

  var eventos = ['pointerdown', 'keydown', 'touchstart', 'scroll', 'mousemove'];
  var arrancado = false;

  function arrancar() {
    if (arrancado) return;
    arrancado = true;
    eventos.forEach(function (e) { w.removeEventListener(e, arrancar); });
    cargarGoogle();
    // Meta y TikTok solo si ya hay permiso; si llega después, los carga
    // `concederMarketing`.
    if (marketing) { cargarMeta(); cargarTikTok(); }
  }

  eventos.forEach(function (e) { w.addEventListener(e, arrancar, { passive: true }); });
  if ('requestIdleCallback' in w) w.requestIdleCallback(arrancar, { timeout: 3500 });
  else w.addEventListener('load', function () { setTimeout(arrancar, 2500); });

  // --------------------------------------------------------------- API

  w.cqxPixeles = {
    /* Registro en la pantalla de evento.
     *
     * datos: { event_id, email, telefono, nombre }
     *
     * Google se dispara siempre (Consent Mode decide si puede cookiear); Meta y
     * TikTok, solo con permiso de marketing — si aún no lo hay, quedan
     * encolados y salen en cuanto se concede, no se pierden.
     */
    lead: function (datos) {
      datos = datos || {};
      arrancar();

      if (CFG.ads_conversion) {
        gtag('event', 'conversion', {
          send_to: CFG.ads_conversion,
          // Con el mismo id que viaja al CRM, un reenvío o una recarga no
          // cuentan dos veces.
          transaction_id: datos.event_id || '',
        });
      }

      conMarketing(function () {
        if (w.fbq && CFG.evento_meta) {
          /* Advanced matching: se reinicia el píxel con los datos del
             registro (Meta los hashea en el navegador) antes de mandar el
             evento, que es lo que hacía el tag del contenedor. */
          if (datos.email || datos.telefono) {
            w.fbq('init', CFG.meta, {
              em: datos.email || undefined,
              ph: datos.telefono || undefined,
            });
          }
          w.fbq('trackCustom', CFG.evento_meta, {
            content_name: 'Registro lanzamiento',
          }, { eventID: datos.event_id || undefined });
        }
        if (w.ttq && CFG.evento_tiktok) {
          if (datos.email || datos.telefono) {
            w.ttq.identify({ email: datos.email || '', phone_number: datos.telefono || '' });
          }
          w.ttq.track(CFG.evento_tiktok, {
            content_name: 'Registro lanzamiento',
          }, { event_id: datos.event_id || undefined });
        }
      });
    },
  };
})(window, document);
