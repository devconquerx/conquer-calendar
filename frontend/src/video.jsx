import './lib/sentry'
import React from 'react'
import { createRoot } from 'react-dom/client'
import VideoPage from './pages/VideoPage'
import TrackingProvider from './components/tracking/TrackingProvider'
import './funnel.css'

const container = document.getElementById('video-root')
const escuela = container.dataset.escuela || ''
const region = container.dataset.region || ''
const nextUrl = container.dataset.nextUrl || ''

// Config del video (videoUrls + buttonPercent) y contenido de la landing viajan
// como JSON embebido por el backend (FunnelForm.config).
let formConfig = {}
try {
  const el = document.getElementById('video-config')
  if (el) formConfig = JSON.parse(el.textContent)
} catch (e) {
  console.error('[Video] No se pudo parsear la config', e)
}

const video = formConfig?.video || {}
const school = { slug: escuela }

createRoot(container).render(
  <TrackingProvider>
    <VideoPage
      school={school}
      region={region}
      formConfig={formConfig}
      videoUrls={video.videoUrls || []}
      buttonPercent={video.buttonPercent || 75}
      nextUrl={nextUrl}
    />
  </TrackingProvider>
)
