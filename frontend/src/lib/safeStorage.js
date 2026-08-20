/**
 * Acceso a localStorage que nunca tumba el render.
 *
 * Cuando el navegador deniega el almacenamiento (cookies de terceros
 * bloqueadas, modo restringido, navegadores embebidos de TikTok/Instagram…) no
 * es que `setItem` falle: es que **leer la propiedad `window.localStorage` ya
 * lanza** SecurityError. Por eso los guards del tipo
 *
 *     typeof localStorage !== 'undefined' && localStorage.getItem(k)
 *
 * no sirven de nada — el `typeof` evalúa el getter y revienta igual. La única
 * protección es envolver el acceso ENTERO en try/catch, que es lo que hace esto.
 *
 * Reproducido en Chrome real: sin esto, la landing entera se quedaba en blanco
 * (FUNNELS-4D, ~47 visitas al día de tráfico de pago).
 */

/** Devuelve el valor guardado, o null si no existe o el navegador no deja leer. */
export function leer(clave) {
  try {
    return localStorage.getItem(clave)
  } catch {
    return null
  }
}

/** Guarda el valor. Devuelve false si el navegador no deja escribir. */
export function guardar(clave, valor) {
  try {
    localStorage.setItem(clave, valor)
    return true
  } catch {
    return false
  }
}
