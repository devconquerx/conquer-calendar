import React, { useState, useEffect } from 'react'
import { fetchConfig, postResolver } from './api'
import FormStep from './components/FormStep'
import Calendar from './components/Calendar'
import BookingDetails from './components/BookingDetails'
import RejectScreen from './components/RejectScreen'
import ProgressBar from './components/form-engine/ProgressBar'
import StepTransition from './components/form-engine/StepTransition'
import WelcomeScreen from './components/form-engine/fields/WelcomeScreen'
import { getTheme, ThemeContext } from './themes'
import './funnel.css'

export default function Funnel({ slug }) {
  const [blocks, setBlocks] = useState([])
  const [escuela, setEscuela] = useState('')
  const [messages, setMessages] = useState({})
  const [currentIndex, setCurrentIndex] = useState(0)
  const [direction, setDirection] = useState('forward')
  const [respuestas, setRespuestas] = useState({})
  const [phase, setPhase] = useState('loading')
  const [outcome, setOutcome] = useState(null)
  const [selectedSlot, setSelectedSlot] = useState(null)
  const [loadError, setLoadError] = useState('')

  useEffect(() => {
    fetchConfig(slug)
      .then(data => {
        setBlocks(data.blocks || [])
        setEscuela(data.escuela || '')
        setMessages(data.messages || {})
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

  const handleNext = (value) => {
    if (!current) return
    const updated =
      current.id !== 'welcome' && value !== null
        ? { ...respuestas, [current.id]: value }
        : { ...respuestas }
    setRespuestas(updated)

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

  const submitResolver = async (finalRespuestas) => {
    setPhase('resolving')
    try {
      const result = await postResolver(slug, finalRespuestas)
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

  // Brand theme (conquerblocks paperboard look, etc.) resolved from escuela,
  // falling back to the funnel slug ('blocks-eu' → conquerblocks).
  const theme = getTheme(escuela, slug)
  const pageStyle = { ...theme.cssVars, ...theme.page }

  if (phase === 'loading') {
    return <div className="loading-wrap">Cargando formulario...</div>
  }
  if (phase === 'error') {
    return <div className="error-wrap">Error: {loadError}</div>
  }
  if (phase === 'resolving') {
    return <div className="loading-wrap" style={pageStyle}>Procesando tus respuestas...</div>
  }

  if (phase === 'outcome') {
    if (outcome.resultado === 'rechazado') {
      return <RejectScreen cancelScreen={outcome.cancel_screen} />
    }
    if (outcome.resultado === 'calendario') {
      if (selectedSlot) {
        return (
          <BookingDetails
            slot={selectedSlot}
            prefill={outcome.prefill}
            eventoInfo={outcome.evento_info}
            prellamadaToken={outcome.prellamada_token}
            funnelSlug={slug}
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
