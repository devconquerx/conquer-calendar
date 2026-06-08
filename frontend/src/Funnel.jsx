import React, { useState, useEffect, useRef, useMemo, useCallback } from 'react'
import { fetchConfig, postResolver, registerLead } from './api'
import useTracking from './hooks/useTracking'
import { fireAllLead } from './lib/pixelEvents'
import FormStep from './components/FormStep'
import Calendar from './components/Calendar'
import BookingDetails from './components/BookingDetails'
import CalendlyEmbed from './components/CalendlyEmbed'
import Confirmation from './components/Confirmation'
import RejectScreen from './components/RejectScreen'
import { buildCalendlyParams, buildCalendlyUrl, getYearMonthForCalendly } from './lib/calendly'
import ProgressBar from './components/form-engine/ProgressBar'
import StepTransition from './components/form-engine/StepTransition'
import WelcomeScreen from './components/form-engine/fields/WelcomeScreen'
import { getPrefillRespuestas } from './lib/prefillParams'
import { getTheme, ThemeContext } from './themes'
import './funnel.css'

export default function Funnel({ slug, escuela: escuelaProp = '', confirmationUrl = '' }) {
  const tracking = useTracking()
  const leadRegisteredRef = useRef(false)
  // schedule_event_id del recorrido: se genera una vez al montar y se reutiliza
  // en el utm_term de Calendly y en fireAllSchedule (igual que el funnel de
  // Django, que lo genera en `trackingParams` al montar el form).
  const scheduleEventId = useMemo(() => {
    const id = tracking.generateScheduleEventId()
    try { localStorage.setItem('cqx_schedule_event_id', id) } catch (_) {}
    return id
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])
  const [blocks, setBlocks] = useState([])
  const [escuela, setEscuela] = useState('')
  const [messages, setMessages] = useState({})
  const [funnelFont, setFunnelFont] = useState('')
  const [currentIndex, setCurrentIndex] = useState(0)
  const [direction, setDirection] = useState('forward')
  // Prefill desde el query string que propaga la landing (name/email/phone),
  // igual que el funnel de Django. Los ids de bloque son name/email/phone.
  const [respuestas, setRespuestas] = useState(() => getPrefillRespuestas(window.location.search))
  const [phase, setPhase] = useState('loading')
  const [outcome, setOutcome] = useState(null)
  const [selectedSlot, setSelectedSlot] = useState(null)
  const [calendlyUrl, setCalendlyUrl] = useState('')
  const [loadError, setLoadError] = useState('')

  useEffect(() => {
    fetchConfig(slug)
      .then(data => {
        setBlocks(data.blocks || [])
        setEscuela(data.escuela || '')
        setMessages(data.messages || {})
        setFunnelFont(data.theme?.font || '')
        setPhase('form')
      })
      .catch(e => {
        setLoadError(e.message)
        setPhase('error')
      })
  }, [slug])

  const current = blocks[currentIndex]

  // Progress counts from block 1 onward (block 0 = welcome screen)
  const totalSteps = blocks.length - 1
  const progress = totalSteps > 0 ? Math.round(((currentIndex) / totalSteps) * 100) : 0

  const handleChange = (value) => {
    if (!current) return
    setRespuestas(prev => ({ ...prev, [current.id]: value }))
  }

  // Registra el lead (nombre+email+tracking) apenas se captura el email, para
  // capturarlo aunque abandone antes de agendar (igual que funnels).
  const maybeRegisterLead = (answers) => {
    if (leadRegisteredRef.current) return
    const email = answers.email
    if (!email) return
    leadRegisteredRef.current = true
    registerLead({
      name: answers.name || '',
      email,
      lead_phone: answers.phone || '',
      escuela: escuelaProp || escuela,
      funnel: slug,
      event_id: tracking.eventId,
      journey_id: tracking.journeyId,
      user_agent: navigator.userAgent,
      url: window.location.href,
      ...tracking.utmParams,
      ...tracking.clickIds,
      _fbp: tracking.pixelCookies._fbp || '',
      _fbc: tracking.pixelCookies._fbc || '',
      _ttp: tracking.pixelCookies._ttp || '',
    })
  }

  const handleNext = (value) => {
    if (!current) return
    const updated =
      current.id !== 'welcome' && value !== null
        ? { ...respuestas, [current.id]: value }
        : { ...respuestas }
    setRespuestas(updated)
    maybeRegisterLead(updated)

    setDirection('forward')
    if (currentIndex < blocks.length - 1) {
      setCurrentIndex(i => i + 1)
    } else {
      submitResolver(updated)
    }
  }

  const handleBack = () => {
    setDirection('backward')
    setCurrentIndex(i => Math.max(0, i - 1))
  }

  // Al agendar en Calendly: navega a la página de Confirmación (equivalente al
  // router.visit del funnel de Django). El evento Schedule en todas las
  // plataformas lo dispara <Confirmation> al montar (igual que funnels), leyendo
  // el UUID de Calendly y el schedule_event_id desde localStorage. Propagamos
  // event_id/journey_id por la URL para que la página de confirmación (otro entry)
  // conserve el mismo recorrido de tracking.
  const handleCalendlyScheduled = useCallback(() => {
    if (confirmationUrl) {
      const sep = confirmationUrl.includes('?') ? '&' : '?'
      const qs = new URLSearchParams({
        event_id: tracking.eventId,
        journey_id: tracking.journeyId,
      }).toString()
      window.location.href = `${confirmationUrl}${sep}${qs}`
      return
    }
    // Fallback: render in-SPA si el backend no proporcionó la URL.
    setPhase('confirmation')
    window.scrollTo({ top: 0, behavior: 'auto' })
  }, [confirmationUrl, tracking.eventId, tracking.journeyId])

  const submitResolver = async (finalRespuestas) => {
    setPhase('resolving')
    try {
      const result = await postResolver(slug, finalRespuestas, tracking.buildFullPayload())
      // Dispara el evento Lead en todas las plataformas (Meta/Google/GA4/TikTok)
      fireAllLead({
        eventId: tracking.eventId,
        journeyId: tracking.journeyId,
        email: finalRespuestas.email || '',
        phone: finalRespuestas.phone || '',
        name: finalRespuestas.name || '',
        schoolSlug: escuelaProp || escuela,
        fbp: tracking.pixelCookies._fbp || '',
        fbc: tracking.pixelCookies._fbc || '',
      })
      // Modo Calendly (fiel a producción): si el rango trae una URL de Calendly,
      // construye el widget con prefill + UTMs + utm_term de tracking.
      if (result.resultado === 'calendario' && result.calendly_url) {
        const body = {
          lead_name: result.prefill?.nombre || finalRespuestas.name || '',
          lead_email: result.prefill?.email || finalRespuestas.email || '',
          lead_phone_number: result.prefill?.telefono || finalRespuestas.phone || '',
          ...tracking.utmParams,
        }
        const params = buildCalendlyParams({
          body,
          monthValue: getYearMonthForCalendly(),
          journeyId: tracking.journeyId,
          scheduleEventId,
        })
        setCalendlyUrl(buildCalendlyUrl(result.calendly_url, params))
      }
      setOutcome(result)
      setPhase('outcome')
    } catch (e) {
      setLoadError(e.message)
      setPhase('error')
    }
  }

  // Global Enter handler for the welcome screen (questions handle Enter themselves)
  useEffect(() => {
    if (phase !== 'form' || !current || current.name !== 'welcome-screen') return
    const onKeyDown = (e) => {
      if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault()
        handleNext(null)
      }
    }
    window.addEventListener('keydown', onKeyDown)
    return () => window.removeEventListener('keydown', onKeyDown)
  }, [phase, current])

  useEffect(() => {
    if (!funnelFont) return
    const id = `gfont-${funnelFont.replace(/\s+/g, '-').toLowerCase()}`
    if (document.getElementById(id)) return
    const link = document.createElement('link')
    link.id = id
    link.rel = 'stylesheet'
    link.href = `https://fonts.googleapis.com/css2?family=${funnelFont.replace(/\s+/g, '+')}:wght@300;400;500;600;700&display=swap`
    document.head.appendChild(link)
  }, [funnelFont])

  // Brand theme (conquerblocks paperboard look, etc.) resolved from escuela,
  // falling back to the funnel slug ('blocks-eu' → conquerblocks).
  const theme = getTheme(escuela, slug)
  const pageStyle = {
    ...theme.cssVars,
    ...theme.page,
    ...(funnelFont ? { fontFamily: `'${funnelFont}', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif` } : {}),
  }

  if (phase === 'loading') {
    return <div className="loading-wrap">Cargando formulario...</div>
  }
  if (phase === 'error') {
    return <div className="error-wrap">Error: {loadError}</div>
  }
  if (phase === 'resolving') {
    return <div className="loading-wrap" style={pageStyle}>Procesando tus respuestas...</div>
  }

  if (phase === 'confirmation') {
    return <Confirmation escuela={escuelaProp || escuela} slug={slug} />
  }

  if (phase === 'outcome') {
    if (outcome.resultado === 'rechazado') {
      return <RejectScreen cancelScreen={outcome.cancel_screen} />
    }
    if (outcome.resultado === 'calendario') {
      // Modo Calendly: embebe el widget del rango (no usamos el calendario local aún).
      if (calendlyUrl) {
        return <CalendlyEmbed url={calendlyUrl} onScheduled={handleCalendlyScheduled} />
      }
      if (selectedSlot) {
        return (
          <BookingDetails
            slot={selectedSlot}
            prefill={outcome.prefill}
            eventoInfo={outcome.evento_info}
            prellamadaToken={outcome.prellamada_token}
            funnelSlug={slug}
            escuela={escuelaProp || escuela}
            onBack={() => setSelectedSlot(null)}
          />
        )
      }
      return (
        <Calendar
          hostSlug={outcome.host_slug}
          eventTypeSlug={outcome.event_type_slug}
          eventoInfo={outcome.evento_info}
          onSlotSelected={setSelectedSlot}
        />
      )
    }
  }

  const isWelcome = current?.name === 'welcome-screen'
  const isLast = currentIndex === blocks.length - 1

  const welcomeField = current
    ? {
        label: current.attributes?.label,
        description: current.attributes?.description,
        buttonText: current.attributes?.buttonText,
      }
    : {}

  const renderStep = () => {
    if (!current) return null
    if (isWelcome) {
      return <WelcomeScreen field={welcomeField} onNext={handleNext} />
    }
    return (
      <FormStep
        key={current.id}
        block={current}
        value={respuestas[current.id] || ''}
        onChange={handleChange}
        onNext={handleNext}
        onBack={handleBack}
        messages={messages}
        stepNumber={currentIndex}
        isFirst={currentIndex <= 1}
        isLast={isLast}
      />
    )
  }

  return (
    <ThemeContext.Provider value={theme}>
      <div className="funnel-wrap" style={pageStyle}>
        <div
          className="px-8 sm:px-16 py-10 rounded-2xl overflow-hidden mx-auto min-h-[80vh]"
          style={{
            width: 'calc(90vw - 2rem)',
            backgroundImage: `linear-gradient(var(--theme-form-bg, transparent), var(--theme-form-bg, transparent)), var(--theme-form-texture, none)`,
            backgroundSize: 'cover',
            backgroundPosition: 'center',
            border: `1px solid var(--theme-form-border, transparent)`,
            boxShadow: 'var(--theme-form-shadow, none)',
          }}
        >
          {!isWelcome && <ProgressBar progress={progress} />}
          <div className="mt-8">
            <StepTransition stepKey={currentIndex} direction={direction}>
              {renderStep()}
            </StepTransition>
          </div>
        </div>
      </div>
    </ThemeContext.Provider>
  )
}
