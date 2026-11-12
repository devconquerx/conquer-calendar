/* ═══ Sistema de diseño "Conquer Lab" ═══
   Es la librería compartida de Figma (Conquer Lab) que define los mismos
   componentes para todas las marcas —Superficie, Tarjeta, Tag, Button, Logo,
   Conquies— y los tiñe con las variables `Brand/<marca>` (start / middle / end
   / tint). Aquí pasa igual: la estructura de la página y las medidas son
   comunes (LabLanding + la rama `lab` de LandingForm) y cada tema de marca solo
   aporta su bloque `lab` con colores y assets.

   Mientras se valida en producción, el diseño solo se enciende con el query
   param `?diseno=lab`; sin él todo sigue en el sistema de siempre. Una marca
   sin bloque `lab` ignora el parámetro. */

// Query param que activa el rediseño. Es el único punto de entrada: sin él la
// landing de producción no cambia.
export const LAB_PARAM = 'diseno'
export const LAB_VALUE = 'lab'

// `search` es el query string del arranque (llega también en SSR), así que el
// HTML del servidor y el del cliente salen iguales.
export function isLabRequested(search) {
  if (!search) return false
  try {
    const params = new URLSearchParams(search.startsWith('?') ? search.slice(1) : search)
    return params.get(LAB_PARAM) === LAB_VALUE
  } catch {
    return false
  }
}

// Neutros de la librería (Core/Color): idénticos en todas las marcas.
export const LAB_NEUTRAL = {
  ink: '#111111',
  white: '#FFFFFF',
  n300: '#E0E0E0',
  n500: '#9A9A9A',
  // Borde de las tarjetas ("▸ Fondo" de Tarjeta).
  line: 'rgba(10,10,10,0.12)',
}

// Variables CSS de una marca. Los componentes del Lab solo leen estas, así que
// una marca nueva no toca ningún componente: le basta su bloque `lab`.
export function labCssVars(lab) {
  const c = lab.colors
  return {
    '--lab-start': c.start,
    '--lab-middle': c.middle,
    '--lab-end': c.end,
    '--lab-tint': c.tint,
    '--lab-ink': LAB_NEUTRAL.ink,
    '--lab-line': LAB_NEUTRAL.line,
    '--lab-n300': LAB_NEUTRAL.n300,
    '--lab-n500': LAB_NEUTRAL.n500,
    // CTA (Button · Fill=Gradient) y acentos caligráficos del texto.
    '--lab-gradient': `linear-gradient(90deg, ${c.start} 0%, ${c.middle} 50%, ${c.end} 100%)`,
    // En Figma el degradado del texto va a ~2°: claro abajo, oscuro arriba.
    '--lab-text-gradient': `linear-gradient(2.4deg, ${c.start} 0%, ${c.middle} 50%, ${c.end} 100%)`,
    '--lab-script': lab.scriptFont || "'Story Script', cursive",
  }
}

/* Fondo de la banda de color (Superficie · Base=Gradiente): un sólido de marca
   con cinco halos radiales encima. Las posiciones salen de la matriz de cada
   gradiente en Figma (frame de 1440×545) pasadas a %, para que escalen con la
   banda en cualquier ancho. */
export function labBandBackground(glows, base) {
  const layers = glows.map(({ rgb, at, size }) =>
    `radial-gradient(ellipse ${size} at ${at}, rgba(${rgb},0.96) 0%, rgba(${rgb},0.42) 62%, rgba(${rgb},0) 100%)`
  )
  return [...layers, `linear-gradient(${base}, ${base})`].join(', ')
}

// Máscara de la textura de líneas sobre la banda (Máscara Radial de Figma):
// invisible en el centro hasta el 30 % y plena en los bordes.
export const LAB_TEXTURE_MASK =
  'radial-gradient(ellipse 70.7% 70.7% at 50% 50%, transparent 30%, #000 100%)'
