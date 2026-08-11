import { parsePhoneNumber } from 'libphonenumber-js'
import countries from '../data/countries'

/**
 * Deriva el país (nombre en inglés, para calzar con las claves de
 * FunnelScoring) desde un teléfono en formato E.164 (+<código><número>).
 *
 * Réplica de `phone.country.en` en mainFormSubmission.js del funnel viejo:
 * ahí el 'country' que promedia el score (`country_score + q1..q6`) sale del
 * teléfono tecleado en la pregunta de scoring, NO del honeypot de la
 * landing (que es un campo distinto, solo para autofill/atribución).
 *
 * Devuelve '' si el teléfono no es parseable o el país no está en `countries`.
 */
export function countryFromPhone(phone) {
  if (!phone) return ''
  try {
    const parsed = parsePhoneNumber(phone)
    if (!parsed?.country) return ''
    return countries.find((c) => c.iso2 === parsed.country)?.en || ''
  } catch {
    return ''
  }
}
