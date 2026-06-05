import React, { useState, useEffect, useRef } from 'react'
import { fetchConfig, postResolver } from './api'
import FormStep from './components/FormStep'
import Calendar from './components/Calendar'
import BookingDetails from './components/BookingDetails'
import RejectScreen from './components/RejectScreen'
import './funnel.css'

export default function Funnel({ slug }) {
  const [blocks, setBlocks] = useState([])
  const [messages, setMessages] = useState({})
  const [currentIndex, setCurrentIndex] = useState(0)
  const [respuestas, setRespuestas] = useState({})
  const [phase, setPhase] = useState('loading')
  const [outcome, setOutcome] = useState(null)
  const [selectedSlot, setSelectedSlot] = useState(null)
  const [loadError, setLoadError] = useState('')
  const formStepRef = useRef(null)

  useEffect(() => {
    fetchConfig(slug)
      .then(data => {
        setBlocks(data.blocks || [])
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

    if (currentIndex < blocks.length - 1) {
      setCurrentIndex(i => i + 1)
    } else {
      submitResolver(updated)
    }
  }

  const handleBack = () => setCurrentIndex(i => Math.max(0, i - 1))

  // Called by the bottom ↓ button
  const handleBottomNext = () => {
    const value = formStepRef.current?.validateAndGetValue()
    if (value !== null && value !== undefined) {
      handleNext(value)
    }
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

  if (phase === 'loading') {
    return <div className="loading-wrap">Cargando formulario...</div>
  }
  if (phase === 'error') {
    return <div className="error-wrap">Error: {loadError}</div>
  }
  if (phase === 'resolving') {
    return <div className="loading-wrap">Procesando tus respuestas...</div>
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

  const showBottomNav = currentIndex > 0

  return (
    <div className="funnel-wrap">
      <div className="funnel-body">
        {current && (
          <FormStep
            key={current.id}
            ref={formStepRef}
            block={current}
            value={respuestas[current.id] || ''}
            onChange={handleChange}
            onNext={handleNext}
            messages={messages}
          />
        )}
      </div>

      {showBottomNav && (
        <div className="bottom-nav">
          <div className="bottom-progress">
            <span className="progress-label">{progress}% completado</span>
            <div className="progress-track">
              <div className="progress-fill" style={{ width: `${progress}%` }} />
            </div>
          </div>
          <div className="nav-arrows">
            <button className="nav-arrow-btn" type="button" onClick={handleBack} aria-label="Anterior">
              <svg stroke="currentColor" strokeWidth="0" viewBox="0 0 20 20" xmlns="http://www.w3.org/2000/svg" fill="#fff">
                <path fillRule="evenodd" d="M14.707 12.707a1 1 0 01-1.414 0L10 9.414l-3.293 3.293a1 1 0 01-1.414-1.414l4-4a1 1 0 011.414 0l4 4a1 1 0 010 1.414z" clipRule="evenodd" />
              </svg>
            </button>
            <button className="nav-arrow-btn" type="button" onClick={handleBottomNext} aria-label="Siguiente">
              <svg stroke="currentColor" strokeWidth="0" viewBox="0 0 20 20" xmlns="http://www.w3.org/2000/svg" fill="#fff">
                <path fillRule="evenodd" d="M5.293 7.293a1 1 0 011.414 0L10 10.586l3.293-3.293a1 1 0 111.414 1.414l-4 4a1 1 0 01-1.414 0l-4-4a1 1 0 010-1.414z" clipRule="evenodd" />
              </svg>
            </button>
          </div>
        </div>
      )}
    </div>
  )
}
