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
  // Conquer AI (ai-eu) NO corre ningún experimento: su landing pide el teléfono
  // siempre y obligatorio, sin checkbox, fijo por config (`landing.phoneRequired`,
  // migración 0032). Llegó a tener uno el 14/09/2026 con los códigos 77/78; se
  // retiró el mismo día y NO se reciclan.
  // Blocks EU (69/70), Blocks EU-2 (71/72) y Languages EU (65/66) cerraron el
  // A/B de fondo el 07/10/2026 con el PAPEL como ganador: sin experimento, el
  // funnel vuelve al papel por defecto del tema y el lead no lleva
  // utm_form_variant. Sus códigos no se reciclan. En Blocks EU el checkbox de
  // WhatsApp sigue fijo por config (`landing.whatsappOptin`).
  // Blocks US (cb-us, slug `blocks-us`): 73 (control: no se pide el teléfono,
  // solo lo captura el honeypot) / 74 (test: checkbox de WhatsApp, que al
  // marcarse revela el campo de teléfono y lo hace obligatorio).
  //
  // Antes corría aquí el A/B de fondo (59/60). Se apagó el 14/09/2026 con el
  // PAPEL como ganador: al no declarar `whiteBackgroundVariant`, el funnel
  // vuelve al papel para todo el mundo, que es el comportamiento por defecto
  // del tema. Los códigos 59/60 no se reciclan —significan papel/blanco en los
  // leads históricos— y por eso cambia también la `storageKey`.
  {
    match: ({ funnelSlug }) => funnelSlug === 'blocks-us',
    storageKey: 'form_variant_cb_us_tel',
    variants: ['73', '74'],
    whatsappOptinVariant: '74',
  },
  // Languages LATAM: test de fondo blanco (EU lo cerró el 07/10/2026, ver arriba). Su landing usa el mismo
  // renderer paperboard que Blocks. US ya no está aquí: cerró el de fondo el
  // 14/09/2026 y corre el del teléfono, más abajo.
  {
    match: ({ funnelSlug }) => funnelSlug === 'languages-latam',
    storageKey: 'form_variant_cl_latam',
    themeId: 'conquerlanguages',
    variants: ['63', '64'],
    whiteBackgroundVariant: '64',
  },
  {
    // Languages US (cl-us): mismo cambio y por el mismo motivo que Blocks US
    // —fuera el A/B de fondo (67/68), gana el papel; entra el del teléfono—,
    // con su propio par de códigos para no mezclar los dos funnels.
    match: ({ funnelSlug }) => funnelSlug === 'languages-us',
    storageKey: 'form_variant_cl_us_tel',
    variants: ['75', '76'],
    whatsappOptinVariant: '76',
  },
]

/* ── Experimentos CERRADOS con ganador fijo ───────────────────────────────
   El 07/10/2026 se apagaron estos tres A/B de la landing dejando la rama B
   (la de test) para todo el mundo. Siguen declarando la MISMA bandera que en el
   experimento, así que el resto del código (fondo blanco, teléfono
   obligatorio, texto de WhatsApp) no distingue entre test y ganador; lo que
   cambia es que:

   - no se sortea: `winner` es la variante de todos, desde el SSR (sin parpadeo
     de papel a blanco);
   - NO se manda `utm_form_variant` en el lead: el test ya no existe y el código
     marcaría como «rama B» leads que no participaron en ningún reparto;
   - se guarda en su `storageKey` igualmente, porque la confirmación sin región
     (ver `hasWhiteBackgroundAssigned`) hereda el fondo leyendo esa clave.

   Sus códigos (55/56, 57/58, 61/62) NO se reciclan: siguen significando sus
   ramas en los leads históricos. */
const WINNING_VARIANTS = [
  // Blocks LATAM: ganó el fondo blanco (58) frente al papel (57).
  { funnelSlug: 'blocks-latam', storageKey: 'form_variant_cb_latam', themeId: 'conquerblocks', winner: '58', whiteBackgroundVariant: '58' },
  // Finance LATAM: ganó el fondo blanco (62) frente al papel (61).
  { funnelSlug: 'finance-latam', storageKey: 'form_variant_cf_latam', themeId: 'conquerfinance', winner: '62', whiteBackgroundVariant: '62' },
  // Finance EU: ganó el campo de WhatsApp visible y obligatorio (56) frente al
  // checkbox (55). El texto legal que menciona WhatsApp iba en las dos ramas y
  // se queda.
  { funnelSlug: 'finance-eu', storageKey: 'form_variant_cf', winner: '56', alwaysPhoneVariant: '56', whatsappComplianceText: true },
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
  if (FORM_VARIANT_EXPERIMENTS.some((exp) => (
    exp.whiteBackgroundVariant
    && exp.themeId === themeId
    && readFormVariant(exp) === exp.whiteBackgroundVariant
  ))) return true
  return WINNING_VARIANTS.some((exp) => (
    exp.whiteBackgroundVariant
    && exp.themeId === themeId
    && readFormVariant({ storageKey: exp.storageKey, variants: [exp.winner] }) === exp.whiteBackgroundVariant
  ))
}

/** Experimento de la página de vídeo para este funnel, o null si no tiene. */
export function getVideoVariantExperiment(funnelSlug) {
  if (!funnelSlug) return null
  return VIDEO_VARIANT_EXPERIMENTS.find((exp) => exp.funnelSlug === funnelSlug) || null
}

/** Experimento que aplica a este funnel (activo o cerrado con `winner`), o
    null si no tiene ninguno. */
export function getFormVariantExperiment({ themeId, region, funnelSlug } = {}) {
  const ctx = {
    themeId: themeId || '',
    region: String(region || '').toLowerCase(),
    funnelSlug: funnelSlug || '',
  }
  return FORM_VARIANT_EXPERIMENTS.find((exp) => exp.match(ctx))
    || WINNING_VARIANTS.find((exp) => exp.funnelSlug === ctx.funnelSlug)
    || null
}

/** Deja guardado el ganador de un experimento cerrado en su storageKey (para la
    herencia de la confirmación). Solo client-side; nunca falla. */
export function persistWinningVariant(experiment) {
  if (typeof window === 'undefined' || !experiment?.winner || !experiment.storageKey) return
  try { localStorage.setItem(experiment.storageKey, experiment.winner) } catch (_) {}
}
