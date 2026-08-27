{% comment %}
  Banner de consentimiento en un solo fichero, para las páginas que NO sirve
  Django.

  El dominio de cada marca está partido en dos: los embudos y las páginas de
  evento las sirve esta aplicación, y el resto Webflow. El banner vivía solo en
  las plantillas de Django, así que en la mitad de Webflow seguía saliendo el de
  Cookiebot. Esto lo empaqueta para que Webflow lo cargue con una línea en su
  código global:

      <script src="https://www.conquerblocks.com/f/conquerx-cookies.js"></script>

  Va ANTES del snippet de GTM, y sin `async` ni `defer`: los valores por defecto
  de Consent Mode tienen que estar puestos antes de que exista cualquier
  etiqueta de Google, o esa primera medición se escapa sin permiso. Todo lo que
  toca el DOM sí espera a que haya DOM.

  Se sirve desde el dominio de la marca (no desde calendar.conquerx.com) por una
  razón concreta: la ruta pasa por el Worker de Cloudflare, que es quien añade
  `X-Visitor-Country`. Sin esa cabecera no sabríamos de qué país entra el
  visitante y habría que asumir Europa para todo el mundo — banner bloqueante en
  LATAM y en Estados Unidos, donde la ley no lo pide.

  Los estilos y el marcado salen de los mismos includes que usan las páginas de
  Django, así que el banner es literalmente el mismo en los dos lados. Y la
  cookie `cqx_consent` es del dominio, no de la aplicación: quien decide en una
  página de Webflow llega al embudo con su decisión ya tomada, y al revés.
{% endcomment %}
(function (w, d) {
  'use strict';

  // Si la página ya trae el banner (una de Django), no hay nada que hacer: sus
  // plantillas lo incluyen entero y montarlo dos veces daría dos diálogos.
  if (w.__CONSENTIMIENTO__) return;

  w.dataLayer = w.dataLayer || [];
  function gtag() { w.dataLayer.push(arguments); }

  var explicito = {{ consentimiento.explicito|yesno:"true,false" }};
  var forzar = {{ consentimiento.forzado|yesno:"true,false" }};   // ?debug=1
  var guardado = d.cookie.indexOf('cqx_consent=') !== -1 && !forzar;

  // Misma regla que en las páginas de Django: donde hace falta permiso previo
  // (RGPD) se deniega hasta que el visitante pulse; donde el consentimiento es
  // implícito se concede desde el principio y el aviso solo informa.
  var inicial = (explicito && !guardado) ? 'denied' : 'granted';
  gtag('consent', 'default', {
    ad_storage: inicial,
    ad_user_data: inicial,
    ad_personalization: inicial,
    analytics_storage: inicial,
    personalization_storage: inicial,
    functionality_storage: 'granted',
    security_storage: 'granted',
    wait_for_update: 500,
  });

  w.__CONSENTIMIENTO__ = {
    aplica: {{ consentimiento.aplica|yesno:"true,false" }},
    explicito: explicito,
    forzar: forzar,
    version: {{ consentimiento.version }},
    origen: 'bundle',
  };

{% if bloquear_cookiebot %}
  /* Cookiebot lo inyecta el contenedor de GTM, no esta página. Si se le deja
     cargar salen DOS banners. Se le impide interceptando la asignación del
     `src`, igual que en las plantillas de Django.

     Es un apaño y se nota: lo limpio es darle al tag de Cookiebot una excepción
     de trigger en cada contenedor, y entonces este bloque sobra. Se puede
     desactivar añadiendo `?cookiebot=1` a la URL del script, para comprobar
     cómo queda la página con el suyo. */
  var crear = d.createElement.bind(d);
  d.createElement = function (etiqueta) {
    var el = crear.apply(null, arguments);
    if (String(etiqueta).toLowerCase() !== 'script') return el;
    try {
      var desc = Object.getOwnPropertyDescriptor(HTMLScriptElement.prototype, 'src');
      Object.defineProperty(el, 'src', {
        configurable: true,
        get: function () { return desc.get.call(el); },
        set: function (valor) {
          if (/(^|\.)cookiebot\.(com|eu)\//i.test(String(valor))) return;
          desc.set.call(el, valor);
        },
      });
    } catch (e) { /* si el navegador no deja, que cargue: peor es quedarse sin consentimiento */ }
    return el;
  };
{% endif %}

  // ------------------------------------------------------------- interfaz
  // A diferencia de las páginas de Django, aquí el script corre en el <head> y
  // todavía no hay <body> donde meter nada. Consent Mode ya está resuelto
  // arriba; el diálogo se monta cuando haya DOM.

  function montar() {
    if (d.getElementById('cqx-consent')) return;

    var estilos = d.createElement('style');
    estilos.textContent = "{{ css|escapejs }}";
    d.head.appendChild(estilos);

    var contenedor = d.createElement('div');
    contenedor.innerHTML = "{{ markup|escapejs }}";
    while (contenedor.firstChild) d.body.appendChild(contenedor.firstChild);

    comportamiento();
  }

  if (d.readyState === 'loading') {
    d.addEventListener('DOMContentLoaded', montar);
  } else {
    montar();
  }

  // El comportamiento va incrustado, no en un <script src> aparte: así no hay
  // una segunda petición que pueda llegar tarde o fallar y dejar el diálogo
  // pintado pero muerto, con los botones sin hacer nada.
  function comportamiento() {
{{ conducta|safe }}
  }
})(window, document);
