import { useState, useEffect } from 'react'

// Start fetch immediately at module load (runs once when JS is parsed)
let geoPromise = null
let cachedResult = { countryCode: null, resolved: false }

function startGeoFetch() {
  if (geoPromise) return geoPromise
  geoPromise = fetch('https://get.geojs.io/v1/ip/country.json')
    .then((r) => r.json())
    .then((data) => {
      if (data?.country) {
        cachedResult = { countryCode: data.country.toUpperCase(), resolved: true }
      } else {
        cachedResult = { countryCode: null, resolved: true }
      }
    })
    .catch(() => {
      cachedResult = { countryCode: null, resolved: true }
    })
  return geoPromise
}

// Fire immediately on import (solo en cliente; en SSR no hay fetch ni red de IP)
if (typeof window !== 'undefined') startGeoFetch()

export default function useGeoLocation() {
  const [countryCode, setCountryCode] = useState(cachedResult.countryCode)
  const [loading, setLoading] = useState(!cachedResult.resolved)

  useEffect(() => {
    // If already resolved by the time the component mounts, sync state
    if (cachedResult.resolved) {
      setCountryCode(cachedResult.countryCode)
      setLoading(false)
      return
    }

    // Otherwise wait for the in-flight promise
    startGeoFetch().finally(() => {
      setCountryCode(cachedResult.countryCode)
      setLoading(false)
    })
  }, [])

  return { countryCode, loading }
}
