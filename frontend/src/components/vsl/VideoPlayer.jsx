import { useEffect, useRef, useState, useCallback } from 'react'
import Plyr from 'plyr'
import 'plyr/dist/plyr.css'
import UnmuteOverlay from './UnmuteOverlay'
import ReturningOverlay from './ReturningOverlay'

const STORAGE_KEY = 'vsl_progress'
const LEGACY_STORAGE_KEY = 'videolitics'

function readStoredState(storageKey, videoUrl) {
  try {
    const data = JSON.parse(localStorage.getItem(storageKey) || '{}')
    if (data.video_url === videoUrl) return data
  } catch {}
  return null
}

function getStoredProgress(videoUrl) {
  const current = readStoredState(STORAGE_KEY, videoUrl)
  if (current) return current

  const legacy = readStoredState(LEGACY_STORAGE_KEY, videoUrl)
  if (legacy) {
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(legacy))
    } catch {}
    return legacy
  }

  return null
}

function storeProgress(videoUrl, updates) {
  try {
    const current = getStoredProgress(videoUrl) || {
      time: 0,
      progress_percent: 0,
      visit_number: 0,
      unmuted: false,
      is_returning: false,
      progress_latest_visit: 0,
      video_url: videoUrl,
    }
    const nextValue = { ...current, ...updates, video_url: videoUrl }
    localStorage.setItem(STORAGE_KEY, JSON.stringify(nextValue))
    localStorage.setItem(LEGACY_STORAGE_KEY, JSON.stringify(nextValue))
  } catch {}
}

export default function VideoPlayer({ videoUrls, buttonPercent = 75, onAgendarClick, onShowButton, onProgress }) {
  const videoRef = useRef(null)
  const playerRef = useRef(null)
  const [showUnmute, setShowUnmute] = useState(false)
  const [showReturning, setShowReturning] = useState(false)
  const [storedData, setStoredData] = useState(null)
  const buttonShownRef = useRef(false)
  const milestonesReportedRef = useRef(new Set())

  const videoUrl = videoUrls?.[0] || ''

  useEffect(() => {
    if (!videoRef.current || !videoUrl) return

    const stored = getStoredProgress(videoUrl)
    const isReturning = stored && stored.progress_percent > 0

    if (isReturning) {
      setStoredData(stored)
      setShowReturning(true)
      storeProgress(videoUrl, {
        visit_number: (stored.visit_number || 0) + 1,
        is_returning: true,
      })

      // Show button for ALL returning users (same as original)
      buttonShownRef.current = true
      if (onShowButton) onShowButton()
    } else {
      storeProgress(videoUrl, { visit_number: 1 })
      setShowUnmute(true)
    }

    videoRef.current.src = videoUrl
    videoRef.current.muted = true

    const player = new Plyr(videoRef.current, {
      hideControls: false,
      autoplay: true,
      muted: true,
      controls: ['play', 'mute', 'volume', 'fullscreen'],
    })

    playerRef.current = player

    // Ensure muted state after Plyr wraps the element
    player.muted = true

    player.on('timeupdate', () => {
      if (!player.duration) return
      const percent = (player.currentTime / player.duration) * 100

      // Only update progress_percent if higher (never decrease on replay/reload)
      const current = getStoredProgress(videoUrl)
      const maxPercent = current && current.progress_percent > percent
        ? current.progress_percent
        : percent

      const updates = {
        time: player.currentTime,
        progress_percent: maxPercent,
        unmuted: !player.muted,
      }

      // Only track progress_latest_visit when unmuted (user is actively watching)
      if (!player.muted) {
        updates.progress_latest_visit = player.currentTime
      }

      storeProgress(videoUrl, updates)

      if (percent >= buttonPercent && !buttonShownRef.current) {
        buttonShownRef.current = true
        if (onShowButton) onShowButton()
      }

      // Report progress every 10% (for ActiveCampaign / lead tracking)
      if (onProgress) {
        for (const p of [10, 20, 30, 40, 50, 60, 70, 80, 90, 100]) {
          if (maxPercent >= p && !milestonesReportedRef.current.has(`p${p}`)) {
            milestonesReportedRef.current.add(`p${p}`)
            onProgress(p)
          }
        }
      }

    })

    player.on('ended', () => {
      if (onAgendarClick) onAgendarClick()
    })

    // Always autoplay muted — even with returning overlay showing
    player.play()?.catch(() => {})

    return () => {
      player.destroy()
    }
  }, [videoUrl])

  const handleUnmute = useCallback(() => {
    setShowUnmute(false)
    if (playerRef.current) {
      playerRef.current.muted = false
      playerRef.current.restart()
    }
  }, [])

  const handleContinue = useCallback(() => {
    setShowReturning(false)
    if (playerRef.current && storedData) {
      playerRef.current.muted = false
      playerRef.current.currentTime = storedData.progress_latest_visit || storedData.time
      playerRef.current.play()?.catch(() => {})
    }
  }, [storedData])

  const handleRestart = useCallback(() => {
    setShowReturning(false)
    if (playerRef.current) {
      playerRef.current.restart()
      playerRef.current.play()?.catch(() => {})
      playerRef.current.muted = false
    }
  }, [])

  if (!videoUrl) return null

  return (
    <div className="relative aspect-video bg-black rounded-lg overflow-hidden">
      <video
        ref={videoRef}
        playsInline
        preload="auto"
        muted
        autoPlay
        className="w-full h-full"
      />

      {showUnmute && <UnmuteOverlay onUnmute={handleUnmute} />}
      {showReturning && (
        <ReturningOverlay onContinue={handleContinue} onRestart={handleRestart} />
      )}
    </div>
  )
}
