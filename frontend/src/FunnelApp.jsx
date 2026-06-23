import { useEffect } from 'react'
import { useRouter } from './lib/router'
import { getTheme } from './themes'
import Landing from './pages/Landing'
import VideoPage from './pages/VideoPage'
import Funnel from './Funnel'
import Confirmation from './components/Confirmation'

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

  if (stage === 'video') {
    const video = formConfig?.video || {}
    return (
      <VideoPage
        school={school}
        region={region}
        formConfig={formConfig}
        videoUrls={video.videoUrls || []}
        buttonPercent={video.buttonPercent || 75}
      />
    )
  }

  if (stage === 'confirmation') {
    return <Confirmation escuela={escuela} slug={slug} />
  }

  return <Funnel slug={slug} escuela={escuela} formConfig={formConfig} />
}
