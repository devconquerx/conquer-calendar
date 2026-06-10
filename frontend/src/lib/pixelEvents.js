/**
 * Event helpers — arquitectura server-side GTM (sGTM).
 *
 * El contenedor GTM se carga server-side en el <head> a través del loader
 * first-party (load.somos.<marca>.com → _includes/_sgtm_head.html). Es ese
 * contenedor el ÚNICO responsable de disparar Meta / GA4 / Google Ads / TikTok
 * hacia el server-side GTM.
 *
 * Por eso aquí NO llamamos a window.fbq / window.gtag / window.ttq: solo
 * empujamos eventos semánticos al dataLayer y GTM los recoge con sus triggers.
 * Las firmas públicas se mantienen para no tocar los componentes.
 *
 * Eventos emitidos al dataLayer (configurar el trigger en el contenedor GTM):
 *   - 'virtual_page_view'  → PageView en cambios de etapa SPA (sin recarga)
 *   - 'form_submit_lead'   → Lead / SubmitForm   (al enviar el formulario)
 *   - 'calendly_scheduled' → Schedule            (tras agendar en Calendly)
 * El campo `event_id` permite la deduplicación con el server-side / CAPI.
 */

import { normalizeSchool } from './pixelConfig'

// ---------------------------------------------------------------------------
// DataLayer
// ---------------------------------------------------------------------------

export function pushToDataLayer(data) {
  window.dataLayer = window.dataLayer || []
  window.dataLayer.push(data)
}

// ---------------------------------------------------------------------------
// Unified wrappers — un solo dataLayer.push por acción; GTM dispara los tags
// ---------------------------------------------------------------------------

/**
 * Pageview virtual para navegaciones SPA (pushState). El PageView de la carga
 * inicial lo dispara el contenedor GTM al cargar; este se usa al cambiar de
 * etapa (landing → video → stepform → confirmación) sin recarga.
 */
export function fireAllPageView() {
  pushToDataLayer({
    event: 'virtual_page_view',
    page_location: window.location.href,
    page_path: window.location.pathname,
  })
}

/**
 * Lead / SubmitForm — al enviar el formulario.
 * GTM mapea este evento a Meta Lead, GA4 generate_lead, Google Ads (lead) y
 * TikTok SubmitForm, enviándolos al server-side GTM.
 */
export function fireAllLead({ eventId, journeyId, email, phone, name, schoolSlug, fbp, fbc }) {
  pushToDataLayer({
    event: 'form_submit_lead',
    school: normalizeSchool(schoolSlug),
    event_id: eventId || '',
    journey_id: journeyId || '',
    // Datos para advanced matching / server-side (GTM los hashea/normaliza)
    lead_email: email || '',
    lead_phone: phone || '',
    lead_name: name || '',
    fbp: fbp || '',
    fbc: fbc || '',
    // Aliases que ya consumía el contenedor existente
    form_email: email || '',
    form_name: name || '',
    form_phone: phone || '',
  })
}

/**
 * Schedule — tras agendar la llamada en Calendly.
 * GTM mapea este evento a Meta Schedule, GA4 schedule_call, Google Ads
 * (schedule) y TikTok Schedule, enviándolos al server-side GTM.
 */
export function fireAllSchedule({ eventId, journeyId, schoolSlug, calendlyEventUuid, scheduleEventId }) {
  pushToDataLayer({
    event: 'calendly_scheduled',
    school: normalizeSchool(schoolSlug),
    event_id: eventId || '',
    journey_id: journeyId || '',
    calendly_event_uuid: calendlyEventUuid || '',
    schedule_event_id: scheduleEventId || '',
  })
}

export { normalizeSchool }
