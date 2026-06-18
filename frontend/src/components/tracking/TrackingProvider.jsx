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
      }),
    [eventId, journeyId, prellamadaUuid, utmParams, clickIds, pixelCookies]
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
