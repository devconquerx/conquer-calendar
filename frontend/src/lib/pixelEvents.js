/**
 * Pixel event helpers for Meta, Google (gtag) and TikTok.
 *
 * Los scripts base se cargan server-side en page.html.
 * Este módulo dispara los eventos de conversión desde React.
 */

import { getPixelIds, normalizeSchool } from './pixelConfig'

// ---------------------------------------------------------------------------
// DataLayer (compat)
// ---------------------------------------------------------------------------

export function pushToDataLayer(data) {
  window.dataLayer = window.dataLayer || []
  window.dataLayer.push(data)
}

// ---------------------------------------------------------------------------
// Meta Pixel
// ---------------------------------------------------------------------------

export function setMetaAdvancedMatching({ schoolSlug, email, phone, name }) {
  if (typeof window.fbq === 'undefined') return
  const ids = getPixelIds(schoolSlug)
  if (!ids) return

  const matchData = {}
  if (email) matchData.em = email.trim().toLowerCase()
  if (phone) {
    const digits = phone.replace(/[^0-9]/g, '')
    if (digits) matchData.ph = digits
  }
  if (name) matchData.fn = name.trim().split(' ')[0].toLowerCase()

  window.fbq('init', ids.meta, matchData)
}

function fireMetaLead({ eventId }) {
  if (typeof window.fbq === 'undefined') return
  window.fbq('track', 'Lead', {}, { eventID: eventId })
}

function fireMetaSchedule({ eventId }) {
  if (typeof window.fbq === 'undefined') return
  window.fbq('track', 'Schedule', {}, { eventID: eventId })
}

// ---------------------------------------------------------------------------
// Google Ads / GA4 (via gtag)
// ---------------------------------------------------------------------------

function fireGoogleAdsConversion({ eventId, schoolSlug, type }) {
  if (typeof window.gtag === 'undefined') return
  const ids = getPixelIds(schoolSlug)
  if (!ids?.googleAds?.conversions?.[type]) return

  const conversionLabel = ids.googleAds.conversions[type]
  window.gtag('event', 'conversion', {
    send_to: `AW-${ids.googleAds.customerId}/${conversionLabel}`,
    transaction_id: eventId,
  })
}

function fireGA4Event({ eventName, params }) {
  if (typeof window.gtag === 'undefined') return
  window.gtag('event', eventName, params || {})
}

// ---------------------------------------------------------------------------
// TikTok Pixel
// ---------------------------------------------------------------------------

function fireTikTokEvent({ eventId, journeyId, eventName, email, phone }) {
  if (typeof window.ttq === 'undefined') return

  const identify = { external_id: journeyId }
  if (email) identify.email = email.trim().toLowerCase()
  if (phone) {
    const digits = phone.replace(/[^0-9]/g, '')
    if (digits) identify.phone_number = '+' + digits
  }

  window.ttq.identify(identify)
  window.ttq.track(eventName, {}, { event_id: eventId })
}

// ---------------------------------------------------------------------------
// Legacy / dataLayer compat
// ---------------------------------------------------------------------------

export function fireFormSubmitEvent({ eventId, email, name, phone, fbclid, fbp }) {
  pushToDataLayer({
    event: 'form_submit_lead',
    form_email: email || '',
    form_name: name || '',
    form_phone: phone || '',
    event_id: eventId || '',
    fbclid: fbclid || '',
    fbp: fbp || '',
  })
}

export function fireTikTokSubmitForm({ eventId, journeyId, email, phone }) {
  fireTikTokEvent({ eventId, journeyId, eventName: 'SubmitForm', email, phone })
}

// ---------------------------------------------------------------------------
// Unified wrappers — fire ALL platforms with one call
// ---------------------------------------------------------------------------

/** Fire Lead/SubmitForm event on all platforms. Used on form submit. */
export function fireAllLead({ eventId, journeyId, email, phone, name, schoolSlug, fbp, fbc }) {
  setMetaAdvancedMatching({ schoolSlug, email, phone, name })
  fireMetaLead({ eventId })

  fireGoogleAdsConversion({ eventId, schoolSlug, type: 'lead' })

  fireGA4Event({ eventName: 'generate_lead', params: { event_id: eventId } })

  fireTikTokEvent({ eventId, journeyId, eventName: 'SubmitForm', email, phone })

  fireFormSubmitEvent({ eventId, email, name, phone, fbclid: '', fbp: fbp || '' })
}

/**
 * Fire Schedule event on all platforms. Se dispara tras agendar en Calendly.
 * Firma idéntica al funnel de Django (incluye calendly_event_uuid y
 * schedule_event_id en el dataLayer).
 */
export function fireAllSchedule({ eventId, journeyId, schoolSlug, calendlyEventUuid, scheduleEventId }) {
  fireMetaSchedule({ eventId })

  fireGoogleAdsConversion({ eventId, schoolSlug, type: 'schedule' })

  fireGA4Event({ eventName: 'schedule_call', params: { event_id: eventId } })

  fireTikTokEvent({ eventId, journeyId, eventName: 'Schedule' })

  pushToDataLayer({
    event: 'calendly_scheduled',
    event_id: eventId,
    journey_id: journeyId,
    calendly_event_uuid: calendlyEventUuid || '',
    schedule_event_id: scheduleEventId || '',
  })
}

export { normalizeSchool }
