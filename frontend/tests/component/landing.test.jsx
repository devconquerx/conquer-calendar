import { describe, expect, it, vi } from 'vitest'
import Landing from '../../src/pages/Landing'
import { renderConFunnel } from './helpers'

vi.mock('../../src/api', () => ({ registerLead: vi.fn() }))

const CONFIG = {
  landing: {
    title: 'Titular <strong>de prueba</strong>',
    subtitle: 'Vídeo gratis',
    description: 'descripción',
    bullets: ['uno', 'dos', 'tres'],
    buttonText: 'Ver vídeo gratis',
    instructor: { name: 'Bienvenido Sáez', role: 'Director', description: 'bio' },
    disclaimer: '*aviso',
  },
}

const montar = (opts) =>
  renderConFunnel(
    <Landing school={{ slug: opts.escuela }} program="fullstack" region={opts.region || 'latam'}
             formConfig={CONFIG} funnelSlug={opts.slug} videoEnabled />,
    opts
  )

const fondoDe = (container) => {
  const raiz = container.firstElementChild
  return { clases: raiz.className, estilo: raiz.getAttribute('style') || '' }
}

/* A/B de fondo blanco. Las dos landings de US salieron el 14/09/2026 (ganó el
   papel y pasaron al A/B de teléfono), así que aquí ya no están: su caso vive
   más abajo, comprobando que se quedan en papel pase lo que pase. */
describe('landing — A/B de fondo blanco', () => {
  const CASOS = [
    { marca: 'Languages LATAM', slug: 'languages-latam', escuela: 'conquer-languages', storageKey: 'form_variant_cl_latam', control: '63', blanco: '64' },
  ]

  for (const c of CASOS) {
    it(`${c.marca}: el control conserva el papel`, () => {
      const { container } = montar({ ...c, variante: c.control })
      const { clases, estilo } = fondoDe(container)
      expect(clases).toContain('bg-cb-bg')
      expect(clases).not.toContain('bg-white')
      expect(estilo).toMatch(/background-image/)
    })

    it(`${c.marca}: la variante de test deja la página en blanco, sin textura`, () => {
      const { container } = montar({ ...c, variante: c.blanco })
      const { clases, estilo } = fondoDe(container)
      expect(clases).toContain('bg-white')
      expect(clases).not.toContain('bg-cb-bg')
      expect(estilo).not.toMatch(/background-image/)
    })

    it(`${c.marca}: en la variante de test las tarjetas también van en blanco`, () => {
      const { container } = montar({ ...c, variante: c.blanco })
      const tarjetas = [...container.querySelectorAll('[style*="background-color"]')]
        .map((d) => d.getAttribute('style'))
      expect(tarjetas.length).toBeGreaterThan(0)
      for (const estilo of tarjetas) {
        expect(estilo).not.toMatch(/#F6F6F6/i)
        expect(estilo).not.toMatch(/url\(/)
      }
    })
  }

  /* Blocks y Finance LATAM cerraron el test el 07/10/2026 con el BLANCO como
     ganador: blanco para todos, también para quien tenía guardado el papel. */
  for (const c of [
    { marca: 'Blocks LATAM', slug: 'blocks-latam', escuela: 'conquer-blocks', storageKey: 'form_variant_cb_latam', viejo: '57' },
    { marca: 'Finance LATAM', slug: 'finance-latam', escuela: 'conquer-finance', storageKey: 'form_variant_cf_latam', viejo: '61' },
  ]) {
    it(`${c.marca}: ganó el blanco, sale blanca sin sortear`, () => {
      const { container } = montar({ slug: c.slug, escuela: c.escuela })
      expect(fondoDe(container).clases).toContain('bg-white')
      expect(fondoDe(container).estilo).not.toMatch(/background-image/)
    })

    it(`${c.marca}: quien tenía el papel guardado también la ve blanca`, () => {
      const { container } = montar({ ...c, variante: c.viejo })
      expect(fondoDe(container).clases).toContain('bg-white')
    })
  }

  it('un experimento que no habla de fondo (Finance EU) no blanquea la landing', () => {
    // Finance EU corre el A/B de teléfono/WhatsApp (55/56), no el de fondo: el
    // hecho de tener experimento no debe pintar de blanco. Antes este caso
    // usaba Blocks EU, que desde el 27/08/2026 sí corre el de fondo (69/70).
    const { container } = montar({
      slug: 'finance-eu', escuela: 'conquer-finance', region: 'eu',
      storageKey: 'form_variant_cf', variante: '56',
    })
    expect(fondoDe(container).clases).not.toContain('bg-white')
  })

  for (const c of [
    { marca: 'Blocks US', slug: 'blocks-us', escuela: 'conquer-blocks', storageKey: 'form_variant_cb_us_tel', checkbox: '74' },
    { marca: 'Languages US', slug: 'languages-us', escuela: 'conquer-languages', storageKey: 'form_variant_cl_us_tel', checkbox: '76' },
  ])
    it(`${c.marca}: cerró el test de fondo, se queda en papel en las dos ramas`, () => {
      // Ni la rama de checkbox ni un código de fondo viejo que quedara en
      // localStorage pueden volver a blanquear la landing.
      localStorage.setItem('form_variant_cb_us', '60')
      localStorage.setItem('form_variant_cl_us', '68')
      const { container } = montar({ ...c, region: 'us', variante: c.checkbox })
      expect(fondoDe(container).clases).toContain('bg-cb-bg')
      expect(fondoDe(container).clases).not.toContain('bg-white')
    })

  /* Blocks EU, Blocks EU-2 y Languages EU cerraron el test el 07/10/2026 con el
     PAPEL como ganador: papel para todos, también para quien tenía el blanco. */
  for (const c of [
    { marca: 'Blocks EU', slug: 'blocks-eu', escuela: 'conquer-blocks', storageKey: 'form_variant_cb_eu_fondo', viejo: '70' },
    { marca: 'Blocks EU-2', slug: 'blocks-eu-2', escuela: 'conquer-blocks', storageKey: 'form_variant_cb_eu_2_fondo', viejo: '72' },
    { marca: 'Languages EU', slug: 'languages-eu', escuela: 'conquer-languages', storageKey: 'form_variant_cl_eu', viejo: '66' },
  ])
    it(`${c.marca}: ganó el papel, aunque tuviera el blanco guardado`, () => {
      const { container } = montar({ ...c, region: 'eu', variante: c.viejo })
      expect(fondoDe(container).clases).toContain('bg-cb-bg')
      expect(fondoDe(container).clases).not.toContain('bg-white')
    })

  it('la variante del vídeo no afecta al fondo de la landing', () => {
    // Se fijan LAS DOS variantes: si solo se fijara la del vídeo, la de la
    // landing se sortearía al montar y el test saldría blanco la mitad de las
    // veces (era flaky así). Con la de la landing en control, lo único que
    // puede mover el fondo es la del vídeo — y no debe.
    localStorage.setItem('form_variant_cl_latam', '63')
    const { container } = montar({
      slug: 'languages-latam', escuela: 'conquer-languages',
      storageKey: 'form_variant_video_cl_latam', variante: '12',
    })
    expect(fondoDe(container).clases).toContain('bg-cb-bg')
  })
})
