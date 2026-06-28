/**
 * Cookie reading utilities for pixel tracking.
 */

export function readCookie(name) {
  if (typeof document === 'undefined') return ''
  const match = document.cookie.match(new RegExp('(?:^|;\\s*)' + name + '=([^;]*)'))
  return match ? decodeURIComponent(match[1]) : ''
}

/**
 * Get Meta and TikTok pixel cookies.
 * _fbc: reads cookie, fallback builds from fbclid URL param (for in-app browsers).
 * _fbp: reads Meta Pixel browser cookie.
 * _ttp: reads TikTok Pixel browser cookie.
 */
export function getPixelCookies() {
  if (typeof window === 'undefined') return { _fbc: '', _fbp: '', _ttp: '' }
  const _fbp = readCookie('_fbp')

  let _fbc = readCookie('_fbc')
  if (!_fbc) {
    const fbclid = new URLSearchParams(window.location.search).get('fbclid')
    if (fbclid) {
      _fbc = `fb.1.${Date.now()}.${fbclid}`
      document.cookie = `_fbc=${_fbc}; max-age=${7 * 24 * 3600}; path=/; SameSite=Lax`
    }
  }

  const _ttp = readCookie('_ttp')

  return { _fbc, _fbp, _ttp }
}
