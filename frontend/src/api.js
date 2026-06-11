import * as Sentry from '@sentry/react'
import { apiUrl } from './lib/apiBase'

function getCsrf() {
  return document.getElementById('funnel-root')?.dataset?.csrf || ''
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
  fetch(apiUrl('/f/api/lead/'), {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'X-CSRFToken': getCsrf(),
    },
    body: JSON.stringify(payload),
  }).catch((err) => {
    console.error('[API] Error registering lead:', err)
    Sentry.captureException(err, { tags: { action: 'registerLead' } })
  })
}

/**
 * Reporta el progreso de visualización del video (cada 10%) al backend, que
 * actualiza el Lead. Fire-and-forget: nunca bloquea ni rompe la reproducción.
 */
export function sendVideoProgressToBackend({ email, percent, school, region }) {
  fetch(apiUrl('/f/api/video-progress/'), {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'X-CSRFToken': getCsrf(),
    },
    body: JSON.stringify({ email, percent, school, region }),
  }).catch((err) => {
    console.error('[API] Error sending video progress:', err)
    Sentry.captureException(err, { tags: { action: 'sendVideoProgressToBackend' } })
  })
}
