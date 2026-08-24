/*
 * Horas siempre en 24h, sin depender del navegador de cada persona.
 *
 * El <input type="time"> nativo se pinta en AM/PM o en 24h según el idioma de
 * Chrome/Firefox, así que dos usuarios veían la misma disponibilidad con
 * formatos distintos. Aquí usamos inputs de texto con máscara y normalización
 * propias: todo el mundo ve HH:MM y se envía HH:MM, que es justo lo que ya
 * espera el backend (availability.views._parse_time).
 *
 * Al escribir acepta 9, 930, 9:3, 9.30, 9h30 o 5pm; al salir del campo lo deja
 * en HH:MM. Las flechas arriba/abajo mueven de 15 en 15 minutos (60 con Shift).
 *
 * Marca los campos con la clase js-hora24. Los <input type="time"> que aparezcan
 * (los haya escrito una plantilla o los cree otro script) se convierten solos.
 */
(function () {
  'use strict';

  var SEL = '.js-hora24';
  var SEL_TIME = 'input[type="time"]';
  var PATRON = '([01][0-9]|2[0-3]):[0-5][0-9]';
  var TITULO = 'Escribe la hora en formato 24h, por ejemplo 09:30';

  function dosDigitos(n) { return (n < 10 ? '0' : '') + n; }

  function formatear(minutos) {
    return dosDigitos(Math.floor(minutos / 60)) + ':' + dosDigitos(minutos % 60);
  }

  /* Minutos desde medianoche, o null si no hay forma de entender el texto. */
  function parsear(texto) {
    if (texto === null || texto === undefined) return null;
    var bruto = String(texto).trim().toLowerCase();
    if (!bruto) return null;

    var pm = /p\.?\s*m/.test(bruto);
    var am = /a\.?\s*m/.test(bruto);

    // Cualquier separador (":", ".", ",", "h", espacio) separa horas de minutos.
    var limpio = bruto.replace(/[^0-9:.,h\s]/g, '').replace(/[:.,h\s]+/g, ':');
    var horas, minutos;

    if (limpio.indexOf(':') !== -1) {
      var partes = limpio.split(':');
      horas = parseInt(partes[0], 10);
      var min = (partes[1] || '').replace(/\D/g, '');
      // Un dígito suelto son decenas, igual que en el input nativo: 9:3 → 09:30.
      if (!min) minutos = 0;
      else if (min.length === 1) minutos = parseInt(min, 10) * 10;
      else minutos = parseInt(min.slice(0, 2), 10);
    } else {
      var d = limpio.replace(/\D/g, '');
      if (!d) return null;
      if (d.length <= 2) { horas = parseInt(d, 10); minutos = 0; }
      else if (d.length === 3) { horas = parseInt(d.slice(0, 1), 10); minutos = parseInt(d.slice(1), 10); }
      else { horas = parseInt(d.slice(0, 2), 10); minutos = parseInt(d.slice(2, 4), 10); }
    }

    if (isNaN(horas) || isNaN(minutos)) return null;
    if (pm && horas < 12) horas += 12;
    if (am && horas === 12) horas = 0;
    if (horas > 23 || minutos > 59) return null;
    return horas * 60 + minutos;
  }

  function normalizar(input) {
    if (!input || input.readOnly || input.disabled) return;
    var minutos = parsear(input.value);
    if (minutos === null) {
      // Vacío se queda vacío (que salte el required); lo ilegible vuelve atrás.
      input.value = String(input.value).trim() ? (input.dataset.hora24Ultima || '') : '';
    } else {
      input.value = formatear(minutos);
    }
    if (input.value) input.dataset.hora24Ultima = input.value;
  }

  /* Mete los dos puntos mientras se teclea: 173 → 17:3, 930 → 9:30. */
  function alEscribir(input) {
    var v = input.value;
    if (!/^[0-9]+$/.test(v) || v.length < 3) return;
    var cabeza = parseInt(v.slice(0, 2), 10) <= 23 ? 2 : 1;
    input.value = v.slice(0, cabeza) + ':' + v.slice(cabeza, cabeza + 2);
  }

  function alPulsar(e, input) {
    if (e.key !== 'ArrowUp' && e.key !== 'ArrowDown') return;
    if (input.readOnly || input.disabled) return;
    e.preventDefault();

    var paso = e.shiftKey ? 60 : 15;
    var actual = parsear(input.value);
    if (actual === null) {
      actual = 9 * 60;
    } else if (e.key === 'ArrowUp') {
      actual = Math.floor(actual / paso) * paso + paso;
    } else {
      actual = Math.ceil(actual / paso) * paso - paso;
    }

    input.value = formatear(((actual % 1440) + 1440) % 1440);
    input.dataset.hora24Ultima = input.value;
    input.dispatchEvent(new Event('input', { bubbles: true }));
    input.dispatchEvent(new Event('change', { bubbles: true }));
  }

  function preparar(input) {
    if (input.dataset.hora24 === '1') return;
    input.dataset.hora24 = '1';

    if (input.type === 'time') {
      var valor = input.value;
      input.type = 'text';
      input.value = valor;
    }

    input.classList.add('js-hora24');
    input.setAttribute('inputmode', 'numeric');
    input.setAttribute('autocomplete', 'off');
    if (!input.getAttribute('placeholder')) input.setAttribute('placeholder', 'HH:MM');
    if (!input.getAttribute('pattern')) input.setAttribute('pattern', PATRON);
    if (!input.getAttribute('title')) input.setAttribute('title', TITULO);

    normalizar(input);
  }

  function aplicar(raiz) {
    var nodos = (raiz || document).querySelectorAll(SEL_TIME + ', ' + SEL);
    Array.prototype.forEach.call(nodos, preparar);
  }

  function esHora(el) {
    return el && el.matches && el.matches(SEL);
  }

  // Todo en fase de captura: así el valor ya está normalizado cuando el change
  // llega a los listeners que cada página tiene puestos sobre el propio input.
  document.addEventListener('input', function (e) {
    if (esHora(e.target)) alEscribir(e.target);
  }, true);

  document.addEventListener('change', function (e) {
    if (esHora(e.target)) normalizar(e.target);
  }, true);

  document.addEventListener('blur', function (e) {
    if (esHora(e.target)) normalizar(e.target);
  }, true);

  document.addEventListener('keydown', function (e) {
    if (esHora(e.target)) alPulsar(e, e.target);
  }, true);

  document.addEventListener('submit', function (e) {
    if (e.target && e.target.querySelectorAll) {
      Array.prototype.forEach.call(e.target.querySelectorAll(SEL), normalizar);
    }
  }, true);

  function iniciar() {
    aplicar(document);
    // Los formularios de disponibilidad crean filas de horas al vuelo.
    new MutationObserver(function (mutaciones) {
      mutaciones.forEach(function (m) {
        Array.prototype.forEach.call(m.addedNodes, function (nodo) {
          if (nodo.nodeType !== 1) return;
          if (nodo.matches && nodo.matches(SEL_TIME + ', ' + SEL)) preparar(nodo);
          if (nodo.querySelectorAll) aplicar(nodo);
        });
      });
    }).observe(document.documentElement, { childList: true, subtree: true });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', iniciar);
  } else {
    iniciar();
  }

  window.Hora24 = { aplicar: aplicar, parsear: parsear, formatear: formatear };
})();
