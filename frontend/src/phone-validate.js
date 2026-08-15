/**
 * Validación de teléfono para la página pública de reserva (template Django, sin
 * React). Expone en `window.CQXPhone` lo mismo que usa el funnel — la librería es
 * la misma y la metadata también, así que un número aceptado aquí lo acepta el
 * funnel y al revés.
 *
 * `esValido` es la validación ESTRICTA (`isValidPhoneNumber`): no solo mira la
 * longitud, también que el prefijo nacional exista de verdad en ese país. Es lo
 * que corta los "+58 11" y los "+58 1111111111111111" antes de crear la reserva.
 *
 * La página degrada sola: si este bundle no carga, el formulario sigue
 * funcionando con la validación de servidor como única red.
 */
import { AsYouType, getExampleNumber, isValidPhoneNumber } from 'libphonenumber-js'
import examples from 'libphonenumber-js/mobile/examples'

window.CQXPhone = {
  /** ¿Es un número real de ese país? `e164` en formato "+58 4121234567". */
  esValido(e164) {
    if (!e164) return false
    try {
      return isValidPhoneNumber(e164)
    } catch {
      return false
    }
  },

  /**
   * Número de ejemplo del país para usarlo de placeholder. En formato nacional
   * y sin el 0 de marcación que algunos países le ponen delante (Venezuela:
   * "0412-1234567"), porque en este campo el prefijo va aparte y ese 0 sobra.
   */
  ejemploNacional(iso2) {
    if (!iso2) return ''
    try {
      const ejemplo = getExampleNumber(iso2, examples)?.format('NATIONAL') || ''
      return ejemplo.replace(/^0+/, '').trim()
    } catch {
      return ''
    }
  },

  /** Formatea mientras se escribe, con los grupos de dígitos propios del país. */
  formatear(valor, iso2) {
    if (!iso2) return valor
    try {
      return new AsYouType(iso2).input(valor)
    } catch {
      return valor
    }
  },
}

// Este módulo se ejecuta después del script inline de la página (los módulos ES
// van diferidos), así que cuando la página pintó su placeholder todavía no
// existía `window.CQXPhone`. El aviso le deja repintarlo con el ejemplo del país.
document.dispatchEvent(new CustomEvent('cqxphone:listo'))
