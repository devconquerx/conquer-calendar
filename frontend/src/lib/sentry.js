/**
 * Sentry (frontend) — réplica de conquerx-funnels-django.
 * Se inicializa solo si VITE_SENTRY_DSN está definido en build time
 * (se inyecta como build arg en la etapa Node del Dockerfile de producción).
 */
import * as Sentry from '@sentry/react'

/* Ruido de los navegadores embebidos de las apps (Instagram, TikTok, Facebook,
   Samsung Internet), que es por donde entra buena parte del tráfico de pago.
   Esas apps inyectan SU PROPIO JavaScript en la página —loggers de rendimiento,
   puentes con el código nativo, barras de navegación— y cuando ese código
   falla, la instrumentación automática del SDK (que envuelve addEventListener
   y setTimeout) lo captura y lo reporta como si fuera nuestro.

   Cada símbolo de esta lista se comprobó con grep contra `frontend/src`: NINGUNO
   existe en nuestro código, así que el filtro no puede tapar un fallo propio. Si
   algún día se usa alguna de estas APIs, hay que revisar esto. */
export const ERRORES_DE_NAVEGADORES_EMBEBIDOS = [
  // Instagram: su logger hablando con el puente Java en beforeunload, cuando la
  // app ya lo ha destruido. También "Java bridge method invocation error".
  /Java object is gone/,
  /Java bridge method invocation error/,
  /Error invoking (postMessage|process)/,
  // TikTok: su logger leyendo performance.timing donde no existe.
  /domInteractive/,
  // Barras de navegación inyectadas (Samsung Internet y similares): funciones
  // globales que la app espera encontrar y que en nuestra página no existen.
  /\b(x|sw)browser\b/,
  /hideFooterLogo/,
  // Puente de la webview de iOS: lo usan las apps, nosotros no.
  /window\.webkit\.messageHandlers/,
  /iframeBridge/,
  // Wallets de cripto que se autoinyectan (MetaMask y compañía).
  /Failed to connect to MetaMask/,
  /reading 'M_ID'/,
]

/* Orígenes cuyo código NUNCA es nuestro. Si una pila pasa por aquí, el error lo
   tiró un tercero.

   OJO con `denyUrls`: filtra por el fichero del evento, y ahí sale SIEMPRE
   nuestro bundle, porque el SDK va compilado dentro y sus envoltorios de
   `fetch`/`setTimeout` son los que aparecen arriba y abajo de la pila. Por eso
   el descarte se hace en `beforeSend` mirando TODOS los frames. */
export const ORIGENES_DE_TERCEROS = [
  // Extensiones del navegador: reemplazan APIs nativas (p.ej. document.createEvent
  // sin su `this` → "Illegal invocation") y rompen scripts de terceros.
  /^(chrome|moz|safari|safari-web)-extension:\/\//,
  // Scripts que inyecta la app anfitriona.
  /^iabjs:\/\//,
  // Cookiebot y Google Tag Manager / GA4: su telemetría fallando (bloqueada,
  // sin red) no es un bug del funnel ni hay nada que arreglar en el código.
  /\/uc\.js(\?|$|:)/,
  /consent\.cookiebot\.com/,
  /\/gtag\/js/,
  /googletagmanager\.com/,
]

/** ¿La pila de este evento pasa por código de terceros? */
export function vieneDeUnTercero(evento) {
  const valores = evento?.exception?.values || []
  return valores.some((valor) =>
    (valor?.stacktrace?.frames || []).some((frame) =>
      ORIGENES_DE_TERCEROS.some((re) => re.test(frame?.filename || ''))
    )
  )
}

if (typeof window !== 'undefined' && import.meta.env.VITE_SENTRY_DSN) {
  Sentry.init({
    dsn: import.meta.env.VITE_SENTRY_DSN,
    environment: import.meta.env.MODE,
    integrations: [
      Sentry.browserTracingIntegration(),
    ],
    tracesSampleRate: 0.2,
    ignoreErrors: ERRORES_DE_NAVEGADORES_EMBEBIDOS,
    beforeSend: (evento) => (vieneDeUnTercero(evento) ? null : evento),
  })
}
