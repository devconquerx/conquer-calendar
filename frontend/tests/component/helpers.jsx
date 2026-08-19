import { render } from '@testing-library/react'
import TrackingProvider from '../../src/components/tracking/TrackingProvider'
import FormVariantProvider from '../../src/lib/formVariantContext'
import { getTheme } from '../../src/themes'

/* Monta un componente del funnel con el mismo entorno que en la app: proveedor
   de tracking y de variante A/B. `variante` deja la variante ya asignada en
   localStorage antes de montar, que es como llega un visitante que ya pasó por
   aquí — así el test controla la rama sin depender del azar. */
export function renderConFunnel(ui, { escuela = 'conquer-blocks', slug = 'blocks-latam', region = 'latam', variante, storageKey } = {}) {
  if (variante && storageKey) localStorage.setItem(storageKey, variante)
  return render(
    <TrackingProvider>
      <FormVariantProvider themeId={getTheme(escuela, slug).id} region={region} funnelSlug={slug}>
        {ui}
      </FormVariantProvider>
    </TrackingProvider>
  )
}

/* Los logos del funnel son <img> sin texto alternativo útil; los decorativos
   van marcados con aria-hidden. Esta es la distinción que hace el test del A/B
   del footer: quitamos los logos, no los píxeles. */
export function logosVisibles(contenedor) {
  return [...contenedor.querySelectorAll('img')].filter((i) => i.getAttribute('aria-hidden') !== 'true')
}
