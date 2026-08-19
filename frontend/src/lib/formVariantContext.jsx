import { createContext, useContext, useEffect, useLayoutEffect, useMemo, useState } from 'react'
import {
  getFormVariantExperiment,
  getVideoVariantExperiment,
  resolveFormVariant,
} from './formVariant'

/* Variante A/B del visitante, resuelta UNA vez para todo el funnel y expuesta
   por contexto: la necesitan tanto el formulario de la landing (la manda al
   backend como `utm_form_variant`) como el tema de cada etapa (la variante de
   fondo blanco de Blocks LATAM afecta a landing, vídeo, stepform, calendario y
   confirmación, que son pantallas distintas del mismo SPA). */

const FormVariantContext = createContext({
  variant: null,
  experiment: null,
  whiteBackground: false,
})

export function useFormVariant() {
  return useContext(FormVariantContext)
}

/* La asignación lee localStorage/URL, así que solo puede ocurrir en el cliente:
   el primer render (y el SSR) usa la variante nula = comportamiento de control.
   En el navegador se resuelve en un layout effect —antes del primer paint— para
   que el fondo no parpadee de papel a blanco; en SSR (Node) cae a useEffect,
   que allí nunca corre y no emite el warning de useLayoutEffect. */
const useVariantEffect = typeof window === 'undefined' ? useEffect : useLayoutEffect

export default function FormVariantProvider({ themeId, region, funnelSlug, children }) {
  const experiment = useMemo(
    () => getFormVariantExperiment({ themeId, region, funnelSlug }),
    [themeId, region, funnelSlug]
  )
  const [variant, setVariant] = useState(null)

  useVariantEffect(() => {
    if (!experiment) return
    setVariant(resolveFormVariant(experiment))
  }, [experiment])

  const value = useMemo(
    () => ({
      variant,
      experiment,
      whiteBackground: !!experiment?.whiteBackgroundVariant
        && variant === experiment.whiteBackgroundVariant,
    }),
    [variant, experiment]
  )

  return <FormVariantContext.Provider value={value}>{children}</FormVariantContext.Provider>
}

/* Variante del test de la PÁGINA DE VÍDEO. A diferencia de la de la landing no
   se resuelve en el root: se asigna aquí, al montar la página de vídeo, para
   que solo entre en el experimento quien la ve de verdad (a la reserva se
   llega también por link directo del setter, sin pasar por el vídeo). El
   StepForm luego la LEE de localStorage, sin asignar, para colgarla de la
   prellamada. */
export function useVideoVariant(funnelSlug) {
  const experiment = useMemo(() => getVideoVariantExperiment(funnelSlug), [funnelSlug])
  const [variant, setVariant] = useState(null)

  useVariantEffect(() => {
    if (!experiment) return
    setVariant(resolveFormVariant(experiment))
  }, [experiment])

  return {
    variant,
    hideFooterLogo: !!experiment && variant === experiment.hideFooterLogoVariant,
  }
}
