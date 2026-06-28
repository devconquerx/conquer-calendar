import './lib/sentry'
import { createRoot, hydrateRoot } from 'react-dom/client'
import FunnelRoot from './app/FunnelRoot'
import './funnel.css'

/* Bootstrap cliente del funnel SPA. AQUÍ viven todas las lecturas del DOM
   (data-*, funnel-config, window.location). Si el #funnel-root ya trae HTML del
   servidor (SSR) hidratamos; si está vacío (flag SSR off, o el render del Node
   falló) hacemos createRoot → CSR idéntico al de hoy. */

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

const stage = d.stage || 'landing'

const props = {
  stage,
  slug: d.slug || '',
  escuela: d.escuela || '',
  region: d.region || '',
  program: d.program || '',
  formConfig,
  videoEnabled: d.videoEnabled === '1',
  urls,
  // Mismo query string que usó el servidor para el SSR → prefill consistente.
  search: window.location.search,
}

// Las etapas no-landing son lazy. Para hidratar/renderizar la etapa inicial de
// forma SÍNCRONA (y que coincida con el HTML del servidor), cargamos su chunk
// ANTES de montar y lo pasamos como initialStageComponent.
const STAGE_LOADERS = {
  video: () => import('./pages/VideoPage'),
  stepform: () => import('./Funnel'),
  confirmation: () => import('./components/Confirmation'),
}

async function boot() {
  let initialStageComponent
  const loader = STAGE_LOADERS[stage]
  if (loader) {
    try {
      const mod = await loader()
      initialStageComponent = mod.default
    } catch (e) {
      console.error('[Funnel] No se pudo cargar la etapa inicial', stage, e)
    }
  }

  const tree = <FunnelRoot {...props} initialStageComponent={initialStageComponent} />

  if (container.firstElementChild) {
    hydrateRoot(container, tree)
  } else {
    createRoot(container).render(tree)
  }
}

boot()
