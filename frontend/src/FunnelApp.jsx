import { useEffect, lazy, Suspense } from 'react'
import { useRouter } from './lib/router'
import { getTheme } from './themes'
import Landing from './pages/Landing'
import Spinner from './components/shared/Spinner'

/* Etapas posteriores a la landing: se cargan bajo demanda (code-splitting) para
   que la landing —la ruta crítica del LCP— no arrastre en su bundle el
   reproductor de vídeo (Plyr), el motor de formularios ni el widget de
   calendario, que ahí no se usan. Cada una viaja en su propio chunk. */
const VideoPage = lazy(() => import('./pages/VideoPage'))
const Funnel = lazy(() => import('./Funnel'))
const Confirmation = lazy(() => import('./components/Confirmation'))

const stageFallback = (
  <div className="flex min-h-screen items-center justify-center">
    <Spinner className="w-8 h-8" />
  </div>
)

/* Aplica el favicon del tema (si lo define) a <head>. El shell del funnel no
   trae <link rel="icon">, así que solo las escuelas con favicon propio —hoy
   Conquer Legal— lo reciben; el resto conserva el favicon por defecto.
   Reemplaza el link existente si lo hubiera (p.ej. el genérico del backend). */
function applyFavicon(favicon) {
  if (!favicon) return
  let link = document.querySelector("link[rel~='icon']")
  if (!link) {
    link = document.createElement('link')
    link.rel = 'icon'
    document.head.appendChild(link)
  }
  link.type = 'image/png'
  link.href = favicon
}

/* Shell de la SPA del funnel: renderiza la etapa activa según el router.
   Todas las etapas comparten TrackingProvider y query string (el prefill +
   tracking viajan por la URL igual que en el flujo multipágina).

   SSR: la etapa inicial (la que pidió la URL) se renderiza con un componente
   NO-lazy (`initialStageComponent`) y SIN <Suspense>, para que `renderToString`
   la serialice de verdad y el cliente la hidrate igual. Las etapas alcanzadas
   por navegación client-side siguen siendo lazy + Suspense (un spinner ahí es
   aceptable y no hay HTML del servidor que igualar). */
export default function FunnelApp({ slug, escuela, region, program, formConfig, videoEnabled, search, initialStage, initialStageComponent }) {
  const { stage } = useRouter()
  const school = { slug: escuela }

  // El favicon depende de la escuela (no de la etapa): se aplica una vez para
  // landing, vídeo, stepform y confirmación.
  useEffect(() => {
    applyFavicon(getTheme(escuela, slug).favicon)
  }, [escuela, slug])

  // En la landing, precargamos los chunks de las etapas siguientes al primer
  // gesto del usuario (hover/tap/tecla) para que el salto a vídeo/stepform sea
  // instantáneo. Solo con interacción: así no compite con la carga inicial ni
  // se cuela en la medición de performance (que no interactúa con la página).
  useEffect(() => {
    if (stage !== 'landing') return
    let done = false
    const events = ['pointerdown', 'keydown', 'touchstart']
    const cleanup = () => events.forEach((e) => window.removeEventListener(e, prefetch))
    const prefetch = () => {
      if (done) return
      done = true
      cleanup()
      import('./Funnel')
      if (videoEnabled) import('./pages/VideoPage')
    }
    events.forEach((e) => window.addEventListener(e, prefetch, { passive: true }))
    return cleanup
  }, [stage, videoEnabled])

  if (stage === 'landing') {
    return (
      <Landing
        school={school}
        program={program}
        region={region}
        formConfig={formConfig}
        funnelSlug={slug}
        videoEnabled={videoEnabled}
      />
    )
  }

  // Renderiza la etapa no-landing con el componente dado (lazy o no), con sus
  // props correctas. Solo una etapa se renderiza a la vez.
  const video = formConfig?.video || {}
  const renderStage = (Comp) => {
    if (stage === 'video') {
      return (
        <Comp
          school={school}
          region={region}
          formConfig={formConfig}
          videoUrls={video.videoUrls || []}
          buttonPercent={video.buttonPercent || 75}
          search={search}
        />
      )
    }
    if (stage === 'confirmation') {
      return <Comp escuela={escuela} slug={slug} />
    }
    return <Comp slug={slug} escuela={escuela} formConfig={formConfig} search={search} />
  }

  // Etapa SSR'd inicial → componente no-lazy, render síncrono sin Suspense.
  if (stage === initialStage && initialStageComponent) {
    return renderStage(initialStageComponent)
  }

  // Etapa por navegación client-side → lazy + Suspense.
  const Lazy = stage === 'video' ? VideoPage : stage === 'confirmation' ? Confirmation : Funnel
  return <Suspense fallback={stageFallback}>{renderStage(Lazy)}</Suspense>
}
