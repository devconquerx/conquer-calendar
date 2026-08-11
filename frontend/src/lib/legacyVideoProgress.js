import * as Sentry from '@sentry/react'

/**
 * Réplica de `sendPercentageOfVideoViewed` de conquerx-funnels-new (idéntico
 * en cf-video-page.js / cb-video-page.js / cl-video-page.js): un sistema de
 * tracking de vídeo PARALELO al del CRM moderno (que va vía
 * `/f/api/video-progress/` → backend → `crm.conquerx.com` con hitos 25/50/75/
 * 100 y campo genérico por marca `vsl_percent_cf`). Este otro pega
 * directamente desde el navegador, sin autenticación, a un endpoint PHP
 * legacy — cada 10% (no cada 25) — con una clave por MARCA+REGIÓN, no
 * genérica por marca.
 *
 * Nunca decidas usar este archivo como sustituto del envío moderno: son dos
 * sistemas independientes, ambos activos en el viejo, así que aquí también
 * conviven — sendVideoProgressToBackend (moderno) sigue llamándose aparte.
 */

const LEGACY_VIDEO_PROGRESS_ENDPOINT = 'https://crm-test.conquerx.com/video-progress-tracker.php'

// Las 9 claves que el viejo manda SIEMPRE en null (cb/cf/cl × eu/latam/us),
// tal cual el objeto `vslPercents` de sendPercentageOfVideoViewed — el
// endpoint PHP legacy espera este shape exacto, se use la marca que se use.
const LEGACY_VSL_NULL_PAYLOAD = {
  vsl_percent_cb_eu: null,
  vsl_percent_cb_latam: null,
  vsl_percent_cb_us: null,
  vsl_percent_cf_eu: null,
  vsl_percent_cf_latam: null,
  vsl_percent_cf_us: null,
  vsl_percent_cl_eu: null,
  vsl_percent_cl_latam: null,
  vsl_percent_cl_us: null,
}

// slug de escuela (FunnelForm.escuela) → código de marca corto del viejo.
const BRAND_CODE_POR_ESCUELA = {
  'conquer-finance': 'cf',
  conquerfinance: 'cf',
  // Blocks y Legal usan el MISMO mecanismo en el viejo (cb-video-page.js /
  // cl-video-page.js, mismo endpoint, mismas 9 claves) pero con casos extra
  // (`vsl_percent_cb_eu_2` del segundo experimento EU de Blocks,
  // `vsl_percent_cl_ge` de Legal en 2 rutas) que no calzan 1:1 con el patrón
  // "marca_región" de abajo. Blocks/Legal YA están desplegados en producción
  // — no se activan aquí hasta decidir con el usuario si sumar esa llamada
  // de red nueva a un endpoint legacy les afecta. Activar es solo añadir sus
  // slugs aquí + las 3 combinaciones estándar (eu/latam/us) que sí son
  // directas; los casos `_eu_2`/`_ge` requieren investigar qué ruta dispara cada uno.
}

/** Sólo las combinaciones marca+región verificadas contra el viejo. */
const LEGACY_VSL_KEY = {
  cf: {
    eu: 'vsl_percent_cf_eu',
    latam: 'vsl_percent_cf_latam',
    us: 'vsl_percent_cf_us',
  },
}

/**
 * Dispara el POST legacy si hay mapeo conocido para esta escuela+región; si
 * no (marca no migrada a este sistema, o región no contemplada), no-op
 * silencioso — igual de inocuo que no tener el <script> viejo cargado.
 */
export function reportLegacyVideoProgress({ email, percent, schoolSlug, region }) {
  if (!email || !percent) return

  const brand = BRAND_CODE_POR_ESCUELA[String(schoolSlug || '').toLowerCase()]
  const key = brand && LEGACY_VSL_KEY[brand]?.[String(region || '').toLowerCase()]
  if (!key) return

  fetch(LEGACY_VIDEO_PROGRESS_ENDPOINT, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      email,
      ...LEGACY_VSL_NULL_PAYLOAD,
      [key]: percent,
    }),
  }).catch((err) => {
    console.error('[LegacyVideoProgress] Error sending video progress:', err)
    Sentry.captureException(err, { tags: { action: 'reportLegacyVideoProgress' } })
  })
}
