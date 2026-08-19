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
export function resolveFormVariant({ storageKey, variants }) {
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
   igual que en el funnel viejo. */
const FORM_VARIANT_EXPERIMENTS = [
  // Finance EU: 55 (checkbox, igual que Legal) / 56 (campo visible y obligatorio).
  {
    match: ({ themeId, region }) => themeId === 'conquerfinance' && region === 'eu',
    storageKey: 'form_variant_cf',
    variants: ['55', '56'],
    whatsappOptinVariant: '55',
    alwaysPhoneVariant: '56',
    whatsappComplianceText: true,
  },
  // Blocks EU, segunda landing (cb-eu-2, slug `blocks-eu-2`): mismo mecanismo
  // que la principal pero con experimento independiente, para no mezclar splits.
  {
    match: ({ themeId, region, funnelSlug }) =>
      themeId === 'conquerblocks' && region === 'eu' && funnelSlug === 'blocks-eu-2',
    storageKey: 'form_variant_cb_eu_2',
    variants: ['53', '54'],
    whatsappOptinVariant: '54',
  },
  // Blocks EU, landing principal (cb-eu, slug `blocks-eu`): 51 (control: sin
  // checkbox, solo honeypot, igual que LATAM/US) / 52 (test: checkbox WhatsApp).
  {
    match: ({ themeId, region }) => themeId === 'conquerblocks' && region === 'eu',
    storageKey: 'form_variant_cb_eu',
    variants: ['51', '52'],
    whatsappOptinVariant: '52',
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
    variants: ['57', '58'],
    whiteBackgroundVariant: '58',
  },
]

/** Experimento que aplica a este funnel, o null si no hay ninguno activo. */
export function getFormVariantExperiment({ themeId, region, funnelSlug } = {}) {
  const ctx = {
    themeId: themeId || '',
    region: String(region || '').toLowerCase(),
    funnelSlug: funnelSlug || '',
  }
  return FORM_VARIANT_EXPERIMENTS.find((exp) => exp.match(ctx)) || null
}
