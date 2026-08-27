/**
 * Asignación de variante A/B persistente por visitante — réplica del
 * mecanismo de conquerx-funnels-new (`consumeForcedFormVariant` +
 * `localStorage[storageKey]` + `Math.random()` al 50/50, por experimento).
 * Genérico: cualquier landing puede declarar el suyo por `storageKey`
 * (ej. Finance EU usa 'form_variant_cf', igual que el proyecto viejo, para
 * que la variante persista aunque el visitante navegue entre marcas/campañas
 * que compartan dominio).
 *
 * Solo debe llamarse client-side (usa localStorage/URL): en SSR o en el
 * primer render usar un valor por defecto y resolver en un efecto tras
 * montar, igual que el resto del código dependiente de localStorage/geo en
 * este proyecto (progressive enhancement, sin bloquear el render inicial).
 */
export function resolveFormVariant(experiment) {
  const { storageKey, variants } = experiment || {}
  if (typeof window === 'undefined' || !storageKey || !variants?.length) return null

  const url = new URL(window.location.href)
  const forced = url.searchParams.get('force_form_variant')
  if (forced && variants.includes(forced)) {
    try { localStorage.setItem(storageKey, forced) } catch (_) {}
    url.searchParams.delete('force_form_variant')
    window.history.replaceState({}, '', `${url.pathname}${url.search}${url.hash}`)
    return forced
  }

  let stored = null
  try { stored = localStorage.getItem(storageKey) } catch (_) {}
  if (stored && variants.includes(stored)) return stored

  const assigned = variants[Math.floor(Math.random() * variants.length)]
  try { localStorage.setItem(storageKey, assigned) } catch (_) {}
  return assigned
}

/** Lee la variante ya asignada SIN asignar ninguna. Para cuando otra etapa
    necesita el dato pero no debe meter al visitante en el experimento (p.ej. el
    StepForm, que adjunta la variante del vídeo a la prellamada: quien llega por
    link directo sin pasar por el vídeo no entra en el test). */
export function readFormVariant(experiment) {
  const { storageKey, variants } = experiment || {}
  if (typeof window === 'undefined' || !storageKey || !variants?.length) return null
  let stored = null
  try { stored = localStorage.getItem(storageKey) } catch (_) {}
  return stored && variants.includes(stored) ? stored : null
}

/* ── Experimentos A/B activos ─────────────────────────────────────────────
   Uno por landing/funnel, con su propio `storageKey` (así el split de cada
   experimento persiste aparte aunque las landings compartan dominio, igual
   que en conquerx-funnels-new). Cada entrada declara QUÉ cambia la variante
   de test; el resto del código pregunta por esas banderas y nunca por el
   número suelto:

   - `whatsappOptinVariant`  → variante que muestra el check "Envíame la
     repetición por WhatsApp" (que a su vez revela el campo de teléfono).
   - `alwaysPhoneVariant`    → variante con el campo de teléfono SIEMPRE
     visible y OBLIGATORIO, sin checkbox.
   - `whiteBackgroundVariant`→ variante que sustituye el fondo de papel
     (paperboard) de la LANDING por blanco (solo la landing; el resto de
     etapas del funnel no cambia).
   - `whatsappComplianceText` → el texto de consentimiento menciona WhatsApp en
     TODO el experimento (las dos variantes), no en una sola.

   `?force_form_variant=<código>` fuerza y persiste la variante (para QA),
   igual que en el funnel viejo.

   Todos se anclan al SLUG exacto del funnel, no a marca+región: hay funnels
   que comparten ambas cosas con otro y no deben heredar su experimento
   (`especializacion-eu` cuelga de la marca Blocks y de la región EU, pero es
   un funnel aparte). Los slugs están verificados contra la BD de producción. */
const FORM_VARIANT_EXPERIMENTS = [
  // Finance EU: 55 (checkbox, igual que Legal) / 56 (campo visible y obligatorio).
  {
    match: ({ funnelSlug }) => funnelSlug === 'finance-eu',
    storageKey: 'form_variant_cf',
    variants: ['55', '56'],
    whatsappOptinVariant: '55',
    alwaysPhoneVariant: '56',
    whatsappComplianceText: true,
  },
  // Finance LATAM (fi-latam, slug `finance-latam`): 61 (control: la landing tal
  // cual) / 62 (test: fondo blanco). Mismo test de diseño que Blocks LATAM.
  // Finance EU queda FUERA a propósito: su landing ya corre el A/B de
  // teléfono/WhatsApp (55/56) y `utm_form_variant` es un único campo por lead,
  // así que no puede llevar dos experimentos a la vez sin ambigüedad.
  {
    match: ({ funnelSlug }) => funnelSlug === 'finance-latam',
    storageKey: 'form_variant_cf_latam',
    themeId: 'conquerfinance',
    variants: ['61', '62'],
    whiteBackgroundVariant: '62',
  },
  // Blocks EU, segunda landing (cb-eu-2, slug `blocks-eu-2`): 71 (control) / 72
  // (fondo blanco). Experimento independiente del de la landing principal para
  // no mezclar splits.
  {
    match: ({ funnelSlug }) => funnelSlug === 'blocks-eu-2',
    storageKey: 'form_variant_cb_eu_2_fondo',
    themeId: 'conquerblocks',
    variants: ['71', '72'],
    whiteBackgroundVariant: '72',
  },
  // Blocks EU, landing principal (cb-eu, slug `blocks-eu`): 69 (control) / 70
  // (fondo blanco).
  //
  // Antes corría aquí el A/B del checkbox de WhatsApp (51/52 en esta landing y
  // 53/54 en la segunda). Se apagó el 27/08/2026 dejando GANADORA la rama CON
  // checkbox, que pasa a ser fija para todo el mundo vía `landing.whatsappOptin`
  // en la config de los dos funnels — no por experimento, así que el campo
  // `utm_form_variant` queda libre para este test de fondo.
  //
  // Los códigos son nuevos (69-72) en vez de reutilizar los viejos: 51-54 ya
  // significan «con/sin checkbox» en los leads históricos y en la pantalla de
  // distribución A/B del CRM, y reciclarlos mezclaría los dos experimentos en
  // la misma serie. Por el mismo motivo cambia la `storageKey`: quien tenga
  // guardado un 51-54 no arrastra rama al test nuevo.
  {
    match: ({ funnelSlug }) => funnelSlug === 'blocks-eu',
    storageKey: 'form_variant_cb_eu_fondo',
    themeId: 'conquerblocks',
    variants: ['69', '70'],
    whiteBackgroundVariant: '70',
  },
  // Blocks LATAM (cb-latam, slug `blocks-latam`): 57 (control: la landing tal
  // cual, con su fondo de papel) / 58 (test: la MISMA landing con el fondo en
  // blanco). El formulario no cambia entre las dos —es un test de diseño, no de
  // campos— y las etapas siguientes (vídeo, stepform, calendario y
  // confirmación) tampoco: el cambio se queda en la landing. Se ancla al slug
  // exacto para no alcanzar a `especializacion-latam`, que comparte marca y
  // región.
  {
    match: ({ funnelSlug }) => funnelSlug === 'blocks-latam',
    storageKey: 'form_variant_cb_latam',
    themeId: 'conquerblocks',
    variants: ['57', '58'],
    whiteBackgroundVariant: '58',
  },
  // Blocks US (cb-us, slug `blocks-us`): 59 (control) / 60 (fondo blanco).
  {
    match: ({ funnelSlug }) => funnelSlug === 'blocks-us',
    storageKey: 'form_variant_cb_us',
    themeId: 'conquerblocks',
    variants: ['59', '60'],
    whiteBackgroundVariant: '60',
  },
  // Languages, las tres regiones (cl-latam / cl-eu / cl-us): mismo test de
  // fondo blanco. Su landing usa el mismo renderer paperboard que Blocks.
  {
    match: ({ funnelSlug }) => funnelSlug === 'languages-latam',
    storageKey: 'form_variant_cl_latam',
    themeId: 'conquerlanguages',
    variants: ['63', '64'],
    whiteBackgroundVariant: '64',
  },
  {
    match: ({ funnelSlug }) => funnelSlug === 'languages-eu',
    storageKey: 'form_variant_cl_eu',
    themeId: 'conquerlanguages',
    variants: ['65', '66'],
    whiteBackgroundVariant: '66',
  },
  {
    match: ({ funnelSlug }) => funnelSlug === 'languages-us',
    storageKey: 'form_variant_cl_us',
    themeId: 'conquerlanguages',
    variants: ['67', '68'],
    whiteBackgroundVariant: '68',
  },
]

/* ── Experimentos de la PÁGINA DE VÍDEO ───────────────────────────────────
   Familia aparte de la de arriba, y por eso no comparten ni storageKey ni
   códigos: la variante de la landing viaja en el Lead (`utm_form_variant` de
   LeadRegister) y esta viaja en la PRELLAMADA (`utm_form_variant` de
   PreSchedule). Al vivir en entidades distintas, un funnel puede correr los dos
   tests a la vez sin que un dato pise al otro — de ahí que aquí sí esté
   finance-eu, que en la landing ya tiene el suyo.

   Hoy todos prueban lo mismo: `hideFooterVariant` es la variante que quita el
   footer de la página de vídeo — rasgado inferior, franja de papel y logo—, de
   modo que la zona oscura del vídeo llega hasta el final de la página.
   La numeración es independiente de la de la landing (otra entidad) y arranca
   en 1. Las filas viejas de PreSchedule que ocupaban estos códigos (enero-mayo
   de 2026, las dejó un backfill del CRM que copiaba la variante del
   LeadRegister, hoy apagado) se reetiquetaron sumándoles 10000, así que este
   rango queda libre para los tests nuevos. */
const VIDEO_VARIANT_EXPERIMENTS = [
  { funnelSlug: 'blocks-eu', storageKey: 'form_variant_video_cb_eu', variants: ['1', '2'] },
  { funnelSlug: 'blocks-latam', storageKey: 'form_variant_video_cb_latam', variants: ['3', '4'] },
  { funnelSlug: 'blocks-us', storageKey: 'form_variant_video_cb_us', variants: ['5', '6'] },
  { funnelSlug: 'finance-eu', storageKey: 'form_variant_video_cf_eu', variants: ['7', '8'] },
  { funnelSlug: 'finance-latam', storageKey: 'form_variant_video_cf_latam', variants: ['9', '10'] },
  { funnelSlug: 'languages-latam', storageKey: 'form_variant_video_cl_latam', variants: ['11', '12'] },
  { funnelSlug: 'languages-eu', storageKey: 'form_variant_video_cl_eu', variants: ['13', '14'] },
  { funnelSlug: 'languages-us', storageKey: 'form_variant_video_cl_us', variants: ['15', '16'] },
].map((exp) => ({
  ...exp,
  // Segundo código del par = variante de test (sin footer); el primero es control.
  hideFooterVariant: exp.variants[1],
}))

/* ¿Este visitante ya tiene asignada la rama de FONDO BLANCO en algún funnel de
   esta marca? Solo LEE, nunca asigna: no mete a nadie en el experimento.

   Existe porque la confirmación es la única etapa cuyo slug no es de fiar: su
   URL puede venir sin región (conquerfinance.com/confirmacion-llamada), y
   entonces el backend resuelve «cualquier funnel activo de la escuela», que hoy
   devuelve finance-eu. Un visitante de Finance LATAM en la rama blanca llegaba
   ahí y veía la confirmación en papel con el resto del funnel en blanco.

   El fondo lo decide la LANDING una sola vez; las etapas siguientes solo tienen
   que leer esa decisión. Se acota a la misma marca porque cada una vive en su
   dominio y no comparte localStorage con las demás. */
export function hasWhiteBackgroundAssigned(themeId) {
  if (!themeId) return false
  return FORM_VARIANT_EXPERIMENTS.some((exp) => (
    exp.whiteBackgroundVariant
    && exp.themeId === themeId
    && readFormVariant(exp) === exp.whiteBackgroundVariant
  ))
}

/** Experimento de la página de vídeo para este funnel, o null si no tiene. */
export function getVideoVariantExperiment(funnelSlug) {
  if (!funnelSlug) return null
  return VIDEO_VARIANT_EXPERIMENTS.find((exp) => exp.funnelSlug === funnelSlug) || null
}

/** Experimento que aplica a este funnel, o null si no hay ninguno activo. */
export function getFormVariantExperiment({ themeId, region, funnelSlug } = {}) {
  const ctx = {
    themeId: themeId || '',
    region: String(region || '').toLowerCase(),
    funnelSlug: funnelSlug || '',
  }
  return FORM_VARIANT_EXPERIMENTS.find((exp) => exp.match(ctx)) || null
}
