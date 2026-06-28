import FunnelApp from '../FunnelApp'
import FunnelRouter from '../lib/router'
import TrackingProvider from '../components/tracking/TrackingProvider'

/* Árbol compartido por el cliente (hydrate/createRoot) y el servidor (SSR).
   NO debe tocar el DOM a nivel de módulo: todas las lecturas de window/document
   viven en el bootstrap cliente (funnel-spa.jsx) o en efectos. Las props llegan
   ya resueltas (el cliente las saca de los data-* + funnel-config; el servidor,
   del payload que envía Django). */
export default function FunnelRoot({
  stage,
  slug,
  escuela,
  region,
  program,
  formConfig,
  videoEnabled,
  urls,
  search,
  initialStageComponent,
}) {
  const initialStage = stage || 'landing'
  return (
    <TrackingProvider>
      <FunnelRouter initialStage={initialStage} urls={urls}>
        <FunnelApp
          slug={slug || ''}
          escuela={escuela || ''}
          region={region || ''}
          program={program || ''}
          formConfig={formConfig}
          videoEnabled={videoEnabled}
          search={search}
          initialStage={initialStage}
          initialStageComponent={initialStageComponent}
        />
      </FunnelRouter>
    </TrackingProvider>
  )
}
