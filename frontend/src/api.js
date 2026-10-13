import * as Sentry from '@sentry/react'
import { apiUrl } from './lib/apiBase'

function getCsrf() {
  return document.getElementById('funnel-root')?.dataset?.csrf || ''
}

// Esperas entre intentos de los envíos fire-and-forget. Un "Failed to fetch" es
// casi siempre la red del móvil o del navegador in-app (TikTok, Instagram) que
// se cae un momento: FUNNELS-D2/7K/7P eran 250 al mes y en cada uno se perdía el
// lead o la prellamada. El servidor tolera el reintento: la prellamada es un
// upsert por journey_id y el lead se deduplica por journey_id + event_id.
const ESPERAS_REINTENTO_MS = [1000, 3000]

function postConReintentos(url, cuerpo, accion) {
  const enviar = (intento) => fetch(url, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'X-CSRFToken': getCsrf(),
    },
    body: cuerpo,
  }).catch((err) => {
    // Solo se reintenta lo que no llegó a tener respuesta (TypeError de red);
    // una respuesta de error del servidor no la arregla repetirla.
    if (err instanceof TypeError && intento < ESPERAS_REINTENTO_MS.length) {
      return new Promise((r) => setTimeout(r, ESPERAS_REINTENTO_MS[intento])).then(() => enviar(intento + 1))
    }
    console.error(`[API] Error en ${accion}:`, err)
    Sentry.captureException(err, { tags: { action: accion }, extra: { intentos: intento + 1 } })
  })
  return enviar(0)
}

export async function fetchConfig(slug) {
  const res = await fetch(apiUrl(`/f/api/${slug}/config/`))
  if (!res.ok) throw new Error('Error al cargar el formulario')
  return res.json()
}

export async function postResolver(slug, respuestas, tracking = {}) {
  const res = await fetch(apiUrl(`/f/api/${slug}/resolver/`), {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'X-CSRFToken': getCsrf(),
    },
    body: JSON.stringify({ respuestas, tracking }),
  })
  if (!res.ok) throw new Error('Error al procesar las respuestas')
  return res.json()
}

/**
 * Pre-schedule intermedio: tras capturar el teléfono, en cada pregunta se
 * crea/actualiza la Prellamada en el backend (upsert por journey_id), igual que
 * el submitForm(..., false) de conquerx-funnels-new. Fire-and-forget: nunca
 * bloquea ni rompe el avance del formulario.
 */
export function sendPreSchedule(slug, respuestas, tracking = {}) {
  return postConReintentos(apiUrl(`/f/api/${slug}/resolver/`),
    JSON.stringify({ respuestas, tracking, final: false }), 'sendPreSchedule')
}

export async function postReservar(slug, data) {
  const res = await fetch(apiUrl(`/f/api/${slug}/reservar/`), {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'X-CSRFToken': getCsrf(),
    },
    body: JSON.stringify(data),
  })
  return res.json()
}

/**
 * Registra el lead (nombre+email+tracking) en el backend apenas se captura el
 * email. Fire-and-forget: dispara las tareas Celery del lado lead. Nunca
 * bloquea ni rompe el flujo del formulario.
 */
export function registerLead(payload) {
  return postConReintentos(apiUrl('/f/api/lead/'), JSON.stringify(payload), 'registerLead')
}

/**
 * Reporta el progreso de visualización del video (cada 10%) al backend, que
 * actualiza el Lead. Fire-and-forget: nunca bloquea ni rompe la reproducción.
 */
export function sendVideoProgressToBackend({ email, percent, school, region }) {
  const url = apiUrl('/f/api/video-progress/')
  const cuerpo = JSON.stringify({ email, percent, school, region })

  // sendBeacon es la API pensada exactamente para esto: el navegador se queda
  // con el envío y lo entrega aunque la página se cierre o el visitante navegue
  // al StepForm en mitad del ping. Además, al mandar el cuerpo como text/plain
  // es una "simple request" y desaparece el preflight CORS (eran ~4.000 OPTIONS
  // al día sólo de este endpoint). El endpoint es csrf_exempt y lee el body con
  // json.loads, así que ni las cabeceras ni el content-type le hacen falta.
  if (typeof navigator !== 'undefined' && typeof navigator.sendBeacon === 'function') {
    try {
      if (navigator.sendBeacon(url, new Blob([cuerpo], { type: 'text/plain;charset=UTF-8' }))) return
    } catch (_) {
      // Si la cola del navegador lo rechaza, cae al fetch de abajo.
    }
  }

  // Reserva para navegadores sin sendBeacon.
  //
  // Un fallo aquí NO se reporta a Sentry: en telemetría fire-and-forget, que un
  // ping no salga (red móvil que se cae, pestaña cerrada, un bloqueador que
  // corta la llamada cross-origin) es una condición esperada, no un error
  // accionable. Se medía en el 0,045% de los pings, y como hay un ping cada 10%
  // y el servidor guarda el máximo, el siguiente cubre al que se perdió.
  fetch(url, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'X-CSRFToken': getCsrf(),
    },
    body: cuerpo,
  }).catch((err) => {
    console.warn('[API] No se pudo enviar el progreso de vídeo:', err)
  })
}
