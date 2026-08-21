/**
 * Sentry (frontend) — réplica de conquerx-funnels-django.
 * Se inicializa solo si VITE_SENTRY_DSN está definido en build time
 * (se inyecta como build arg en la etapa Node del Dockerfile de producción).
 */
import * as Sentry from '@sentry/react'

/* Ruido de los navegadores embebidos de las apps (Instagram, TikTok), que es
   por donde entra buena parte del tráfico de pago. Esas apps inyectan SU PROPIO
   JavaScript en la página —loggers de rendimiento, puentes con el código
   nativo— y cuando ese código falla, la instrumentación automática del SDK
   (que envuelve addEventListener y setTimeout) lo captura y lo reporta como si
   fuera nuestro. Eran 589 eventos, casi la mitad de todo lo abierto:

   - "Java object is gone": el logger de Instagram (iabjs://) hablando con el
     puente Java en beforeunload, cuando la app ya lo ha destruido.
   - "domInteractive": el logger de TikTok leyendo performance.timing en una
     página donde no existe.

   Ninguna de las dos APIs se usa en nuestro código, así que el filtro no puede
   tapar un fallo propio. Si algún día se instrumenta rendimiento en el funnel,
   hay que revisar esto. */
export const ERRORES_DE_NAVEGADORES_EMBEBIDOS = [
  /Java object is gone/,
  /domInteractive/,
]

/* Scripts inyectados por la app anfitriona: nada que venga de ahí es nuestro. */
export const URLS_DE_TERCEROS = [/^iabjs:\/\//]

if (typeof window !== 'undefined' && import.meta.env.VITE_SENTRY_DSN) {
  Sentry.init({
    dsn: import.meta.env.VITE_SENTRY_DSN,
    environment: import.meta.env.MODE,
    integrations: [
      Sentry.browserTracingIntegration(),
    ],
    tracesSampleRate: 0.2,
    ignoreErrors: ERRORES_DE_NAVEGADORES_EMBEBIDOS,
    denyUrls: URLS_DE_TERCEROS,
  })
}
