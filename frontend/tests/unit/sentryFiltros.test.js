/**
 * Los filtros de ruido de Sentry, contra los mensajes REALES de producción.
 *
 * Un filtro que se pasa de ancho deja de traer lo que sí importa. Por eso se
 * fija aquí con los mensajes exactos que hay que tapar y, sobre todo, con los
 * que NO deben taparse nunca.
 */
import { describe, expect, it } from 'vitest'
import {
  ERRORES_DE_NAVEGADORES_EMBEBIDOS,
  ORIGENES_DE_TERCEROS,
  vieneDeUnTercero,
} from '../../src/lib/sentry'

const filtra = (mensaje) => ERRORES_DE_NAVEGADORES_EMBEBIDOS.some((re) => re.test(mensaje))
const evento = (...ficheros) => ({
  exception: { values: [{ stacktrace: { frames: ficheros.map((filename) => ({ filename })) } }] },
})

describe('filtros por mensaje', () => {
  it('tapa los mensajes reales de las apps', () => {
    // Literales de FUNNELS-44/66, 4M, 4R, 73, 4A, 4P, 5P, 6B, 7F, 70.
    expect(filtra('Error invoking postMessage: Java object is gone')).toBe(true)
    expect(filtra('Error invoking process: Java bridge method invocation error')).toBe(true)
    expect(filtra("Cannot read properties of undefined (reading 'domInteractive')")).toBe(true)
    expect(filtra('ReferenceError: xbrowser is not defined')).toBe(true)
    expect(filtra('swbrowser.inNightMode is not a function')).toBe(true)
    expect(filtra('ReferenceError: hideFooterLogo is not defined')).toBe(true)
    expect(filtra("undefined is not an object (evaluating 'window.webkit.messageHandlers')")).toBe(true)
    expect(filtra("undefined is not an object (evaluating 'this.iframeBridge.initHandshake')")).toBe(true)
    expect(filtra('i: Failed to connect to MetaMask')).toBe(true)
    expect(filtra("Cannot read properties of undefined (reading 'M_ID')")).toBe(true)
  })

  it('NO tapa errores nuestros que se le parezcan', () => {
    expect(filtra("Cannot read properties of undefined (reading 'formConfig')")).toBe(false)
    expect(filtra("Cannot read properties of null (reading 'parentNode')")).toBe(false)
    expect(filtra('Invalid hook call. Hooks can only be called inside of the body of a function component.')).toBe(false)
    expect(filtra('Failed to fetch')).toBe(false)
    expect(filtra("Failed to read the 'localStorage' property from 'Window'")).toBe(false)
    expect(filtra('DataError: value too long for type character varying(1500)')).toBe(false)
    // 'browser' a secas no puede activar el patrón de xbrowser/swbrowser.
    expect(filtra('browser is not defined')).toBe(false)
    expect(filtra('Cannot read properties of undefined (reading \'utm_idcampaign\')')).toBe(false)
  })
})

describe('descarte por origen de la pila', () => {
  it('descarta lo que tiró un tercero', () => {
    // FUNNELS-42/43: una extensión rompe document.createEvent y lo llama Cookiebot.
    expect(vieneDeUnTercero(evento(
      'https://www.conquerlanguages.com/static/assets/funnel-BvhLlPcz.js',
      '/uc.js',
      'chrome-extension://dbilanlcioamaadkbepcenpombaejbla/dist/inject_content.js',
    ))).toBe(true)
    // FUNNELS-32: el ping de GA4 fallando dentro del navegador de Instagram.
    expect(vieneDeUnTercero(evento('/gtag/js', '/gtag/js', '/static/assets/funnel-BvhLlPcz.js'))).toBe(true)
    expect(vieneDeUnTercero(evento('iabjs://navigation_performance_logger_android'))).toBe(true)
  })

  it('NO descarta una pila enteramente nuestra', () => {
    expect(vieneDeUnTercero(evento(
      'https://calendar.conquerx.com/static/assets/funnel-B_uLUlBx.js',
      'https://calendar.conquerx.com/static/assets/VideoPage-BSDx9wu8.js',
    ))).toBe(false)
    expect(vieneDeUnTercero({})).toBe(false)
    expect(vieneDeUnTercero({ exception: { values: [{}] } })).toBe(false)
  })

  it('los patrones de origen no pillan ficheros nuestros por accidente', () => {
    const bloquea = (url) => ORIGENES_DE_TERCEROS.some((re) => re.test(url))
    expect(bloquea('https://calendar.conquerx.com/static/assets/plyr-Cwtstkjp.js')).toBe(false)
    expect(bloquea('https://calendar.conquerx.com/static/assets/funnel-B_uLUlBx.js')).toBe(false)
  })
})
