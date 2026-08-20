import { createContext, useState, useEffect, useCallback, useMemo } from 'react'
import { generateEventId, getOrCreateEventId, getOrCreateJourneyId, generateScheduleEventId, generatePrellamadaUuid } from '../../lib/trackingIds'
import { getPixelCookies } from '../../lib/cookies'
import { getUtmParams, getClickIds, buildTrackingPayload } from '../../lib/utmParams'
import { pushToDataLayer } from '../../lib/pixelEvents'

export const TrackingContext = createContext(null)

export default function TrackingProvider({ children }) {
  const [eventId] = useState(() => getOrCreateEventId())
  const [journeyId] = useState(() => getOrCreateJourneyId())
  // uuid de la Prellamada: por montaje, sin persistir → cambia en cada recarga
  // (igual que conquerx-funnels-new). Es la clave de upsert que viaja al CRM.
  const [prellamadaUuid] = useState(() => generatePrellamadaUuid())
  const [utmParams] = useState(() => getUtmParams())
  const [clickIds] = useState(() => getClickIds())
  const [pixelCookies] = useState(() => getPixelCookies())
  // IPv6 del visitante. Django solo ve la IPv4 que le pasa Cloudflare, así que
  // hay que preguntarla desde el cliente igual que hacía conquerx-funnels-new
  // (`api64.ipify.org`, quedándose con la respuesta solo si trae ':', porque el
  // servicio devuelve la IPv4 cuando no hay IPv6). Es un dato de matching para
  // las CAPI de Meta y TikTok. Fire-and-forget: si falla o tarda, el formulario
  // se envía igual y el campo va vacío, como hasta ahora.
  const [ipv6, setIpv6] = useState('')

  useEffect(() => {
    let cancelado = false
    fetch('https://api64.ipify.org?format=json')
      .then((r) => r.json())
      .then((d) => {
        if (!cancelado && d?.ip && d.ip.includes(':')) setIpv6(d.ip)
      })
      .catch(() => {})
    return () => { cancelado = true }
  }, [])

  useEffect(() => {
    pushToDataLayer({
      event_id: eventId,
      journey_id: journeyId,
    })
    console.log('[Tracking] event_id:', eventId, '| journey_id:', journeyId)
  }, [eventId, journeyId])

  const generateNewEventId = useCallback(() => generateEventId(), [])

  const buildFullPayload = useCallback(
    () =>
      buildTrackingPayload({
        eventId,
        journeyId,
        uuid: prellamadaUuid,
        utmParams,
        clickIds,
        pixelCookies,
        ipv6,
      }),
    [eventId, journeyId, prellamadaUuid, utmParams, clickIds, pixelCookies, ipv6]
  )

  const value = useMemo(
    () => ({
      eventId,
      journeyId,
      prellamadaUuid,
      utmParams,
      clickIds,
      pixelCookies,
      generateNewEventId,
      generateScheduleEventId,
      buildFullPayload,
    }),
    [eventId, journeyId, prellamadaUuid, utmParams, clickIds, pixelCookies, generateNewEventId, buildFullPayload]
  )

  return <TrackingContext.Provider value={value}>{children}</TrackingContext.Provider>
}
