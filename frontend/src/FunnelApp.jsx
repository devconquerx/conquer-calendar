import { useRouter } from './lib/router'
import Landing from './pages/Landing'
import VideoPage from './pages/VideoPage'
import Funnel from './Funnel'
import Confirmation from './components/Confirmation'

/* Shell de la SPA del funnel: renderiza la etapa activa según el router.
   Todas las etapas comparten bundle, TrackingProvider y query string (el
   prefill + tracking viajan por la URL igual que en el flujo multipágina). */
export default function FunnelApp({ slug, escuela, region, program, formConfig, videoEnabled }) {
  const { stage } = useRouter()
  const school = { slug: escuela }

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
