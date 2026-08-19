import { describe, expect, it, vi } from 'vitest'
import VideoPage from '../../src/pages/VideoPage'
import { logosVisibles, renderConFunnel } from './helpers'

vi.mock('../../src/api', () => ({ sendVideoProgressToBackend: vi.fn() }))
vi.mock('../../src/components/vsl/VideoPlayer', () => ({ default: () => <div data-testid="player" /> }))

const CONFIG = { video: { videoUrls: ['https://x.test/v.mp4'], buttonPercent: 75 } }

const montar = ({ slug, escuela, variante, storageKey }) =>
  renderConFunnel(
    <VideoPage school={{ slug: escuela }} region="latam" formConfig={CONFIG} funnelSlug={slug} search="" />,
    { escuela, slug, variante, storageKey }
  )

/* A/B del logo del footer (Blocks EU/LATAM/US y Finance EU/LATAM). Este test
   renderiza la página entera: cualquier variable fuera de alcance o acceso a
   undefined revienta aquí, que es como se coló el fallo del 19/08. */
describe('página de vídeo — A/B del logo del footer', () => {
  const CASOS = [
    { marca: 'Blocks LATAM', slug: 'blocks-latam', escuela: 'conquer-blocks', storageKey: 'form_variant_video_cb_latam', control: '3', sinLogo: '4' },
    { marca: 'Blocks EU', slug: 'blocks-eu', escuela: 'conquer-blocks', storageKey: 'form_variant_video_cb_eu', control: '1', sinLogo: '2' },
    { marca: 'Blocks US', slug: 'blocks-us', escuela: 'conquer-blocks', storageKey: 'form_variant_video_cb_us', control: '5', sinLogo: '6' },
    { marca: 'Finance EU', slug: 'finance-eu', escuela: 'conquer-finance', storageKey: 'form_variant_video_cf_eu', control: '7', sinLogo: '8' },
    { marca: 'Finance LATAM', slug: 'finance-latam', escuela: 'conquer-finance', storageKey: 'form_variant_video_cf_latam', control: '9', sinLogo: '10' },
  ]

  for (const c of CASOS) {
    it(`${c.marca}: la variante de control muestra el logo`, () => {
      const { container } = montar({ ...c, variante: c.control })
      const footer = container.querySelector('footer')
      expect(footer).toBeTruthy()
      expect(logosVisibles(footer).length).toBeGreaterThan(0)
    })

    it(`${c.marca}: la variante de test lo oculta y conserva la franja y los píxeles`, () => {
      const { container } = montar({ ...c, variante: c.sinLogo })
      const footer = container.querySelector('footer')
      expect(footer).toBeTruthy()
      expect(logosVisibles(footer)).toHaveLength(0)
      // Los decorativos siguen ahí: solo se va el logo, no el footer.
      expect(footer.querySelectorAll('img[aria-hidden="true"]').length).toBeGreaterThan(0)
    })
  }

  it('un funnel sin experimento renderiza con logo y no reserva clave en localStorage', () => {
    const { container } = montar({ slug: 'languages-latam', escuela: 'conquer-languages' })
    expect(logosVisibles(container.querySelector('footer')).length).toBeGreaterThan(0)
    expect(Object.keys(localStorage).filter((k) => k.startsWith('form_variant_video'))).toHaveLength(0)
  })

  it('sin funnelSlug (montaje fuera del shell) no revienta', () => {
    expect(() =>
      renderConFunnel(<VideoPage school={{ slug: 'conquer-blocks' }} region="latam" formConfig={CONFIG} search="" />)
    ).not.toThrow()
  })
})
