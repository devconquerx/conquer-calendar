/**
 * Tracking ID generation utilities.
 */

function randomSuffix() {
  return Math.random().toString(36).substring(2, 8)
}

/** New event ID per significant action — format: "{timestamp}_{random6}" */
export function generateEventId() {
  return `${Date.now()}_${randomSuffix()}`
}

/**
 * Event ID del recorrido del funnel. Lee primero el `event_id` de la URL (que
 * la landing propaga a través de video → stepform) y, si no está, genera uno
 * nuevo. NO se persiste en localStorage: una visita nueva (landing sin
 * `event_id` en la URL) obtiene su propio event_id.
 *
 * Esto replica el comportamiento del funnel de Django (SPA Inertia con un único
 * TrackingProvider en la raíz): un mismo event_id cubre todo el recorrido de la
 * visita (Lead del landing + Lead del form + Schedule), por lo que Meta/GA/
 * TikTok deduplican esos eventos. Aquí, al ser páginas separadas, conseguimos
 * el mismo efecto propagando el event_id por la URL.
 */
export function getOrCreateEventId() {
  const urlParams = new URLSearchParams(window.location.search)
  const urlEventId = urlParams.get('event_id')
  if (urlEventId) return urlEventId
  return generateEventId()
}

/**
 * Persistent journey ID across the entire visitor session.
 * Reads from URL param first, then localStorage, then generates new.
 * Format: "jrn_{timestamp}_{random6}" — never expires.
 */
export function getOrCreateJourneyId() {
  const urlParams = new URLSearchParams(window.location.search)
  const urlJourneyId = urlParams.get('journey_id')
  if (urlJourneyId) {
    localStorage.setItem('cqx_journey_id', urlJourneyId)
    return urlJourneyId
  }

  const stored = localStorage.getItem('cqx_journey_id')
  if (stored) return stored

  const newId = `jrn_${Date.now()}_${randomSuffix()}`
  localStorage.setItem('cqx_journey_id', newId)
  return newId
}

/** Schedule-specific event ID — format: "{timestamp}_{random6}" */
export function generateScheduleEventId() {
  return `${Date.now()}_${randomSuffix()}`
}

/**
 * UUID de la Prellamada — clave de upsert en el CRM (campo `uuid`).
 * Se genera nuevo por montaje del formulario y NO se persiste, así que cambia
 * en cada recarga del navegador, igual que el `useState(uuidv4())` de
 * conquerx-funnels-new. Todas las llamadas de un mismo montaje comparten este
 * uuid; una recarga genera uno nuevo (fila nueva en el CRM).
 */
export function generatePrellamadaUuid() {
  if (typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function') {
    return crypto.randomUUID()
  }
  // Fallback UUID v4 para navegadores/entornos sin crypto.randomUUID.
  return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, (c) => {
    const r = (Math.random() * 16) | 0
    const v = c === 'x' ? r : (r & 0x3) | 0x8
    return v.toString(16)
  })
}
