import { createContext, useContext, useMemo } from 'react'
import { useFormVariant } from '../lib/formVariantContext'
import { toWhiteBackground } from './whiteBackground'
import conquerblocks from './conquerblocks'
import conquerlegal from './conquerlegal'
import conquerfinance from './conquerfinance'
import conquerlanguages from './conquerlanguages'
import defaultTheme from './default'

const THEMES = {
  conquerblocks,
  conquerlegal,
  conquerfinance,
  conquerlanguages,
}

// Strip everything but letters: 'conquer-blocks' / 'blocks-eu' → 'conquerblocks' / 'blockseu'
function normalize(value) {
  return String(value || '').toLowerCase().replace(/[^a-z]/g, '')
}

// Detect brand from a school slug ('conquer-blocks') or funnel slug ('blocks-eu')
function detectBrand(value) {
  const n = normalize(value)
  if (!n) return null
  if (n.includes('blocks')) return 'conquerblocks'
  if (n.includes('finance')) return 'conquerfinance'
  if (n.includes('languages')) return 'conquerlanguages'
  if (n.includes('legal')) return 'conquerlegal'
  return null
}

// Accepts any number of hints (escuela, slug, ...); first match wins.
export function getTheme(...hints) {
  for (const hint of hints) {
    const brand = detectBrand(hint)
    if (brand && THEMES[brand]) return THEMES[brand]
  }
  return defaultTheme
}

/* Aplica al tema ya resuelto (incluido el rediseño por página: `landingPaper`,
   `stepformPaper`…) la variante A/B de diseño que le toque a este visitante.
   Hoy solo existe una: el fondo blanco, que cubre el funnel ENTERO (landing,
   vídeo, stepform, calendario y confirmación), así que la llama cada etapa al
   resolver su tema. La variante se decide una sola vez, en el root, y viaja por
   contexto: todas las etapas ven la misma. */
export function useVariantTheme(theme) {
  const { whiteBackground } = useFormVariant()
  return useMemo(
    () => (whiteBackground ? toWhiteBackground(theme) : theme),
    [theme, whiteBackground]
  )
}

export const ThemeContext = createContext(defaultTheme)

export function useTheme() {
  return useContext(ThemeContext)
}

export { defaultTheme }
