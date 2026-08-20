import FunnelApp from '../FunnelApp'
import ErrorBoundary from '../components/ErrorBoundary'
import FunnelRouter from '../lib/router'
import TrackingProvider from '../components/tracking/TrackingProvider'
import FormVariantProvider from '../lib/formVariantContext'
import { getTheme } from '../themes'

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
    /* Envuelve TODO, incluido el proveedor de tracking: un fallo ahí dentro
       dejaba la página en blanco, que para una landing de pago es perder al
       visitante entero. */
    <ErrorBoundary>
      <TrackingProvider>
        {/* La variante A/B se resuelve una vez para TODO el funnel (aquí, por
            encima del router): la consumen tanto el form de la landing como el
            tema de cada etapa. */}
        <FormVariantProvider
          themeId={getTheme(escuela, slug).id}
          region={region || ''}
          funnelSlug={slug || ''}
        >
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
        </FormVariantProvider>
      </TrackingProvider>
    </ErrorBoundary>
  )
}
