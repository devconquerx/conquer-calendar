import { useState, useCallback, useMemo } from 'react'
import VideoPlayer from '../components/vsl/VideoPlayer'
import AgendarButton from '../components/vsl/AgendarButton'
import { getTheme } from '../themes'
import { sendVideoProgressToBackend } from '../api'
import { safeHtml } from '../lib/sanitize'

/* Página de video (VSL) standalone — entre la landing de lead y el StepForm.
   Muestra el video (autoplay muted + overlays), revela el botón al alcanzar el
   buttonPercent y, al pulsarlo, redirige al StepForm conservando el query string
   (name/email/phone/event_id/journey_id que vienen de la landing). */
export default function VideoPage({ school, region, formConfig, videoUrls, buttonPercent, nextUrl }) {
  const [showButton, setShowButton] = useState(false)

  const theme = getTheme(school?.slug)
  const isCB = theme.id === 'conquerblocks'
  const assets = theme.assets

  const video = formConfig?.video || {}
  const urls = videoUrls && videoUrls.length ? videoUrls : (video.videoUrls || [])
  const pct = buttonPercent || video.buttonPercent || 75
  const landing = formConfig?.landing || formConfig?.welcome || {}

  // Email para el tracking de progreso (viene como query param desde la landing).
  const email = useMemo(
    () => new URLSearchParams(window.location.search).get('email') || '',
    []
  )

  const handleShowButton = useCallback(() => setShowButton(true), [])

  const handleProgress = useCallback(
    (percent) => {
      sendVideoProgressToBackend({ email, percent, school: school?.slug, region })
    },
    [email, school, region]
  )

  // Siguiente etapa: el StepForm. Conserva el query string actual (prefill + tracking).
  const goToStepForm = useCallback(() => {
    const search = window.location.search || ''
    window.location.href = `${nextUrl}${search}`
  }, [nextUrl])

  const pageStyle = isCB && assets?.paperboardTexture ? {
    backgroundImage: `linear-gradient(rgba(255,255,255,0.55), rgba(255,255,255,0.55)), url(${assets.paperboardTexture})`,
    backgroundSize: 'cover',
    backgroundPosition: 'center',
    backgroundAttachment: 'fixed',
  } : undefined

  return (
    <div
      className={`min-h-screen overflow-x-hidden relative flex flex-col ${isCB ? 'font-funnel bg-cb-bg text-cb-ink' : 'bg-[#0A0A0A] text-white'}`}
      style={pageStyle}
    >
      <main className="relative z-10 flex-1 w-full max-w-[920px] mx-auto px-5 flex flex-col">
        {/* Logo */}
        {assets?.logo && (
          <div className="py-4 flex justify-center">
            <img src={assets.logo} alt={school?.slug || ''} className="h-9 w-auto" />
          </div>
        )}

        {/* Titular (de la landing, si existe) */}
        {(landing.subtitle || landing.title) && (
          <div className="text-center mb-5 animate-fade-in">
            {landing.subtitle && (
              <p className={`text-sm font-medium uppercase tracking-wide mb-2 ${isCB ? 'bg-gradient-to-r from-[#FF4000] to-[#FFBF00] bg-clip-text text-transparent' : 'text-orange-400'}`}>
                {landing.subtitle}
              </p>
            )}
            {landing.title && (
              <h1
                className={`max-w-[760px] mx-auto text-xl md:text-2xl font-medium leading-[1.15] ${isCB
                  ? 'text-cb-ink [&_strong]:[background-image:linear-gradient(135deg,#FF4000,#FF9800)] [&_strong]:bg-clip-text [&_strong]:text-transparent [&_em]:not-italic [&_em]:font-bold [&_em]:[-webkit-text-fill-color:#0A0A0A] [&_em]:[background-image:none]'
                  : 'text-white'}`}
                dangerouslySetInnerHTML={safeHtml(landing.title)}
              />
            )}
          </div>
        )}

        {/* Reproductor */}
        <div className="animate-fade-in">
          <VideoPlayer
            videoUrls={urls}
            buttonPercent={pct}
            onAgendarClick={goToStepForm}
            onShowButton={handleShowButton}
            onProgress={handleProgress}
          />
        </div>

        {/* Botón CTA — aparece al alcanzar el buttonPercent */}
        {showButton && <AgendarButton theme={theme} onClick={goToStepForm} />}
      </main>

      <div className="py-10" />
    </div>
  )
}
