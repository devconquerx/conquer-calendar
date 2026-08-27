/**
 * Tracking ID generation utilities.
 */
import { guardar, leer } from './safeStorage'

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
  // En SSR no hay URL ni se renderiza este valor al DOM; el cliente recalcula
  // el real al hidratar. Devolvemos uno desechable para no romper el render.
  if (typeof window === 'undefined') return generateEventId()
  const urlParams = new URLSearchParams(window.location.search)
  const urlEventId = urlParams.get('event_id')
  if (urlEventId) return urlEventId
  return generateEventId()
}

/**
 * Persistent journey ID across the entire visitor session.
 * Reads from URL param first, then localStorage, then generates new.
 * Format: "jrn_{timestamp}_{random6}" — never expires.
 *
 * Si el navegador tiene el almacenamiento bloqueado no se persiste y cada carga
 * genera uno nuevo: se pierde reconocer a quien vuelve otro día, pero el
 * recorrido de ESTA visita se mantiene porque el journey_id viaja de etapa a
 * etapa por la URL. Antes esto lanzaba y dejaba la landing en blanco.
 */
export function getOrCreateJourneyId() {
  // En SSR (sin window/localStorage) devolvemos uno desechable; el cliente lo
  // recalcula/persiste al hidratar. No se renderiza al DOM.
  if (typeof window === 'undefined') return `jrn_${Date.now()}_${randomSuffix()}`
  const urlParams = new URLSearchParams(window.location.search)
  const urlJourneyId = urlParams.get('journey_id')
  if (urlJourneyId) {
    guardar('cqx_journey_id', urlJourneyId)
    return urlJourneyId
  }

  const stored = leer('cqx_journey_id')
  if (stored) return stored

  const newId = `jrn_${Date.now()}_${randomSuffix()}`
  guardar('cqx_journey_id', newId)
  return newId
}

/** Schedule-specific event ID — format: "{timestamp}_{random6}" */
export function generateScheduleEventId() {
  return `${Date.now()}_${randomSuffix()}`
}

/** Cuánto vive el uuid de la Prellamada guardado en el navegador.
 *
 * 24h cubre de sobra a quien vuelve al embudo el mismo día (los reingresos
 * medidos en producción van de 22 segundos a 34 minutos) sin llegar a fundir
 * dos visitas lejanas: alguien que vuelve semanas después por otra campaña
 * merece una Prellamada nueva, no pisar las respuestas y la variante A/B de la
 * anterior. También acota el estropicio en un ordenador compartido. */
export const UUID_PRELLAMADA_TTL_MS = 24 * 60 * 60 * 1000

const CLAVE_UUID = 'cqx_prellamada_uuid'

/**
 * UUID de la Prellamada — clave de upsert, tanto de nuestra tabla como del CRM.
 *
 * Se persiste con caducidad. Antes se generaba por montaje y no se guardaba
 * (herencia de `useState(uuidv4())` de conquerx-funnels-new), así que volver a
 * entrar al embudo creaba una Prellamada nueva. Cuando esa persona pedía la
 * misma hora que ya tenía reservada, la reserva —que es OneToOne— ya tenía
 * dueña y el POST reventaba: el visitante veía un error después de haber
 * reservado bien (FUNNELS-96, 112 veces en dos días).
 *
 * Reutilizarlo también deja de partir en dos el registro del CRM cuando alguien
 * vuelve sobre sus pasos.
 *
 * Si el almacenamiento está bloqueado, `leer`/`guardar` devuelven vacío sin
 * lanzar y se cae al comportamiento de antes: uuid nuevo por montaje. Peor,
 * pero nunca roto — por eso el arreglo de servidor sigue haciendo falta.
 */
export function getOrCreatePrellamadaUuid() {
  if (typeof window === 'undefined') return generatePrellamadaUuid()

  const guardado = leer(CLAVE_UUID)
  if (guardado) {
    try {
      const { uuid, expira } = JSON.parse(guardado)
      if (uuid && typeof expira === 'number' && Date.now() < expira) return uuid
    } catch (_) {
      // Valor corrupto o de un formato anterior: se descarta y se genera otro.
    }
  }

  const uuid = generatePrellamadaUuid()
  guardar(CLAVE_UUID, JSON.stringify({ uuid, expira: Date.now() + UUID_PRELLAMADA_TTL_MS }))
  return uuid
}

/** UUID v4 suelto, sin persistir. */
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
