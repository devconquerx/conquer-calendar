import { createContext, useState, useEffect, useCallback, useMemo } from 'react'
import { generateEventId, getOrCreateJourneyId, generateScheduleEventId } from '../../lib/trackingIds'
import { getPixelCookies } from '../../lib/cookies'
import { getUtmParams, getClickIds, buildTrackingPayload } from '../../lib/utmParams'
import { pushToDataLayer } from '../../lib/pixelEvents'

export const TrackingContext = createContext(null)

export default function TrackingProvider({ children }) {
  const [eventId] = useState(() => generateEventId())
  const [journeyId] = useState(() => getOrCreateJourneyId())
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
        utmParams,
        clickIds,
        pixelCookies,
      }),
    [eventId, journeyId, utmParams, clickIds, pixelCookies]
  )

  const value = useMemo(
    () => ({
      eventId,
      journeyId,
      utmParams,
      clickIds,
      pixelCookies,
      generateNewEventId,
      generateScheduleEventId,
      buildFullPayload,
    }),
    [eventId, journeyId, utmParams, clickIds, pixelCookies, generateNewEventId, buildFullPayload]
  )

  return <TrackingContext.Provider value={value}>{children}</TrackingContext.Provider>
}
