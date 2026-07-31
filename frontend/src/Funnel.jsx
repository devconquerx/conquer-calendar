import React, { useState, useEffect, useRef, useMemo, useCallback } from 'react'
import { fetchConfig, postResolver, postReservar, sendPreSchedule } from './api'
import useTracking from './hooks/useTracking'
import { fireAllLead } from './lib/pixelEvents'
import FormStep from './components/FormStep'
import Calendar from './components/Calendar'
import BookingDetails from './components/BookingDetails'
import CalendlyEmbed from './components/CalendlyEmbed'
import Confirmation from './components/Confirmation'
import RejectScreen from './components/RejectScreen'
import { buildCalendlyParams, buildCalendlyUrl, getYearMonthForCalendly } from './lib/calendly'
import BottomNavBar from './components/form-engine/BottomNavBar'
import StepTransition from './components/form-engine/StepTransition'
import WelcomeScreen from './components/form-engine/fields/WelcomeScreen'
import { getPrefillRespuestas } from './lib/prefillParams'
import { validateBlock } from './lib/validateBlock'
import { getTheme, ThemeContext } from './themes'
import { useRouter } from './lib/router'
import './funnel.css'

export default function Funnel({ slug, escuela: escuelaProp = '', confirmationUrl = '', formConfig = null, search }) {
  // `search` lo inyecta el entry SSR (query string del request) para que el
  // prefill server == cliente y no haya hydration mismatch. En CSR cae a
  // window.location.search (comportamiento actual).
  const initialSearch = search ?? (typeof window !== 'undefined' ? window.location.search : '')
  const router = useRouter()
  const tracking = useTracking()
  // Config del formulario embebida en el shell (funnel-config): cuando está
  // presente, el StepForm se renderiza al instante sin pedir nada al servidor.
  // El fetch a /f/api/<slug>/config/ queda solo como fallback (dev standalone,
  // o si por algún motivo la config no viajó en el HTML).
  const embedded = formConfig && Array.isArray(formConfig.blocks) ? formConfig : null
  // Los pasos de contacto (name/email/phone) que llegan por la URL SÍ se muestran
  // en el StepForm, pero autorrellenados con el valor del query param (ese valor
  // se siembra en `respuestas`). No se ocultan: el lead ve y puede corregir sus
  // datos.
  // schedule_event_id del recorrido: se genera una vez al montar y se reutiliza
  // en el utm_term de Calendly y en fireAllSchedule (igual que el funnel de
  // Django, que lo genera en `trackingParams` al montar el form).
  const scheduleEventId = useMemo(() => {
    const id = tracking.generateScheduleEventId()
    if (typeof localStorage !== 'undefined') {
      try { localStorage.setItem('cqx_schedule_event_id', id) } catch (_) {}
    }
    return id
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])
  const [blocks, setBlocks] = useState(() => embedded ? (embedded.blocks || []) : [])
  const [escuela, setEscuela] = useState(embedded ? escuelaProp : '')
  const [messages, setMessages] = useState(() => embedded?.messages || {})
  const [funnelFont, setFunnelFont] = useState(() => embedded?.theme?.font || '')
  const [currentIndex, setCurrentIndex] = useState(0)
  const [direction, setDirection] = useState('forward')
  // Prefill desde el query string que propaga la landing (name/email/phone),
  // igual que el funnel de Django. Los ids de bloque son name/email/phone.
  const [respuestas, setRespuestas] = useState(() => getPrefillRespuestas(initialSearch))
  const [phase, setPhase] = useState(embedded ? 'form' : 'loading')
  const [outcome, setOutcome] = useState(null)
  const [selectedSlot, setSelectedSlot] = useState(null)
  // Reserva directa desde el funnel: al elegir hora se reserva con los datos
  // de la prellamada, sin re-pedirlos. 'booking' pinta el estado de espera;
  // si el intento directo falla, 'directBookingFailed' cae al formulario de
  // BookingDetails (prefillado) como fallback para reintentar/corregir.
  const [booking, setBooking] = useState(false)
  const [directBookingFailed, setDirectBookingFailed] = useState(false)
  const [calendlyUrl, setCalendlyUrl] = useState('')
  const [loadError, setLoadError] = useState('')

  useEffect(() => {
    // Con la config embebida ya tenemos los bloques: nada que pedir al servidor.
    if (embedded) return
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
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [slug])

  const current = blocks[currentIndex]

  // Progress counts from block 1 onward (block 0 = welcome screen)
  const totalSteps = blocks.length - 1
  const progress = totalSteps > 0 ? Math.round(((currentIndex) / totalSteps) * 100) : 0

  const currentValueFilled = current ? validateBlock(current, respuestas[current.id] || '') : false

  const handleChange = (value) => {
    if (!current) return
    setRespuestas(prev => ({ ...prev, [current.id]: value }))
  }

  // NOTA: el StepForm NO registra leads. El lead lo crea la landing (única
  // fuente, como en conquerx-funnels-new, donde el form solo alimentaba la
  // PreSchedule vía Make); aquí el visitante queda capturado igualmente por la
  // Prellamada progresiva (sendPreSchedule) desde que escribe su teléfono.
  // Antes había un re-registro aquí y cada recorrido creaba DOS LeadRegisters
  // en el CRM (el segundo con page_url=/agenda/...).

  const handleNext = (value) => {
    if (!current) return
    const updated =
      current.id !== 'welcome' && value !== null
        ? { ...respuestas, [current.id]: value }
        : { ...respuestas }
    setRespuestas(updated)

    setDirection('forward')
    if (currentIndex < blocks.length - 1) {
      // Pre-schedule progresivo: una vez capturado el teléfono, cada avance
      // crea/actualiza la Prellamada por journey_id (réplica del
      // submitForm(..., false) de conquerx-funnels-new). El submit del último
      // bloque la finaliza vía submitResolver. Fire-and-forget.
      if (updated.phone) {
        sendPreSchedule(slug, updated, tracking.buildFullPayload())
      }
      setCurrentIndex(i => i + 1)
    } else {
      submitResolver(updated)
    }
  }

  const handleBack = () => {
    setDirection('backward')
    setCurrentIndex(i => Math.max(0, i - 1))
  }

  // Al agendar en Calendly: navega a la página de Confirmación. El evento
  // Schedule en todas las plataformas lo dispara <Confirmation> al montar
  // (igual que funnels), leyendo el UUID de Calendly y el schedule_event_id
  // desde localStorage. Propagamos event_id/journey_id por la URL para que la
  // etapa de confirmación conserve el mismo recorrido de tracking.
  // Lleva a la página de confirmación del funnel (la misma para Calendly y para
  // el calendario nativo). El evento Schedule lo dispara <Confirmation> al
  // montar, así que aquí no se dispara (evita doble disparo).
  // Brand theme (conquerblocks paperboard look, etc.) resolved from escuela,
  // falling back to the funnel slug ('blocks-eu' → conquerblocks). Declarado
  // antes de goToConfirmation, que lo usa (y lo lista en sus deps).
  const theme = getTheme(escuela, slug)

  const goToConfirmation = useCallback(() => {
    const params = new URLSearchParams(window.location.search)
    params.set('event_id', tracking.eventId)
    params.set('journey_id', tracking.journeyId)
    // Compat con el contenedor GTM heredado de Webflow (Finance): sus variables
    // de Schedule leen el email de localStorage.calendly_email; lo dejamos
    // escrito antes de navegar para que enhanced conversions/CAPI lo lleven.
    const bookedEmail = outcome?.prefill?.email || params.get('email') || ''
    if (bookedEmail) {
      try { localStorage.setItem('calendly_email', bookedEmail) } catch (_) {}
    }
    const etUrl = outcome?.evento_info?.confirmacion_tipo === 'url' && outcome?.evento_info?.confirmacion_url
    if (etUrl) {
      if (router) {
        router.navigateRaw(etUrl, { search: `?${params.toString()}` })
        return
      }
      const sep = etUrl.includes('?') ? '&' : '?'
      window.location.href = `${etUrl}${sep}${params.toString()}`
      return
    }
    // Hexboard (Finance): navegación REAL a la confirmación, no pushState. El
    // contenedor GTM de Finance (era Webflow) dispara el Schedule (GA4/Meta/
    // Twitter) con el trigger "page load en *confirmacion-llamada*": dentro del
    // SPA ese page-load nunca ocurre y la conversión se pierde. Con la
    // recarga, el contenedor publicado funciona tal cual (verificado contra el
    // sGTM). Si algún día el contenedor pasa a escuchar `calendly_scheduled`,
    // este branch puede volver al router.navigate — no ambos, o duplicaría.
    // OJO: en el SPA la prop confirmationUrl no viaja (FunnelApp no la pasa);
    // la URL canónica de la etapa vive en router.urls.confirmation.
    const hardConfirmationUrl = confirmationUrl || router?.urls?.confirmation || ''
    if (theme?.hexboard && hardConfirmationUrl) {
      const sep = hardConfirmationUrl.includes('?') ? '&' : '?'
      window.location.href = `${hardConfirmationUrl}${sep}${params.toString()}`
      return
    }
    if (router) {
      router.navigate('confirmation', { search: `?${params.toString()}` })
      return
    }
    if (confirmationUrl) {
      const sep = confirmationUrl.includes('?') ? '&' : '?'
      window.location.href = `${confirmationUrl}${sep}${params.toString()}`
      return
    }
    setPhase('confirmation')
    window.scrollTo({ top: 0, behavior: 'auto' })
  }, [router, confirmationUrl, tracking.eventId, tracking.journeyId, outcome, theme])

  // Al elegir hora viniendo del funnel: los datos personales ya se pidieron en
  // el StepForm (viven en la Prellamada / outcome.prefill), así que se reserva
  // directo — fecha y hora son los únicos pasos del calendario. El formulario
  // de BookingDetails queda solo para el uso suelto del calendario (sin
  // prefill) y como fallback si la reserva directa falla.
  const handleSlotSelected = (slot) => {
    setSelectedSlot(slot)
    const prefill = outcome?.prefill || {}
    const canBookDirect = !directBookingFailed && prefill.email && prefill.nombre
    if (!canBookDirect) return
    setBooking(true)
    postReservar(slug, {
      prellamada_token: outcome.prellamada_token,
      inicio_utc: slot.utc,
      tz: slot.tz,
      nombre: (prefill.nombre || '').trim(),
      email: (prefill.email || '').trim(),
      telefono: (prefill.telefono || '').trim(),
      notas: '',
    })
      .then((result) => {
        if (result.ok) {
          goToConfirmation(result)
        } else {
          // Slot ocupado u otro rechazo: volver al formulario prefillado.
          setDirectBookingFailed(true)
          setBooking(false)
        }
      })
      .catch(() => {
        setDirectBookingFailed(true)
        setBooking(false)
      })
  }

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

  const pageStyle = {
    ...theme.cssVars,
    ...theme.page,
    ...(funnelFont ? { fontFamily: `'${funnelFont}', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif` } : {}),
  }

  // Publica las CSS vars del tema en :root. La barra inferior (BottomNavBar) y
  // otros elementos se renderizan FUERA de `.funnel-wrap`, así que necesitan que
  // las variables (--theme-btn-gradient, --theme-accent…) estén en el documento
  // para heredar el color de marca (azul Legal / naranja Blocks).
  useEffect(() => {
    const root = document.documentElement
    const vars = theme.cssVars || {}
    for (const [k, val] of Object.entries(vars)) root.style.setProperty(k, val)
    return () => {
      for (const k of Object.keys(vars)) root.style.removeProperty(k)
    }
  }, [theme])

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

  // Finance (hexboard): el StepForm de producción vive dentro del shell de la
  // página de vídeo — navbar oscuro (#333 de body, borde #4f4f4f, logo
  // invertido 180px) + sección blanca de ~75vh con el form + resto oscuro.
  // El shell NO se aplica al embed de Calendly (producción oculta navbar y
  // footer al abrir el widget).
  const hexShell = (children) => (
    <div className="min-h-[100dvh] flex flex-col" style={{ backgroundColor: '#333333' }}>
      <header className="h-[75px] md:h-[70px] flex-shrink-0 flex items-center justify-center border-b border-[#4f4f4f]">
        <img src={theme.assets?.logoInverted || theme.assets?.logo} alt="" className="w-[180px] h-auto" />
      </header>
      {/* La sección blanca crece y deja solo una franja oscura fija abajo. */}
      <div className="bg-white flex-1 flex flex-col">{children}</div>
      <div className="h-[80px] flex-shrink-0" aria-hidden="true" />
    </div>
  )

  if (phase === 'outcome') {
    if (outcome.resultado === 'rechazado') {
      const reject = <RejectScreen cancelScreen={outcome.cancel_screen} theme={theme} funnelFont={funnelFont} />
      return theme.hexboard ? hexShell(reject) : reject
    }
    if (outcome.resultado === 'calendario') {
      // Modo Calendly: embebe el widget del rango (no usamos el calendario local aún).
      if (calendlyUrl) {
        return <CalendlyEmbed url={calendlyUrl} onScheduled={goToConfirmation} />
      }
      if (selectedSlot && booking) {
        return (
          <div className="loading-wrap" style={pageStyle}>Confirmando tu reserva...</div>
        )
      }
      if (selectedSlot && (directBookingFailed || !(outcome.prefill?.email && outcome.prefill?.nombre))) {
        return (
          <BookingDetails
            slot={selectedSlot}
            prefill={outcome.prefill}
            eventoInfo={outcome.evento_info}
            prellamadaToken={outcome.prellamada_token}
            funnelSlug={slug}
            escuela={escuelaProp || escuela}
            theme={theme}
            funnelFont={funnelFont}
            onBack={() => setSelectedSlot(null)}
            onBooked={goToConfirmation}
          />
        )
      }
      return (
        <Calendar
          hostSlug={outcome.host_slug}
          eventTypeSlug={outcome.event_type_slug}
          eventoInfo={outcome.evento_info}
          theme={theme}
          funnelFont={funnelFont}
          onSlotSelected={handleSlotSelected}
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
      return <WelcomeScreen field={welcomeField} onNext={handleNext} theme={theme} />
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

  // Hexboard: el form no ocupa toda la altura (deja ver el fondo oscuro
  // debajo, como producción) y va anclado arriba, sin tarjeta.
  const formBody = (
    <div
      className="funnel-wrap"
      style={theme.hexboard
        // Hexboard: contenido (welcome y preguntas) centrado verticalmente
        // en la zona blanca.
        ? { ...pageStyle, minHeight: 'auto', flexGrow: 1, justifyContent: 'center' }
        : pageStyle}
    >
      <div
        className={`w-full grow sm:w-[calc(90vw_-_2rem)] sm:grow-0 px-4 min-[480px]:px-8 sm:px-16 py-10 mx-auto sm:rounded-2xl sm:border sm:shadow-[var(--theme-form-shadow,none)] ${theme.hexboard ? 'min-h-0 grow-0' : 'min-h-[100dvh] sm:min-h-[80vh]'}`}
        style={{
          borderColor: 'var(--theme-form-border, transparent)',
          backgroundImage: `linear-gradient(var(--theme-form-bg, transparent), var(--theme-form-bg, transparent)), var(--theme-form-texture, none)`,
          backgroundSize: 'cover',
          backgroundPosition: 'center',
        }}
      >
        <div className={`overflow-hidden ${theme.hexboard ? 'min-h-0' : 'mt-8 min-h-[60vh]'}`}>
          <StepTransition stepKey={currentIndex} direction={direction}>
            {renderStep()}
          </StepTransition>
        </div>
      </div>
    </div>
  )

  return (
    <ThemeContext.Provider value={theme}>
      {theme.hexboard ? hexShell(formBody) : formBody}

      {phase === 'form' && !isWelcome && (
        <BottomNavBar
          progress={progress}
          onUp={handleBack}
          onDown={() => handleNext(respuestas[current?.id] || '')}
          canGoUp={currentIndex > 1}
          canGoDown={!isLast && currentValueFilled}
          bottomOffset={theme.hexboard ? 80 : 0}
        />
      )}
    </ThemeContext.Provider>
  )
}
