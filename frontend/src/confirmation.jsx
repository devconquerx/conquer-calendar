import './lib/sentry'
import React from 'react'
import { createRoot } from 'react-dom/client'
import Confirmation from './components/Confirmation'
import TrackingProvider from './components/tracking/TrackingProvider'
import './funnel.css'

const container = document.getElementById('confirmation-root')
const escuela = container.dataset.escuela || ''
const slug = container.dataset.slug || ''

createRoot(container).render(
  <TrackingProvider>
    <Confirmation escuela={escuela} slug={slug} />
  </TrackingProvider>
)
