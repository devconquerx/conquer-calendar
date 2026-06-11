import { createContext, useContext } from 'react'
import conquerblocks from './conquerblocks'
import conquerlegal from './conquerlegal'
import defaultTheme from './default'

const THEMES = {
  conquerblocks,
  conquerlegal,
  // conquerfinance, conquerlanguages → default (white) for now
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

export const ThemeContext = createContext(defaultTheme)

export function useTheme() {
  return useContext(ThemeContext)
}

export { defaultTheme }
