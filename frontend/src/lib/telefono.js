import { getExampleNumber, isValidPhoneNumber, parsePhoneNumberFromString } from 'libphonenumber-js'
import examples from 'libphonenumber-js/mobile/examples'
import countries from '../data/countries'

/**
 * Normaliza un teléfono E.164 a la forma que libphonenumber da por válida.
 *
 * Hoy solo corrige México. En 2019 se eliminó el "1" que llevaban los móviles
 * mexicanos después del +52, pero WhatsApp lo arrastró durante años: muchísima
 * gente tiene su número guardado así y lo copia tal cual. libphonenumber
 * reconoce que es mexicano pero NO le quita ese 1, así que lo daba por inválido
 * y el visitante se quedaba bloqueado en el paso del teléfono — el último antes
 * de agendar la llamada.
 *
 * Se normaliza al construir el número, no solo al validarlo, para que el CRM y
 * Respond.io reciban siempre la forma canónica.
 */
export function normalizarTelefono(valor) {
  if (typeof valor !== 'string') return valor
  const limpio = valor.replace(/\s/g, '')
  // Los tres formatos mexicanos anteriores a 2019: el "1" de móviles, el 045
  // que se marcaba para llamar a un móvil y el 01 de larga distancia. Los tres
  // dejan el número en 11 o 12 dígitos nacionales, y los válidos son 10, así
  // que quitarlos no puede pisar un número bueno.
  const mexicanoAntiguo = /^\+52(?:1|045|01)(\d{10})$/.exec(limpio)
  return mexicanoAntiguo ? `+52${mexicanoAntiguo[1]}` : valor
}

/**
 * Mensaje de teléfono inválido que dice algo útil.
 *
 * El anterior era "Número inválido. Incluye el código de país (ej: +34
 * 612345678)", y el formulario YA tiene un selector de país con su prefijo: se
 * le pedía al visitante justo lo que acababa de hacer, así que no sabía qué
 * corregir. Ahora se nombra el país detectado y se le da un ejemplo real de
 * cómo se escribe un número de ahí.
 */
export function mensajeTelefonoInvalido(valor) {
  let pais = ''
  let ejemplo = ''
  try {
    const iso = parsePhoneNumberFromString(normalizarTelefono(valor || ''))?.country
    if (iso) {
      pais = countries.find((c) => c.iso2 === iso)?.es || ''
      ejemplo = getExampleNumber(iso, examples)?.format('NATIONAL') || ''
    }
  } catch {
    // Si no se puede deducir el país, se cae al mensaje genérico de abajo.
  }

  if (pais && ejemplo) return `Ese número no parece válido para ${pais}. Ejemplo: ${ejemplo}`
  if (pais) return `Ese número no parece válido para ${pais}. Revísalo.`
  return 'Ese número no parece válido. Revisa el país y los dígitos.'
}

/**
 * Construye el E.164 a partir de lo que teclea el visitante y el país que tiene
 * seleccionado.
 *
 * Antes se concatenaba `+prefijo + dígitos` a pelo, y eso falla por los dos
 * lados. Por defecto rechazaba a gente con número bueno: quien copia su número
 * entero del móvil ("+34 612 34 56 78", "0034…") acababa con el prefijo
 * duplicado. Y por exceso dejaba colar números rotos: un estadounidense que
 * escribe "1 213 373 4253" (con el 1 nacional, como se marca allí) generaba
 * +112133734253, que la validación daba por bueno y llega al CRM como un
 * contacto al que nadie puede escribir. Igual con el 011 de Brasil.
 *
 * La regla de cada país —qué prefijo nacional se quita, dónde va el 9, cuántos
 * dígitos tiene— la conoce libphonenumber, así que se le deja interpretar el
 * número con el país como contexto. Si el texto trae un "+" explícito, manda
 * ese país; si no, se interpreta como número nacional del país elegido.
 *
 * Solo cuando la librería no consigue nada se cae a la concatenación de
 * siempre, para que el campo siga produciendo un valor mientras se teclea.
 */
export function construirE164(escrito, iso2, phoneCode) {
  const texto = String(escrito ?? '').trim()
  if (!texto) return ''

  try {
    const parsed = parsePhoneNumberFromString(texto, iso2 || undefined)
    if (parsed?.isValid()) return parsed.number
  } catch {
    // Sigue por el camino de abajo.
  }

  const concatenado = `+${phoneCode || ''}${texto.replace(/\D/g, '')}`
  const mexicano = normalizarTelefono(concatenado)
  try {
    if (isValidPhoneNumber(mexicano)) return mexicano
  } catch {
    // Ni con esas: se devuelve tal cual y que lo juzgue la validación.
  }
  return mexicano
}

/**
 * Parte un E.164 en las piezas que el backend guarda por separado
 * (`lead_phone_prefix` + `lead_phone`) y el país al que pertenece.
 *
 * Hace falta porque esas piezas NO se pueden sacar de lo que el visitante
 * teclea: si pega su número entero, los dígitos ya llevan el prefijo dentro y
 * el CRM acababa guardando "+34" y "34612345678" por separado, o sea un
 * +3434612345678 al reconstruirlo. Se derivan del número ya normalizado.
 */
export function partirE164(e164) {
  try {
    const p = parsePhoneNumberFromString(String(e164 || ''))
    if (p) {
      return {
        prefijo: `+${p.countryCallingCode}`,
        nacional: String(p.nationalNumber),
        iso2: p.country || '',
      }
    }
  } catch {
    // Sin partes utilizables: quien llame decide el fallback.
  }
  return { prefijo: '', nacional: '', iso2: '' }
}
