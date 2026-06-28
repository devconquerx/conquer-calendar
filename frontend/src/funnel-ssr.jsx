import { renderToString } from 'react-dom/server'
import FunnelRoot from './app/FunnelRoot'
import Landing from './pages/Landing'
import VideoPage from './pages/VideoPage'
import Funnel from './Funnel'
import Confirmation from './components/Confirmation'

/* Entry de SSR. El servicio Node llama a `render(props)` con el payload que
   Django ya calcula (stage, funnel_config, escuela, region, program, urls,
   search). Importa las etapas de forma ESTÁTICA (no lazy) para poder
   serializarlas síncronamente con renderToString; el componente de la etapa
   pedida se pasa como `initialStageComponent`. No toca el DOM. */
const STAGE_COMPONENTS = {
  landing: Landing,
  video: VideoPage,
  stepform: Funnel,
  confirmation: Confirmation,
}

export function render(props = {}) {
  const stage = props.stage || 'landing'
  const initialStageComponent = STAGE_COMPONENTS[stage] || Landing
  return renderToString(
    <FunnelRoot {...props} stage={stage} initialStageComponent={initialStageComponent} />
  )
}
