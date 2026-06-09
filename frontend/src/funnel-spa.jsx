import './lib/sentry'
import React from 'react'
import { createRoot } from 'react-dom/client'
import FunnelApp from './FunnelApp'
import FunnelRouter from './lib/router'
import TrackingProvider from './components/tracking/TrackingProvider'
import './funnel.css'

/* Entry único del funnel SPA. El backend sirve este mismo shell en las cuatro
   etapas (landing, video, stepform, confirmación) indicando en data-stage cuál
   renderizar; la navegación entre ellas es client-side (pushState). */

const container = document.getElementById('funnel-root')
const d = container.dataset

// FunnelForm.config (landing/welcome/video/...) embebido por el backend.
let formConfig = {}
try {
  const el = document.getElementById('funnel-config')
  if (el) formConfig = JSON.parse(el.textContent)
} catch (e) {
  console.error('[Funnel] No se pudo parsear la config', e)
}

// URLs canónicas de cada etapa (incluyen el base path, p.ej. /preview).
const urls = {
  landing: d.landingUrl || '',
  video: d.videoUrl || '',
  stepform: d.stepformUrl || '',
  confirmation: d.confirmationUrl || '',
}

createRoot(container).render(
  <TrackingProvider>
    <FunnelRouter initialStage={d.stage || 'landing'} urls={urls}>
      <FunnelApp
        slug={d.slug || ''}
        escuela={d.escuela || ''}
        region={d.region || ''}
        program={d.program || ''}
        formConfig={formConfig}
        videoEnabled={d.videoEnabled === '1'}
      />
    </FunnelRouter>
  </TrackingProvider>
)
