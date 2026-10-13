import { describe, expect, it, vi } from 'vitest'
import VideoPage from '../../src/pages/VideoPage'
import { logosVisibles, renderConFunnel } from './helpers'

vi.mock('../../src/api', () => ({ sendVideoProgressToBackend: vi.fn() }))
vi.mock('../../src/components/vsl/VideoPlayer', () => ({
  default: ({ videoUrls }) => <div data-testid="player" data-src={videoUrls?.[0] || ''} />,
}))

const CONFIG = { video: { videoUrls: ['https://x.test/v.mp4'], buttonPercent: 75 } }

const montar = ({ slug, escuela, variante, storageKey }) =>
  renderConFunnel(
    <VideoPage school={{ slug: escuela }} region="latam" formConfig={CONFIG} funnelSlug={slug} search="" />,
    { escuela, slug, variante, storageKey }
  )

/* A/B del footer de la página de vídeo (Blocks EU/LATAM/US y Finance EU/LATAM):
   la variante de test quita el footer ENTERO —rasgado inferior, franja de papel
   y logo— para que la zona oscura del vídeo llegue hasta el final.
   Renderiza la página entera: cualquier variable fuera de alcance o acceso a
   undefined revienta aquí, que es como se coló el fallo del 19/08. */
describe('página de vídeo — A/B del footer', () => {
  const CASOS = [
    { marca: 'Blocks LATAM', slug: 'blocks-latam', escuela: 'conquer-blocks', storageKey: 'form_variant_video_cb_latam', control: '3', sinLogo: '4' },
    { marca: 'Blocks EU', slug: 'blocks-eu', escuela: 'conquer-blocks', storageKey: 'form_variant_video_cb_eu', control: '1', sinLogo: '2' },
    { marca: 'Blocks US', slug: 'blocks-us', escuela: 'conquer-blocks', storageKey: 'form_variant_video_cb_us', control: '5', sinLogo: '6' },
    { marca: 'Finance EU', slug: 'finance-eu', escuela: 'conquer-finance', storageKey: 'form_variant_video_cf_eu', control: '7', sinLogo: '8' },
    { marca: 'Finance LATAM', slug: 'finance-latam', escuela: 'conquer-finance', storageKey: 'form_variant_video_cf_latam', control: '9', sinLogo: '10' },
    { marca: 'Languages LATAM', slug: 'languages-latam', escuela: 'conquer-languages', storageKey: 'form_variant_video_cl_latam', control: '11', sinLogo: '12' },
    { marca: 'Languages EU', slug: 'languages-eu', escuela: 'conquer-languages', storageKey: 'form_variant_video_cl_eu', control: '13', sinLogo: '14' },
    { marca: 'Languages US', slug: 'languages-us', escuela: 'conquer-languages', storageKey: 'form_variant_video_cl_us', control: '15', sinLogo: '16' },
  ]

  for (const c of CASOS) {
    it(`${c.marca}: la variante de control muestra el logo`, () => {
      const { container } = montar({ ...c, variante: c.control })
      const footer = container.querySelector('footer')
      expect(footer).toBeTruthy()
      expect(logosVisibles(footer).length).toBeGreaterThan(0)
    })

    it(`${c.marca}: la variante de test quita el footer entero`, () => {
      const { container } = montar({ ...c, variante: c.sinLogo })
      expect(container.querySelector('footer')).toBeNull()
    })
  }

  it('un funnel sin experimento renderiza con logo y no reserva clave en localStorage', () => {
    const { container } = montar({ slug: 'languages-ge', escuela: 'conquer-languages' })
    expect(logosVisibles(container.querySelector('footer')).length).toBeGreaterThan(0)
    expect(Object.keys(localStorage).filter((k) => k.startsWith('form_variant_video'))).toHaveLength(0)
  })

  it('sin funnelSlug (montaje fuera del shell) no revienta', () => {
    expect(() =>
      renderConFunnel(<VideoPage school={{ slug: 'conquer-blocks' }} region="latam" formConfig={CONFIG} search="" />)
    ).not.toThrow()
  })
})

/* A/B de la VSL de Legal EU-2 (13/10/2026): 17 ve la larga de siempre y 18 la
   corta (`video.altVideoUrls`). Lo que se rompe si falla no se ve en la página:
   el visitante ve otro vídeo del que dice su código, y el test se lee al revés. */
describe('página de vídeo — A/B de la VSL de Legal EU-2', () => {
  const VSL = { video: { videoUrls: ['https://x.test/larga.mp4'], altVideoUrls: ['https://x.test/corta.mp4'], buttonPercent: 75 } }
  const montarLegal = (variante) => renderConFunnel(
    <VideoPage school={{ slug: 'conquer-legal' }} region="eu" formConfig={VSL} funnelSlug="legal-eu-2" search="" />,
    { escuela: 'conquer-legal', slug: 'legal-eu-2', variante, storageKey: 'form_variant_video_cg_eu_2' }
  )
  const fuente = (container) => container.querySelector('[data-testid="player"]')?.dataset.src

  it('17 (control) ve la VSL larga', () => {
    expect(fuente(montarLegal('17').container)).toBe('https://x.test/larga.mp4')
  })

  it('18 ve la VSL corta', () => {
    expect(fuente(montarLegal('18').container)).toBe('https://x.test/corta.mp4')
  })

  it('quien llega sin rama queda sorteado y ve el vídeo de su rama', () => {
    const { container } = montarLegal(undefined)
    const rama = localStorage.getItem('form_variant_video_cg_eu_2')
    expect(['17', '18']).toContain(rama)
    expect(fuente(container)).toBe(rama === '18' ? 'https://x.test/corta.mp4' : 'https://x.test/larga.mp4')
  })

  it('no toca el footer: las dos ramas lo conservan', () => {
    for (const v of ['17', '18']) {
      localStorage.clear()
      expect(montarLegal(v).container.querySelector('footer')).toBeTruthy()
    }
  })
})
