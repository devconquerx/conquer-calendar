import { describe, expect, it, vi } from 'vitest'
import {
  getFormVariantExperiment,
  getVideoVariantExperiment,
  readFormVariant,
  resolveFormVariant,
} from '../../src/lib/formVariant'

/* Catálogo de funnels reales (slug/escuela/región tal y como están en la BD de
   producción). Los tests recorren TODOS: así, si alguien añade un experimento y
   se le solapa con otro funnel, salta aquí y no en producción. */
const FUNNELS = [
  { slug: 'blocks-latam', themeId: 'conquerblocks', region: 'latam' },
  { slug: 'blocks-eu', themeId: 'conquerblocks', region: 'eu' },
  { slug: 'blocks-eu-2', themeId: 'conquerblocks', region: 'eu' },
  { slug: 'blocks-us', themeId: 'conquerblocks', region: 'us' },
  { slug: 'finance-latam', themeId: 'conquerfinance', region: 'latam' },
  { slug: 'finance-eu', themeId: 'conquerfinance', region: 'eu' },
  { slug: 'finance-us', themeId: 'conquerfinance', region: 'us' },
  { slug: 'languages-latam', themeId: 'conquerlanguages', region: 'latam' },
  { slug: 'languages-eu', themeId: 'conquerlanguages', region: 'eu' },
  { slug: 'languages-us', themeId: 'conquerlanguages', region: 'us' },
  { slug: 'languages-ge', themeId: 'conquerlanguages', region: 'ge' },
  { slug: 'languages-kids-latam', themeId: 'conquerlanguages', region: 'latam' },
  { slug: 'legal-eu', themeId: 'conquerlegal', region: 'eu' },
  { slug: 'especializacion-latam', themeId: 'conquerblocks', region: 'latam' },
  { slug: 'especializacion-eu', themeId: 'conquerblocks', region: 'eu' },
  { slug: 'especializacion-us', themeId: 'conquerblocks', region: 'us' },
]

const experimentoLanding = (f) =>
  getFormVariantExperiment({ themeId: f.themeId, region: f.region, funnelSlug: f.slug })
const experimentoVideo = (f) => getVideoVariantExperiment(f.slug)

describe('registro de experimentos', () => {
  it('asigna a cada funnel el experimento de landing que le toca, y a ninguno más', () => {
    const mapa = Object.fromEntries(
      FUNNELS.map((f) => [f.slug, experimentoLanding(f)?.storageKey || null])
    )
    expect(mapa).toEqual({
      'blocks-latam': 'form_variant_cb_latam',
      'blocks-eu': 'form_variant_cb_eu_fondo',
      'blocks-eu-2': 'form_variant_cb_eu_2_fondo',
      'blocks-us': 'form_variant_cb_us',
      'finance-latam': 'form_variant_cf_latam',
      'finance-eu': 'form_variant_cf',
      'finance-us': null,
      'languages-latam': 'form_variant_cl_latam',
      'languages-eu': 'form_variant_cl_eu',
      'languages-us': 'form_variant_cl_us',
      'languages-ge': null,
      'languages-kids-latam': null,
      'legal-eu': null,
      // Comparten marca y región con blocks-*, pero son funnels propios y NO
      // deben entrar en sus tests.
      'especializacion-latam': null,
      // Cuelga de la marca Blocks y de la región EU, pero es un funnel propio:
      // no debe heredar el experimento de blocks-eu (bug que este test cazó).
      'especializacion-eu': null,
      'especializacion-us': null,
    })
  })

  it('asigna el experimento de vídeo solo a las cinco landings del test del logo', () => {
    const mapa = Object.fromEntries(
      FUNNELS.map((f) => [f.slug, experimentoVideo(f)?.variants.join('/') || null])
    )
    expect(mapa).toMatchObject({
      'blocks-eu': '1/2',
      'blocks-latam': '3/4',
      'blocks-us': '5/6',
      'finance-eu': '7/8',
      'finance-latam': '9/10',
      'finance-us': null,
      'languages-latam': '11/12',
      'languages-eu': '13/14',
      'languages-us': '15/16',
      'legal-eu': null,
      'especializacion-latam': null,
    })
  })

  it('no repite códigos entre experimentos de la misma entidad', () => {
    const codigosLanding = FUNNELS.flatMap((f) => experimentoLanding(f)?.variants || [])
    const codigosVideo = FUNNELS.flatMap((f) => experimentoVideo(f)?.variants || [])
    // Cada experimento aparece una vez por funnel que lo usa; los duplicados
    // legítimos (mismo experimento) se colapsan antes de comparar.
    const unicos = (arr) => [...new Set(arr)]
    expect(unicos(codigosLanding).length).toBe(new Set(unicos(codigosLanding)).size)
    expect(unicos(codigosVideo).length).toBe(new Set(unicos(codigosVideo)).size)
  })

  it('cada experimento declara variantes distintas y una bandera de qué cambia', () => {
    for (const f of FUNNELS) {
      for (const exp of [experimentoLanding(f), experimentoVideo(f)].filter(Boolean)) {
        expect(exp.variants).toHaveLength(2)
        expect(exp.variants[0]).not.toBe(exp.variants[1])
        expect(exp.storageKey).toMatch(/^form_variant_/)
        const banderas = ['whiteBackgroundVariant', 'hideFooterVariant', 'whatsappOptinVariant', 'alwaysPhoneVariant']
        const declaradas = banderas.filter((b) => exp[b])
        expect(declaradas.length).toBeGreaterThan(0)
        // La variante que señala cada bandera tiene que existir en el par.
        for (const b of declaradas) expect(exp.variants).toContain(exp[b])
      }
    }
  })
})

describe('resolveFormVariant', () => {
  const exp = { storageKey: 'form_variant_test', variants: ['1', '2'] }

  it('reparte 50/50 entre visitantes nuevos', () => {
    const cuenta = { 1: 0, 2: 0 }
    for (let i = 0; i < 4000; i++) {
      localStorage.clear()
      cuenta[resolveFormVariant(exp)] += 1
    }
    // Margen amplio a propósito: detecta un sesgo real (p.ej. una variante que
    // no sale nunca) sin volverse inestable por azar.
    expect(cuenta['1']).toBeGreaterThan(1700)
    expect(cuenta['2']).toBeGreaterThan(1700)
  })

  it('conserva la variante del visitante entre visitas', () => {
    const primera = resolveFormVariant(exp)
    expect(resolveFormVariant(exp)).toBe(primera)
    expect(resolveFormVariant(exp)).toBe(primera)
    expect(localStorage.getItem('form_variant_test')).toBe(primera)
  })

  it('acepta ?force_form_variant, lo persiste y lo limpia de la URL', () => {
    window.history.replaceState({}, '', '/landing?force_form_variant=2&utm_source=meta')
    expect(resolveFormVariant(exp)).toBe('2')
    expect(localStorage.getItem('form_variant_test')).toBe('2')
    expect(window.location.search).toBe('?utm_source=meta')
  })

  it('ignora un force que no pertenece a este experimento y deja el parámetro para otro', () => {
    window.history.replaceState({}, '', '/landing?force_form_variant=99')
    expect(exp.variants).toContain(resolveFormVariant(exp))
    expect(window.location.search).toBe('?force_form_variant=99')
  })

  it('reasigna si lo guardado ya no es una variante válida (test renumerado)', () => {
    localStorage.setItem('form_variant_test', '63')
    expect(exp.variants).toContain(resolveFormVariant(exp))
  })

  it('no revienta sin experimento ni con uno incompleto', () => {
    for (const malo of [null, undefined, {}, { storageKey: 'k' }, { variants: [] }]) {
      expect(resolveFormVariant(malo)).toBeNull()
    }
  })

  it('sobrevive a un localStorage bloqueado (modo privado)', () => {
    vi.spyOn(Storage.prototype, 'getItem').mockImplementation(() => { throw new Error('denegado') })
    vi.spyOn(Storage.prototype, 'setItem').mockImplementation(() => { throw new Error('denegado') })
    expect(exp.variants).toContain(resolveFormVariant(exp))
  })
})

describe('readFormVariant', () => {
  const exp = { storageKey: 'form_variant_test', variants: ['1', '2'] }

  it('lee lo guardado sin asignar nada', () => {
    expect(readFormVariant(exp)).toBeNull()
    expect(localStorage.getItem('form_variant_test')).toBeNull()
    localStorage.setItem('form_variant_test', '2')
    expect(readFormVariant(exp)).toBe('2')
  })

  it('devuelve null ante un valor ajeno al experimento', () => {
    localStorage.setItem('form_variant_test', '77')
    expect(readFormVariant(exp)).toBeNull()
  })

  it('no revienta sin experimento — el StepForm lo llama con null en los funnels sin test', () => {
    for (const malo of [null, undefined, {}, { storageKey: 'k' }]) {
      expect(readFormVariant(malo)).toBeNull()
    }
  })
})
