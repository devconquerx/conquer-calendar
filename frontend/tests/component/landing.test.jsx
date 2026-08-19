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

/* A/B de fondo blanco: Blocks LATAM/US y Finance LATAM. Cambia SOLO la landing;
   el resto del funnel conserva su papel (eso se comprueba en ssr.smoke y e2e). */
describe('landing — A/B de fondo blanco', () => {
  const CASOS = [
    { marca: 'Blocks LATAM', slug: 'blocks-latam', escuela: 'conquer-blocks', storageKey: 'form_variant_cb_latam', control: '57', blanco: '58' },
    { marca: 'Blocks US', slug: 'blocks-us', escuela: 'conquer-blocks', region: 'us', storageKey: 'form_variant_cb_us', control: '59', blanco: '60' },
    { marca: 'Finance LATAM', slug: 'finance-latam', escuela: 'conquer-finance', storageKey: 'form_variant_cf_latam', control: '61', blanco: '62' },
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

  it('un funnel sin experimento de fondo (Blocks EU) conserva el papel', () => {
    const { container } = montar({ slug: 'blocks-eu', escuela: 'conquer-blocks', region: 'eu' })
    expect(fondoDe(container).clases).toContain('bg-cb-bg')
  })

  it('la variante del vídeo no afecta al fondo de la landing', () => {
    // Se fijan LAS DOS variantes: si solo se fijara la del vídeo, la de la
    // landing se sortearía al montar y el test saldría blanco la mitad de las
    // veces (era flaky así). Con la de la landing en control, lo único que
    // puede mover el fondo es la del vídeo — y no debe.
    localStorage.setItem('form_variant_cb_latam', '57')
    const { container } = montar({
      slug: 'blocks-latam', escuela: 'conquer-blocks',
      storageKey: 'form_variant_video_cb_latam', variante: '4',
    })
    expect(fondoDe(container).clases).toContain('bg-cb-bg')
  })
})
