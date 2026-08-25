import { beforeEach, describe, expect, it, vi } from 'vitest'
import { renderConFunnel } from './helpers'
import VideoPage from '../../src/pages/VideoPage'
import Confirmation from '../../src/components/Confirmation'
import Calendar from '../../src/components/Calendar'
import Funnel from '../../src/Funnel'
import { getTheme } from '../../src/themes'
import { toWhiteBackground } from '../../src/themes/whiteBackground'

// Igual que el resto de tests de la página de vídeo: el reproductor real
// (plyr) pide APIs de navegador que jsdom no trae, y aquí solo miramos fondos.
vi.mock('../../src/api', () => ({ sendVideoProgressToBackend: vi.fn(), postReservar: vi.fn() }))
vi.mock('../../src/components/vsl/VideoPlayer', () => ({ default: () => <div data-testid="player" /> }))

/* El A/B de fondo blanco cubre el funnel ENTERO, no solo la landing: cada etapa
   resuelve su propio tema, así que si alguna se olvida de pasarlo por
   `useVariantTheme` el visitante ve papel en mitad del recorrido. Estos tests
   recorren las etapas que pintan papel y fijan que las dos ramas se distinguen.

   La clave del test: `storageKey` + `variante` dejan la rama ya asignada en
   localStorage antes de montar, igual que un visitante que viene de la landing. */

const CLAVE = 'form_variant_cb_latam'
const PAPEL = '57'
const BLANCO = '58'

const configVideo = {
  video: { title: 'Título', subtitle: 'Vídeo', videoUrls: ['https://example.com/v.mp4'], buttonPercent: 75 },
}

function montarVideo(variante) {
  return renderConFunnel(
    <VideoPage
      school={{ slug: 'conquer-blocks' }}
      region="latam"
      formConfig={configVideo}
      videoUrls={configVideo.video.videoUrls}
      buttonPercent={75}
      nextUrl="/agenda/fullstack/latam/"
      search=""
      funnelSlug="blocks-latam"
    />,
    { variante, storageKey: CLAVE }
  )
}

function montarConfirmacion(variante) {
  return renderConFunnel(
    <Confirmation escuela="conquer-blocks" slug="blocks-latam" />,
    { variante, storageKey: CLAVE }
  )
}

/* Une los estilos en línea de un nodo y sus descendientes: el papel se pinta
   con `background-image: url(...)`, así que buscar 'url(' basta para saber si
   queda textura en la etapa. */
function estilosDe(contenedor) {
  return [...contenedor.querySelectorAll('[style]')]
    .map((n) => n.getAttribute('style'))
    .join(' | ')
}

describe('A/B de fondo blanco en todo el funnel', () => {
  beforeEach(() => {
    localStorage.clear()
    vi.restoreAllMocks()
  })

  describe('página de vídeo', () => {
    it('con la variante de papel mantiene la textura', () => {
      const { container } = montarVideo(PAPEL)
      expect(estilosDe(container)).toContain('paperboard')
    })

    it('con la variante blanca no queda textura de papel', () => {
      const { container } = montarVideo(BLANCO)
      expect(estilosDe(container)).not.toContain('paperboard')
      // Y nunca una url rota: el bug sería `url(null)` al anular la textura.
      expect(estilosDe(container)).not.toContain('url(null)')
      expect(estilosDe(container)).not.toContain('url(undefined)')
    })

    it('con la variante blanca aclara el rasgado para que no haga escalón', () => {
      const { container } = montarVideo(BLANCO)
      const rasgados = [...container.querySelectorAll('img')].filter((i) => (i.getAttribute('src') || '').includes('torn'))
      expect(rasgados.length).toBeGreaterThan(0)
      for (const img of rasgados) expect(img.className).toContain('brightness-125')
    })

    it('con la variante de papel el rasgado se queda tal cual', () => {
      const { container } = montarVideo(PAPEL)
      const rasgados = [...container.querySelectorAll('img')].filter((i) => (i.getAttribute('src') || '').includes('torn'))
      for (const img of rasgados) expect(img.className).not.toContain('brightness-125')
    })
  })

  describe('confirmación', () => {
    it('con la variante de papel mantiene las secciones crema', () => {
      const { container } = montarConfirmacion(PAPEL)
      expect(container.innerHTML).toContain('bg-[#F5EDE3]')
    })

    it('con la variante blanca pinta las secciones en blanco', () => {
      const { container } = montarConfirmacion(BLANCO)
      expect(container.innerHTML).not.toContain('bg-[#F5EDE3]')
      expect(estilosDe(container)).not.toContain('url(null)')
    })
  })

  describe('stepform', () => {
    const CONFIG = {
      blocks: [
        { id: 'welcome', type: 'welcome', title: 'Hola' },
        { id: 'edad', type: 'multiple_choice', title: '¿Edad?', choices: [{ value: 'a', label: '25-34' }] },
      ],
      messages: {},
      theme: {},
    }

    const montarStepForm = (variante) => renderConFunnel(
      <Funnel slug="blocks-latam" escuela="conquer-blocks" formConfig={CONFIG} search="" />,
      { variante, storageKey: CLAVE }
    )

    it('con la variante blanca el wrapper va en blanco y sin textura', () => {
      const { container } = montarStepForm(BLANCO)
      const wrap = container.querySelector('.funnel-wrap')
      expect(wrap.getAttribute('style')).toContain('rgb(255, 255, 255)')
      expect(wrap.getAttribute('style')).not.toContain('paperboard')
      expect(estilosDe(container)).not.toContain('url(null)')
    })

    it('con la variante de papel el wrapper conserva la textura', () => {
      const { container } = montarStepForm(PAPEL)
      expect(container.querySelector('.funnel-wrap').getAttribute('style')).toContain('paperboard')
    })
  })

  describe('calendario', () => {
    // El calendario pinta su papel desde funnel.css, así que lo que hay que
    // comprobar es la clase que apaga esa textura (la misma que ya usa Finance).
    const props = {
      slots: [],
      onSelect: () => {},
      loading: false,
    }

    it('con la variante blanca usa el wrapper plano', () => {
      const { container } = renderConFunnel(
        <Calendar {...props} theme={toWhiteBackground(getTheme('conquer-blocks'))} />,
        { variante: BLANCO, storageKey: CLAVE }
      )
      expect(container.querySelector('.bk-wrapper').className).toContain('bk-wrapper--plain')
    })

    it('con la variante de papel conserva el wrapper con textura', () => {
      const { container } = renderConFunnel(
        <Calendar {...props} theme={getTheme('conquer-blocks')} />,
        { variante: PAPEL, storageKey: CLAVE }
      )
      expect(container.querySelector('.bk-wrapper').className).not.toContain('bk-wrapper--plain')
    })
  })

  describe('funnels sin el experimento', () => {
    it('la página de vídeo de un funnel fuera del test se queda con su papel', () => {
      // languages-ge no corre el A/B: aunque la clave esté en localStorage no
      // debe aplicarse (el experimento se ancla al slug exacto).
      const { container } = renderConFunnel(
        <VideoPage
          school={{ slug: 'conquer-languages' }}
          region="ge"
          formConfig={configVideo}
          videoUrls={configVideo.video.videoUrls}
          buttonPercent={75}
          nextUrl="/ge/schedule"
          search=""
          funnelSlug="languages-ge"
        />,
        { variante: BLANCO, storageKey: CLAVE, escuela: 'conquer-languages', slug: 'languages-ge', region: 'ge' }
      )
      expect(estilosDe(container)).toContain('paperboard')
    })
  })
})
