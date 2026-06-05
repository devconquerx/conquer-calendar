import { useContext } from 'react'
import { TrackingContext } from '../components/tracking/TrackingProvider'

export default function useTracking() {
  const ctx = useContext(TrackingContext)
  if (!ctx) throw new Error('useTracking must be used within a TrackingProvider')
  return ctx
}
