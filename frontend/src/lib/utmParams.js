/**
 * UTM parameter and click ID extraction from current URL.
 */

export const TRACKING_QUERY_KEYS = [
  'utm_source',
  'utm_medium',
  'utm_campaign',
  'utm_content',
  'utm_term',
  'utm_idcampaign',
  'utm_adsetid',
  'utm_adid',
  'conditions',
  'product',
  '_ga',
  '_gid',
]

const CLICK_ID_KEYS = [
  'gclid',
  'gbraid',
  'wbraid',
  'fbclid',
  'msclkid',
  'dclid',
  'ttclid',
  'gclsrc',
]

/** Read UTM params from current URL */
export function getUtmParams() {
  if (typeof window === 'undefined') return {}
  const params = new URLSearchParams(window.location.search)
  const result = {}
  for (const key of TRACKING_QUERY_KEYS) {
    const val = params.get(key)
    if (val) result[key] = val
  }
  return result
}

/** Read ad platform click IDs from current URL */
export function getClickIds() {
  if (typeof window === 'undefined') return {}
  const params = new URLSearchParams(window.location.search)
  const result = {}
  for (const key of CLICK_ID_KEYS) {
    const val = params.get(key)
    if (val) result[key] = val
  }
  return result
}

/**
 * Build a flat tracking payload combining UTMs + click IDs + pixel cookies + tracking IDs.
 */
export function buildTrackingPayload({ eventId, journeyId, uuid, utmParams, clickIds, pixelCookies }) {
  return {
    event_id: eventId,
    journey_id: journeyId,
    // uuid de la Prellamada (clave de upsert en el CRM). Solo se incluye si viene.
    ...(uuid ? { uuid } : {}),
    ...utmParams,
    ...clickIds,
    _fbc: pixelCookies?._fbc || '',
    _fbp: pixelCookies?._fbp || '',
    _ttp: pixelCookies?._ttp || '',
    user_agent: navigator.userAgent || '',
    url: window.location.href,
  }
}
