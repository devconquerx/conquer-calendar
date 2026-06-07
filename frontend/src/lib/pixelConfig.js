/**
 * Pixel IDs por escuela para disparar eventos client-side.
 * Usado por pixelEvents.js. Los scripts base se cargan server-side en page.html.
 */

const PIXEL_IDS = {
  conquerblocks: {
    meta: '921361326426436',
    tiktok: 'CTMK2ORC77U1LI1DFAD0',
    ga4: 'G-LNCT8EQRDT',
    googleAds: {
      customerId: '6193039470',
      conversions: {
        lead: '7478637099',
        schedule: '7478385997',
      },
    },
  },
  conquerfinance: {
    meta: '1011283009921986',
    tiktok: 'D03U523C77U9QS83BBI0',
    ga4: 'G-9PGHQW52XM',
    googleAds: {
      customerId: '1192352539',
      conversions: {
        lead: '7478395177',
        schedule: '7478652894',
      },
    },
  },
  conquerlanguages: {
    meta: '627205843180202',
    tiktok: 'CVIQE0JC77U02UO7SEC0',
    ga4: 'G-FJBW5107MW',
    googleAds: {
      customerId: '1164152552',
      conversions: {
        lead: '7478389619',
        schedule: '7478647338',
      },
    },
  },
}

// conquer-calendar usa 'conquer-blocks' (con guion) como escuela; funnels usa
// 'conquerblocks'. Normalizamos a la clave canónica sin guion.
const SCHOOL_ALIASES = {
  'conquer-blocks': 'conquerblocks',
  'conquer-finance': 'conquerfinance',
  'conquer-languages': 'conquerlanguages',
}

export function normalizeSchool(slug) {
  if (!slug) return ''
  const s = String(slug).trim().toLowerCase()
  return SCHOOL_ALIASES[s] || s
}

export function getPixelIds(schoolSlug) {
  return PIXEL_IDS[normalizeSchool(schoolSlug)] || null
}
