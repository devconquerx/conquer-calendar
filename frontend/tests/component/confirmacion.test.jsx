import { describe, expect, it } from 'vitest'
import { render } from '../../src/funnel-ssr'

/* La confirmación es la última pantalla del recorrido y la que dispara el
   evento Schedule. Cada marca usa el renderer que le toca; este test fija esa
   correspondencia para que un tema nuevo (o un `...defaultTheme` heredado) no
   la mande al renderer equivocado y la deje en blanco, como pasaba en
   Conquer Languages. */
const pintar = (escuela, slug) =>
  render({ stage: 'confirmation', escuela, slug, region: 'latam', formConfig: {}, urls: {}, search: '' })

describe('confirmación por marca', () => {
  it('Blocks usa el renderer paperboard, con sus 3 pasos', () => {
    const html = pintar('conquer-blocks', 'blocks-latam')
    expect(html).toMatch(/Paso 1/i)
    expect(html).toMatch(/Paso 2/i)
    expect(html).toMatch(/Paso 3/i)
  })

  it('Legal también', () => {
    expect(pintar('conquer-legal', 'legal-eu')).toMatch(/Paso 1/i)
  })

  it('Languages renderiza contenido real, no una pantalla vacía', () => {
    for (const slug of ['languages-latam', 'languages-eu', 'languages-us']) {
      const html = pintar('conquer-languages', slug)
      expect(html.length).toBeGreaterThan(500)
      expect(html).toMatch(/felicidades|reservad|confirmad/i)
    }
  })

  it('ninguna marca deja la confirmación en blanco', () => {
    const marcas = [
      ['conquer-blocks', 'blocks-latam'], ['conquer-finance', 'finance-latam'],
      ['conquer-languages', 'languages-latam'], ['conquer-legal', 'legal-eu'],
      ['conquer-languages-kids', 'languages-kids-latam'], ['conquer-blocks-esp', 'especializacion-latam'],
    ]
    for (const [escuela, slug] of marcas) {
      expect(pintar(escuela, slug).length, `${escuela} devolvió una pantalla vacía`).toBeGreaterThan(500)
    }
  })
})
