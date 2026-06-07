/**
 * Lee del query string los datos de lead que la landing propaga (name, email,
 * phone…) para pre-rellenar el StepForm, igual que el funnel de Django
 * (funnels/frontend/src/lib/prefillParams.js).
 *
 * El PhoneField de conquer-calendar usa un teléfono E.164 plano ("+34612…"),
 * así que aquí `phone` se devuelve como string E.164 (no como el JSON
 * estructurado de funnels-new). La landing ya manda `phone` en ese formato; si
 * no, se reconstruye desde `lead_phone` + `lead_phone_prefix` (claves legacy).
 */

function onlyDigits(value) {
  return String(value || '').replace(/\D/g, '')
}

function buildLegacyPhone(params) {
  const digits = onlyDigits(params.get('lead_phone'))
  if (!digits) return ''
  const prefix = onlyDigits(params.get('lead_phone_prefix'))
  return prefix ? `+${prefix}${digits}` : `+${digits}`
}

export function getPrefillFromSearch(search) {
  const params = new URLSearchParams(search || '')
  const canonicalPhone = (params.get('phone') || '').trim()
  return {
    name: params.get('name') || params.get('fullname') || '',
    email: params.get('email') || '',
    originalEmail: params.get('original_email') || '',
    phone: canonicalPhone || buildLegacyPhone(params),
  }
}

/** Subconjunto del prefill mapeado a los ids de bloque del StepForm. */
export function getPrefillRespuestas(search) {
  const { name, email, phone } = getPrefillFromSearch(search)
  const init = {}
  if (name) init.name = name
  if (email) init.email = email
  if (phone) init.phone = phone
  return init
}
