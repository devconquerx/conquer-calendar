/* Resolución del origen del backend del calendario.

   El funnel y el widget de reservas se sirven en calendar.conquerx.com, pero el
   bundle puede ejecutarse embebido en un dominio de marca (conquerlegal.com,
   conquerblocks.com, …) donde esas rutas de API/slots NO existen. Para que los
   requests vayan siempre al backend correcto sin tener que mapear cada dominio:

   - Si corremos en el MISMO origen que el calendario (o no hay origen
     configurado, p.ej. en dev localhost) → se devuelve la ruta RELATIVA, igual
     que siempre (no rompe nada de lo que ya funciona).
   - Si corremos en OTRO origen (embebido en un dominio de marca) → se antepone
     el origen canónico del calendario y el request va directo a él.

   El origen canónico se resuelve, por orden de prioridad:
   1. window.__CQX_CALENDAR_ORIGIN__  (lo inyecta el backend en sus plantillas;
      permite override en runtime sin recompilar).
   2. import.meta.env.VITE_CALENDAR_ORIGIN  (horneado en el bundle en build de
      producción vía frontend/.env.production; es el que cubre el caso embebido
      en Webflow, donde no hay plantilla Django que inyecte nada).
   3. '' → mismo origen (dev). */

const RAW =
  (typeof window !== 'undefined' && window.__CQX_CALENDAR_ORIGIN__) ||
  (import.meta.env && import.meta.env.VITE_CALENDAR_ORIGIN) ||
  ''

// Sin barra final, para concatenar limpio con paths que empiezan en '/'.
export const CALENDAR_ORIGIN = String(RAW).replace(/\/+$/, '')

/**
 * Devuelve la URL a usar para un request del backend del calendario.
 * @param {string} path  Ruta absoluta del backend (debe empezar por '/').
 */
export function apiUrl(path) {
  if (!CALENDAR_ORIGIN) return path
  try {
    if (window.location.origin === CALENDAR_ORIGIN) return path
  } catch (_) {
    // Sin window (SSR/tests): asume relativo.
    return path
  }
  return `${CALENDAR_ORIGIN}${path}`
}
