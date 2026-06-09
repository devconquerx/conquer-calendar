/**
 * Sentry (frontend) — réplica de conquerx-funnels-django.
 * Se inicializa solo si VITE_SENTRY_DSN está definido en build time
 * (se inyecta como build arg en la etapa Node del Dockerfile de producción).
 */
import * as Sentry from '@sentry/react'

if (import.meta.env.VITE_SENTRY_DSN) {
  Sentry.init({
    dsn: import.meta.env.VITE_SENTRY_DSN,
    environment: import.meta.env.MODE,
    integrations: [
      Sentry.browserTracingIntegration(),
    ],
    tracesSampleRate: 0.2,
  })
}
