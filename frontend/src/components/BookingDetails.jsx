import React, { useState } from 'react'
import { postReservar } from '../api'
import useTracking from '../hooks/useTracking'
import { fireAllSchedule } from '../lib/pixelEvents'

function LeftPanel({ eventoInfo }) {
  return (
    <div className="bk-left">
      <h1 className="bk-title">{eventoInfo?.nombre || 'Consultoría'}</h1>
      {eventoInfo?.duracion_minutos && (
        <div className="bk-meta">
          <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/>
          </svg>
          {eventoInfo.duracion_minutos} min
        </div>
      )}
      {eventoInfo?.precio && (
        <div className="bk-meta">
          <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <line x1="12" y1="1" x2="12" y2="23"/><path d="M17 5H9.5a3.5 3.5 0 0 0 0 7h5a3.5 3.5 0 0 1 0 7H6"/>
          </svg>
          {eventoInfo.precio} EUR
        </div>
      )}
      {eventoInfo?.descripcion && (
        <div className="bk-desc" dangerouslySetInnerHTML={{ __html: eventoInfo.descripcion }} />
      )}
    </div>
  )
}

export default function BookingDetails({ slot, prefill, eventoInfo, prellamadaToken, funnelSlug, escuela = '', onBack }) {
  const tracking = useTracking()
  const [nombre, setNombre] = useState(prefill?.nombre || '')
  const [email, setEmail] = useState(prefill?.email || '')
  const [telefono, setTelefono] = useState(prefill?.telefono || '')
  const [notas, setNotas] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  const handleSubmit = async (e) => {
    e.preventDefault()
    if (!nombre.trim() || !email.trim()) {
      setError('Nombre y email son obligatorios.')
      return
    }
    setLoading(true)
    setError('')
    try {
      const result = await postReservar(funnelSlug, {
        prellamada_token: prellamadaToken,
        inicio_utc: slot.utc,
        tz: slot.tz,
        nombre: nombre.trim(),
        email: email.trim(),
        telefono: telefono.trim(),
        notas: notas.trim(),
      })
      if (result.ok) {
        // Dispara el evento Schedule en todas las plataformas antes del redirect
        fireAllSchedule({
          eventId: tracking.eventId,
          journeyId: tracking.journeyId,
          schoolSlug: escuela,
          calendlyEventUuid: '',
          scheduleEventId: (typeof localStorage !== 'undefined' && localStorage.getItem('cqx_schedule_event_id')) || '',
        })
        window.location.href = `/r/${result.confirmacion_token}/`
      } else {
        setError(result.mensaje || 'Error al crear la reserva. Inténtalo de nuevo.')
      }
    } catch {
      setError('Error de conexión. Inténtalo de nuevo.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="bk-wrapper">
      <div className="bk-card">
        <LeftPanel eventoInfo={eventoInfo} />

        <div className="bk-right" style={{ display: 'flex', flexDirection: 'column' }}>
          <button type="button" className="bk-back" onClick={onBack}>
            <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
              <polyline points="15 18 9 12 15 6"/>
            </svg>
            Atrás
          </button>

          <div className="bk-slot-badge">
            🕐 <strong>{slot.label}</strong> — {slot.fechaDisplay}
            {eventoInfo?.duracion_minutos && <> &middot; {eventoInfo.duracion_minutos} min</>}
          </div>

          {error && <div className="bk-error">{error}</div>}

          <form onSubmit={handleSubmit}>
            <div className="bk-fields">
              <div>
                <label className="bk-label" htmlFor="bd-nombre">Nombre *</label>
                <input id="bd-nombre" type="text" className="bk-input"
                  required minLength={2} autoComplete="name"
                  value={nombre} onChange={e => setNombre(e.target.value)} />
              </div>
              <div>
                <label className="bk-label" htmlFor="bd-email">Email *</label>
                <input id="bd-email" type="email" className="bk-input"
                  required autoComplete="email"
                  value={email} onChange={e => setEmail(e.target.value)} />
              </div>
              <div>
                <label className="bk-label" htmlFor="bd-telefono">Teléfono</label>
                <input id="bd-telefono" type="tel" className="bk-input"
                  autoComplete="tel"
                  value={telefono} onChange={e => setTelefono(e.target.value)} />
              </div>
              <div>
                <label className="bk-label" htmlFor="bd-notas">Notas (opcional)</label>
                <textarea id="bd-notas" className="bk-input" rows={3}
                  style={{ resize: 'vertical' }}
                  value={notas} onChange={e => setNotas(e.target.value)} />
              </div>
              <button type="submit" className="bk-submit" disabled={loading}>
                {loading ? 'Reservando…' : 'Confirmar reserva'}
              </button>
            </div>
          </form>
        </div>
      </div>
    </div>
  )
}
