import './lib/sentry'
import React from 'react'
import { createRoot } from 'react-dom/client'
import Funnel from './Funnel'
import TrackingProvider from './components/tracking/TrackingProvider'

const container = document.getElementById('funnel-root')
const slug = container.dataset.slug
const csrf = container.dataset.csrf
const escuela = container.dataset.escuela || ''
const confirmationUrl = container.dataset.confirmationUrl || ''

createRoot(container).render(
  <TrackingProvider>
    <Funnel slug={slug} csrf={csrf} escuela={escuela} confirmationUrl={confirmationUrl} />
  </TrackingProvider>
)
