import React from 'react'
import { createRoot } from 'react-dom/client'
import Landing from './pages/Landing'
import TrackingProvider from './components/tracking/TrackingProvider'
import './funnel.css'

const container = document.getElementById('landing-root')
const escuela = container.dataset.escuela || ''
const slug = container.dataset.slug || ''
const region = container.dataset.region || ''
const program = container.dataset.program || ''
const nextUrl = container.dataset.nextUrl || ''

// El contenido de la landing (landing/welcome/instructor/bullets/key) viaja como
// JSON embebido por el backend (FunnelForm.config).
let formConfig = {}
try {
  const el = document.getElementById('landing-config')
  if (el) formConfig = JSON.parse(el.textContent)
} catch (e) {
  console.error('[Landing] No se pudo parsear la config', e)
}

const school = { slug: escuela }

createRoot(container).render(
  <TrackingProvider>
    <Landing
      school={school}
      program={program}
      region={region}
      formConfig={formConfig}
      nextUrl={nextUrl}
      funnelSlug={slug}
    />
  </TrackingProvider>
)
