import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState } from 'react'
import { fireAllPageView } from './pixelEvents'

/* Router mínimo del funnel SPA.

   Las URLs canónicas de cada etapa (landing → video → stepform → confirmation)
   las sigue emitiendo el backend (data-*-url en el shell): aquí solo decidimos
   qué etapa renderizar y navegamos entre ellas con pushState, sin recarga.
   Al navegar se disparan pageviews virtuales en los píxeles (los scripts base
   ya disparan el PageView de la carga inicial desde la plantilla). */

export const RouterContext = createContext(null)

const normalize = (path) => (path || '/').replace(/\/+$/, '') || '/'

function pathOf(url) {
  try {
    return normalize(new URL(url, window.location.origin).pathname)
  } catch (_) {
    return ''
  }
}

export function stageFromPath(pathname, urls, fallback) {
  const path = normalize(pathname)
  for (const [stage, url] of Object.entries(urls)) {
    if (url && pathOf(url) === path) return stage
  }
  return fallback
}

export default function FunnelRouter({ initialStage, urls, children }) {
  const [stage, setStage] = useState(initialStage)

  // ¿Se ha navegado ya dentro de la SPA, o seguimos en la etapa con la que se
  // cargó el documento? Importa para el autoplay del vídeo: una navegación con
  // pushState conserva la activación de usuario del navegador (el submit de la
  // landing), así que el vídeo puede arrancar con sonido; una carga directa o
  // una recarga no la tiene y el navegador lo bloquearía.
  // Va en un ref a propósito: se consulta al montar, no debe provocar renders.
  const navegadoRef = useRef(false)
  const hasNavigated = useCallback(() => navegadoRef.current, [])

  // `search` debe venir con '?' inicial; si no se pasa, se conserva el query
  // string actual (prefill + tracking viajan por la URL entre etapas).
  const navigate = useCallback(
    (nextStage, { search } = {}) => {
      const url = urls[nextStage]
      if (!url) {
        console.error(`[Router] Etapa sin URL: ${nextStage}`)
        return
      }
      const qs = search !== undefined ? search : window.location.search || ''
      window.history.pushState({ stage: nextStage }, '', `${url}${qs}`)
      navegadoRef.current = true
      setStage(nextStage)
      window.scrollTo({ top: 0, behavior: 'auto' })
      fireAllPageView()
    },
    [urls]
  )

  const navigateRaw = useCallback(
    (path, { search, stage: targetStage = 'confirmation' } = {}) => {
      const qs = search !== undefined ? search : window.location.search || ''
      window.history.pushState({ stage: targetStage }, '', `${path}${qs}`)
      navegadoRef.current = true
      setStage(targetStage)
      window.scrollTo({ top: 0, behavior: 'auto' })
      fireAllPageView()
    },
    []
  )

  useEffect(() => {
    const onPop = () => {
      setStage(stageFromPath(window.location.pathname, urls, initialStage))
    }
    window.addEventListener('popstate', onPop)
    return () => window.removeEventListener('popstate', onPop)
  }, [urls, initialStage])

  const value = useMemo(
    () => ({ stage, navigate, navigateRaw, urls, hasNavigated }),
    [stage, navigate, navigateRaw, urls, hasNavigated]
  )

  return <RouterContext.Provider value={value}>{children}</RouterContext.Provider>
}

/* null cuando el componente se monta fuera de la SPA (fallback: navegación
   con recarga completa). */
export function useRouter() {
  return useContext(RouterContext)
}
