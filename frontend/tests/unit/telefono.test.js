/**
 * El campo de teléfono, atacado a propósito.
 *
 * Es el último paso antes de agendar: lo que se rechace aquí son llamadas que
 * no se reservan, y lo que se acepte mal son contactos a los que luego nadie
 * puede escribir. Antes se construía el número concatenando `+prefijo` con los
 * dígitos tecleados, y eso fallaba por los dos lados a la vez.
 *
 * Por eso la mayoría de los casos comprueban el VALOR resultante, no solo que
 * se acepte: el fallo peor que tenía no era rechazar, era aceptar un número
 * roto (un +112133734253 de Estados Unidos, o el +540111523456789 que salía del
 * formato argentino "011 15") y mandarlo al CRM como bueno.
 */
import { describe, expect, it } from 'vitest'
import { construirE164, mensajeTelefonoInvalido, normalizarTelefono, partirE164 } from '../../src/lib/telefono'
import { validateBlock } from '../../src/lib/validateBlock'

const construir = (escrito, iso, code) => construirE164(escrito, iso, code)
const esValido = (valor) => validateBlock({ name: 'phone-number' }, valor)
const marcar = (escrito, iso, code) => esValido(construir(escrito, iso, code))

describe('lo que la gente escribe de verdad', () => {
  // [país, prefijo, lo que teclea, E.164 que debe salir]
  const CASOS = [
    ['ES', '34', '612345678', '+34612345678'],
    ['ES', '34', '612 34 56 78', '+34612345678'],
    ['ES', '34', '612-345-678', '+34612345678'],
    ['MX', '52', '5512345678', '+525512345678'],
    ['AR', '54', '1123456789', '+541123456789'],
    ['AR', '54', '91123456789', '+5491123456789'],
    ['CO', '57', '3001234567', '+573001234567'],
    ['PE', '51', '987654321', '+51987654321'],
    ['CL', '56', '912345678', '+56912345678'],
    ['EC', '593', '991234567', '+593991234567'],
    ['US', '1', '2133734253', '+12133734253'],
    ['US', '1', '(213) 373-4253', '+12133734253'],
    ['IT', '39', '3123456789', '+393123456789'],
    ['PT', '351', '912345678', '+351912345678'],
    ['GB', '44', '7400123456', '+447400123456'],
  ]
  it.each(CASOS)('%s: "%s" → %s', (iso, code, escrito, esperado) => {
    expect(construir(escrito, iso, code)).toBe(esperado)
    expect(esValido(esperado)).toBe(true)
  })
})

describe('pega su número entero, con prefijo incluido', () => {
  // Copiar el número de los contactos o de WhatsApp es lo más normal del mundo,
  // y antes se duplicaba el prefijo y se rechazaba a todos.
  const CASOS = [
    ['ES', '34', '+34 612345678', '+34612345678'],
    ['ES', '34', '0034 612345678', '+34612345678'],
    ['ES', '34', '34612345678', '+34612345678'],
    ['MX', '52', '+52 5512345678', '+525512345678'],
    ['CO', '57', '+57 3001234567', '+573001234567'],
    ['AR', '54', '+54 9 11 2345-6789', '+5491123456789'],
  ]
  it.each(CASOS)('%s: "%s" → %s', (iso, code, escrito, esperado) => {
    expect(construir(escrito, iso, code)).toBe(esperado)
  })
})

describe('prefijos nacionales: aquí es donde colaban números rotos', () => {
  it('Estados Unidos con el 1 delante ya no genera +11…', () => {
    // Antes: +112133734253, que la validación daba por bueno.
    expect(construir('12133734253', 'US', '1')).toBe('+12133734253')
  })

  it('Argentina en formato "011 15" ya no genera un número imposible', () => {
    // Antes: +540111523456789 — aceptado y sin embargo inservible.
    expect(construir('011 15 2345-6789', 'AR', '54')).toBe('+5491123456789')
  })

  it('Brasil con el 0 del DDD', () => {
    expect(construir('011 91234-5678', 'BR', '55')).toBe('+5511912345678')
  })

  it('el 0 nacional argentino y el británico', () => {
    expect(construir('01123456789', 'AR', '54')).toBe('+541123456789')
    expect(construir('07400123456', 'GB', '44')).toBe('+447400123456')
  })
})

describe('formatos mexicanos anteriores a 2019', () => {
  // Se eliminaron, pero WhatsApp los arrastró años y la gente los tiene
  // guardados así. México es el 5,7% de los leads con teléfono.
  it.each([
    ['el 1 de móviles', '15512345678'],
    ['con espacios', '1 55 1234 5678'],
    ['el 045', '045 55 1234 5678'],
    ['el 01', '01 55 1234 5678'],
  ])('%s → +525512345678', (_nombre, escrito) => {
    expect(construir(escrito, 'MX', '52')).toBe('+525512345678')
    expect(marcar(escrito, 'MX', '52')).toBe(true)
  })

  it('normalizarTelefono no toca los números de otros países', () => {
    for (const n of ['+34612345678', '+5491123456789', '+12133734253', '+525512345678']) {
      expect(normalizarTelefono(n)).toBe(n)
    }
  })

  it('no inventa un número donde no lo hay', () => {
    expect(normalizarTelefono('+5211234')).toBe('+5211234')
    expect(normalizarTelefono(null)).toBe(null)
    expect(normalizarTelefono(undefined)).toBe(undefined)
  })
})

describe('lo que NO debe colar', () => {
  it.each([
    ['todo ceros', '000000000', 'ES', '34'],
    ['todo unos', '111111111', 'ES', '34'],
    ['secuencia', '123456789', 'ES', '34'],
    ['secuencia US', '1234567890', 'US', '1'],
    ['prefijo inexistente de EE.UU.', '5464846484', 'US', '1'],
    ['demasiado corto', '6', 'ES', '34'],
    ['demasiado largo', '9'.repeat(40), 'ES', '34'],
    ['solo letras', 'FLOWERS', 'US', '1'],
    ['vacío', '', 'ES', '34'],
    ['espacios', '   ', 'ES', '34'],
  ])('rechaza %s', (_nombre, escrito, iso, code) => {
    expect(marcar(escrito, iso, code)).toBe(false)
  })

  it('no revienta con entradas imposibles', () => {
    for (const raro of [null, undefined, 12345, {}, []]) {
      expect(() => construirE164(raro, 'ES', '34')).not.toThrow()
    }
  })
})

describe('mensaje de error', () => {
  it('nombra el país y da un ejemplo real cuando puede deducirlo', () => {
    expect(mensajeTelefonoInvalido('+34600')).toContain('España')
    expect(mensajeTelefonoInvalido('+34600')).toMatch(/Ejemplo: \d/)
    expect(mensajeTelefonoInvalido('+525512')).toContain('México')
  })

  it('nunca vuelve a pedir el código de país, que el formulario ya tiene puesto', () => {
    for (const n of ['+15464846484', '+34600', 'sinsentido', '']) {
      expect(mensajeTelefonoInvalido(n)).not.toContain('código de país')
    }
  })
})

describe('partir el número para el CRM', () => {
  // La landing guarda el prefijo y el número nacional en columnas distintas. Si
  // esas piezas salen de lo tecleado en vez del número normalizado, quien pega
  // su número entero acaba en el CRM como +3434612345678.
  it.each([
    ['+34612345678', '+34', '612345678', 'ES'],
    ['+525512345678', '+52', '5512345678', 'MX'],
    ['+5491123456789', '+54', '91123456789', 'AR'],
    ['+12133734253', '+1', '2133734253', 'US'],
  ])('%s → prefijo %s, nacional %s', (e164, prefijo, nacional, iso2) => {
    expect(partirE164(e164)).toEqual({ prefijo, nacional, iso2 })
  })

  it('el número pegado entero se parte bien, no se duplica el prefijo', () => {
    const e164 = construirE164('+34 612345678', 'ES', '34')
    expect(partirE164(e164)).toEqual({ prefijo: '+34', nacional: '612345678', iso2: 'ES' })
  })

  it('devuelve piezas vacías en vez de reventar con basura', () => {
    for (const raro of ['', 'sinsentido', null, undefined]) {
      expect(() => partirE164(raro)).not.toThrow()
      expect(partirE164(raro).nacional).toBe('')
    }
  })
})
