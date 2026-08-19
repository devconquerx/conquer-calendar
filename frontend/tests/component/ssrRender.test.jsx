import { describe, expect, it } from 'vitest'
import { render } from '../../src/funnel-ssr'

/* Humo de render: pinta CADA etapa de CADA funnel con el entry de SSR, que es
   el árbol real de la app. No comprueba diseño — comprueba que ninguna pantalla
   revienta al ejecutarse.
   Existe por el fallo del 19/08: `hideFooterLogo` estaba declarado en un
   componente y usado en otro. El build pasaba (es válido sintácticamente) y la
   página de vídeo caía en producción al montar. Un render lo caza en 20 ms. */

const FUNNELS = [
  { slug: 'blocks-latam', escuela: 'conquer-blocks', region: 'latam' },
  { slug: 'blocks-eu', escuela: 'conquer-blocks', region: 'eu' },
  { slug: 'blocks-eu-2', escuela: 'conquer-blocks', region: 'eu' },
  { slug: 'blocks-us', escuela: 'conquer-blocks', region: 'us' },
  { slug: 'finance-latam', escuela: 'conquer-finance', region: 'latam' },
  { slug: 'finance-eu', escuela: 'conquer-finance', region: 'eu' },
  { slug: 'finance-us', escuela: 'conquer-finance', region: 'us' },
  { slug: 'languages-latam', escuela: 'conquer-languages', region: 'latam' },
  { slug: 'languages-eu', escuela: 'conquer-languages', region: 'eu' },
  { slug: 'languages-us', escuela: 'conquer-languages', region: 'us' },
  { slug: 'languages-ge', escuela: 'conquer-languages', region: 'ge' },
  { slug: 'languages-kids-latam', escuela: 'conquer-languages-kids', region: 'latam' },
  { slug: 'legal-eu', escuela: 'conquer-legal', region: 'eu' },
  { slug: 'especializacion-latam', escuela: 'conquer-blocks-esp', region: 'latam' },
]

const ETAPAS = ['landing', 'video', 'stepform', 'confirmation']

const CONFIG = {
  landing: {
    title: 'Titular <strong>con negrita</strong>', subtitle: 'Vídeo gratis', description: 'desc',
    bullets: ['uno', 'dos', 'tres'], buttonText: 'Ver vídeo gratis',
    instructor: { name: 'Instructor', role: 'Rol', description: 'bio' }, disclaimer: '*aviso',
  },
  video: { videoUrls: ['https://x.test/v.mp4'], buttonPercent: 75 },
  blocks: [{ name: 'welcome-screen', id: 'welcome', attributes: { label: 'Bienvenido', buttonText: 'Comenzar' } }],
  q_order: [],
}

const URLS = { landing: '/l', video: '/v', stepform: '/s', confirmation: '/c' }

describe('render de todas las etapas de todos los funnels', () => {
  for (const f of FUNNELS) {
    for (const stage of ETAPAS) {
      it(`${f.slug} · ${stage}`, () => {
        const html = render({
          stage, slug: f.slug, escuela: f.escuela, region: f.region,
          program: 'fullstack', videoEnabled: true, search: '?name=Ana&email=a%40b.com',
          formConfig: CONFIG, urls: URLS,
        })
        expect(typeof html).toBe('string')
        expect(html.length).toBeGreaterThan(0)
      })
    }
  }

  it('aguanta una config vacía (funnel recién creado, sin contenido en BD)', () => {
    for (const stage of ETAPAS) {
      expect(() => render({
        stage, slug: 'blocks-latam', escuela: 'conquer-blocks', region: 'latam',
        formConfig: {}, urls: URLS, search: '',
      })).not.toThrow()
    }
  })
})
