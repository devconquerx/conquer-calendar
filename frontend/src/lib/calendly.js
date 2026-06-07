/**
 * Helpers de Calendly — port de conquerx-funnels-new/src/components/mainForm.helpers.js.
 *
 * Construyen la URL del widget de Calendly con prefill (nombre/email/teléfono),
 * UTMs y un `utm_term` de tracking (`utm_term_original|journey_id|schedule_event_id`),
 * y resuelven el layout del widget + el mes a mostrar.
 */

export const QUERY_PARAM_KEYS = [
  'utm_source',
  'utm_medium',
  'utm_campaign',
  'utm_term',
  'utm_content',
  'utm_idcampaign',
  'utm_adsetid',
  'utm_adid',
]

function formatYearMonth(year, month) {
  return `${year}-${month.toString().padStart(2, '0')}`
}

/** Layout del widget según el ancho del viewport (móvil vs escritorio). */
export function getCalendlyWidgetLayout(viewportWidth) {
  const isMobile = viewportWidth <= 768
  return {
    isMobile,
    shouldLockScroll: isMobile,
    widgetHeight: isMobile ? '100%' : '1150px',
    sectionMinHeight: isMobile ? '100vh' : '1150px',
  }
}

/** utm_term de tracking: `utm_term_original|journey_id|schedule_event_id`. */
export function buildCalendlyTrackingTerm(originalUtmTerm = '', journeyId = '', scheduleEventId = '') {
  return `${originalUtmTerm || '_'}|${journeyId || '_'}|${scheduleEventId || '_'}`
}

/** Params del widget: prefill (name/email/a1), mes y UTMs (con utm_term de tracking). */
export function buildCalendlyParams({
  body,
  queryParams = QUERY_PARAM_KEYS,
  monthValue = '',
  journeyId = '',
  scheduleEventId = '',
  includeMonth = true,
}) {
  const params = {
    name: body.lead_name || '',
    email: body.lead_email || '',
    a1: body.lead_phone_number || '',
  }

  if (includeMonth && monthValue) {
    params.month = monthValue
  }

  for (const key of queryParams) {
    params[key] = body[key] || ''
  }

  params.utm_term = buildCalendlyTrackingTerm(params.utm_term, journeyId, scheduleEventId)
  return params
}

/** URL final del widget con los params serializados + hide_gdpr_banner. */
export function buildCalendlyUrl(baseUrl, params) {
  const serialized = new URLSearchParams(params).toString().replace(/\+/g, ' ')
  return `${baseUrl}?${serialized}&hide_gdpr_banner=1`
}

/** Extrae el UUID del evento de Calendly desde un postMessage de la web. */
export function extractCalendlyEventUuid(messageEvent) {
  if (messageEvent?.origin !== 'https://calendly.com') return ''
  if (messageEvent?.data?.event !== 'calendly.event_scheduled') return ''
  const eventUri = messageEvent.data?.payload?.event?.uri || ''
  return eventUri.split('/').pop() || ''
}

/**
 * Año-mes (`YYYY-MM`) que debe pre-seleccionar Calendly. Sin la tabla de
 * excepciones de la API (no portada), usa solo la lógica de fin de mes del
 * original: salta al mes siguiente en los últimos días/horarios.
 */
export function getYearMonthForCalendly({ now = new Date() } = {}) {
  let year = now.getFullYear()
  let month = now.getMonth() + 1
  const day = now.getDate()
  const hour = now.getHours()
  const dayOfWeek = now.getDay()
  const lastDayOfMonth = new Date(year, month, 0).getDate()

  let shouldSwitchMonth = false
  if (day === lastDayOfMonth) {
    if (hour >= 14 || dayOfWeek === 6 || dayOfWeek === 0) {
      shouldSwitchMonth = true
    }
  } else if (day === lastDayOfMonth - 1) {
    if (dayOfWeek === 6 || (dayOfWeek === 5 && hour >= 14)) {
      shouldSwitchMonth = true
    }
  }

  if (shouldSwitchMonth) {
    month += 1
    if (month > 12) {
      month = 1
      year += 1
    }
  }

  return formatYearMonth(year, month)
}
