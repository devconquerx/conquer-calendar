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
