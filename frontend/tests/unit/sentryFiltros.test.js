/**
 * Los filtros de ruido de Sentry, contra los mensajes REALES de producción.
 *
 * Un `ignoreErrors` es un filtro ciego por texto: si se pasa de ancho, deja de
 * llegar lo que sí importa. Por eso se fija aquí con los mensajes exactos que
 * hay que tapar y, sobre todo, con los que NO deben taparse nunca.
 */
import { describe, expect, it } from 'vitest'
import { ERRORES_DE_NAVEGADORES_EMBEBIDOS, URLS_DE_TERCEROS } from '../../src/lib/sentry'

const filtra = (mensaje) => ERRORES_DE_NAVEGADORES_EMBEBIDOS.some((re) => re.test(mensaje))

describe('filtros de ruido de navegadores embebidos', () => {
  it('tapa los mensajes reales de Instagram y TikTok', () => {
    // Copiados literalmente de FUNNELS-44/66 y FUNNELS-4M.
    expect(filtra('Error invoking postMessage: Java object is gone')).toBe(true)
    expect(filtra("Cannot read properties of undefined (reading 'domInteractive')")).toBe(true)
  })

  it('NO tapa errores nuestros que se le parezcan', () => {
    expect(filtra("Cannot read properties of undefined (reading 'formConfig')")).toBe(false)
    expect(filtra("Cannot read properties of null (reading 'parentNode')")).toBe(false)
    expect(filtra('Invalid hook call. Hooks can only be called inside of the body of a function component.')).toBe(false)
    expect(filtra('Failed to fetch')).toBe(false)
    expect(filtra("Failed to read the 'localStorage' property from 'Window'")).toBe(false)
  })

  it('descarta los scripts inyectados por la app anfitriona, y solo esos', () => {
    const bloquea = (url) => URLS_DE_TERCEROS.some((re) => re.test(url))
    expect(bloquea('iabjs://navigation_performance_logger_android')).toBe(true)
    expect(bloquea('https://calendar.conquerx.com/static/assets/funnel-B_uLUlBx.js')).toBe(false)
  })
})
