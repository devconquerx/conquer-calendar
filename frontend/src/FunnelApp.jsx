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
   Todas las etapas comparten bundle, TrackingProvider y query string (el
   prefill + tracking viajan por la URL igual que en el flujo multipágina). */
export default function FunnelApp({ slug, escuela, region, program, formConfig, videoEnabled }) {
  const { stage } = useRouter()
  const school = { slug: escuela }

  // El favicon depende de la escuela (no de la etapa): se aplica una vez para
  // landing, vídeo, stepform y confirmación.
  useEffect(() => {
    applyFavicon(getTheme(escuela, slug).favicon)
  }, [escuela, slug])

  // En la landing, precargamos en segundo plano los chunks de las etapas
  // siguientes para que el salto a vídeo/stepform sea instantáneo. Lo
  // disparamos con el primer gesto del usuario (o tras unos segundos como
  // respaldo), ya superado el LCP, para no competir con la carga inicial.
  useEffect(() => {
    if (stage !== 'landing') return
    let done = false
    const events = ['pointerdown', 'keydown', 'touchstart']
    const cleanup = () => {
      events.forEach((e) => window.removeEventListener(e, prefetch))
      clearTimeout(timer)
    }
    const prefetch = () => {
      if (done) return
      done = true
      cleanup()
      import('./Funnel')
      if (videoEnabled) import('./pages/VideoPage')
    }
    const timer = setTimeout(prefetch, 5000)
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

  const video = formConfig?.video || {}
  return (
    <Suspense fallback={stageFallback}>
      {stage === 'video' ? (
        <VideoPage
          school={school}
          region={region}
          formConfig={formConfig}
          videoUrls={video.videoUrls || []}
          buttonPercent={video.buttonPercent || 75}
        />
      ) : stage === 'confirmation' ? (
        <Confirmation escuela={escuela} slug={slug} />
      ) : (
        <Funnel slug={slug} escuela={escuela} formConfig={formConfig} />
      )}
    </Suspense>
  )
}
