import React, { useState } from 'react'
import { leer } from '../lib/safeStorage'
import { postReservar } from '../api'
import useTracking from '../hooks/useTracking'
import { fireAllSchedule } from '../lib/pixelEvents'
import { apiUrl } from '../lib/apiBase'

/** ISO en UTC → {fecha: 'lunes, 12 de mayo de 2026', hora: '17:30'} en la tz dada. */
function formatearEnTz(iso, tz) {
  if (!iso) return { fecha: '', hora: '' }
  const d = new Date(iso)
  if (isNaN(d)) return { fecha: '', hora: '' }
  const opts = tz ? { timeZone: tz } : {}
  try {
    return {
      fecha: new Intl.DateTimeFormat('es-ES', {
        weekday: 'long', day: 'numeric', month: 'long', year: 'numeric', ...opts,
      }).format(d),
      hora: new Intl.DateTimeFormat('es-ES', {
        hour: '2-digit', minute: '2-digit', hour12: false, ...opts,
      }).format(d),
    }
  } catch {
    // tz inválida (no debería): se cae a la del navegador antes que romper.
    return formatearEnTz(iso, '')
  }
}

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

export default function BookingDetails({ slot, prefill, eventoInfo, prellamadaToken, funnelSlug, escuela = '', theme, onBack, onBooked }) {
  const tracking = useTracking()
  // Diseño ÚNICO estandarizado (look Calendly) para todas las marcas. El color
  // de acento sigue a la marca vía los tokens --theme-* que consume .bk-wrapper.
  const [nombre, setNombre] = useState(prefill?.nombre || '')
  const [email, setEmail] = useState(prefill?.email || '')
  const [telefono, setTelefono] = useState(prefill?.telefono || '')
  const [notas, setNotas] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  // Duplicado (el evento tiene "solo una reserva por invitado" y este email ya
  // tiene una futura): guardamos la reserva vieja para ofrecer reemplazarla,
  // igual que el modal de la página pública.
  const [duplicado, setDuplicado] = useState(null)
  // Caja de comentarios configurable por tipo de evento. Si el backend no manda
  // el flag (respuesta vieja en caché), se muestra: el default es mostrarla.
  const mostrarNotas = eventoInfo?.mostrar_caja_comentarios !== false

  const reservar = async (reemplazarToken = '') => {
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
        // Mismo id de Schedule que usa el píxel (dedup CAPI/CRM, como el viejo).
        schedule_event_id: leer('cqx_schedule_event_id') || '',
        nombre: nombre.trim(),
        email: email.trim(),
        telefono: telefono.trim(),
        notas: notas.trim(),
        ...(reemplazarToken ? { reemplazar_token: reemplazarToken } : {}),
      })
      if (result.ok) {
        // Dentro de un funnel: llevar a SU página de confirmación (el evento
        // Schedule lo dispara <Confirmation> al montar, no aquí). Sin funnel
        // (uso suelto): disparar Schedule y caer en la confirmación por-evento.
        if (onBooked) {
          onBooked(result)
        } else {
          fireAllSchedule({
            eventId: tracking.eventId,
            journeyId: tracking.journeyId,
            schoolSlug: escuela,
            calendlyEventUuid: '',
            scheduleEventId: leer('cqx_schedule_event_id') || '',
          })
          if (eventoInfo?.confirmacion_tipo === 'url' && eventoInfo?.confirmacion_url) {
            window.location.href = eventoInfo.confirmacion_url
          } else {
            window.location.href = apiUrl(`/r/${result.confirmacion_token}/`)
          }
        }
      } else if (result.error === 'duplicado' && result.reserva_existente) {
        // No es un error: se le ofrece cancelar la vieja y quedarse con esta,
        // que es justo lo que necesita quien se equivocó de hora.
        setDuplicado(result.reserva_existente)
      } else {
        setDuplicado(null)
        setError(result.mensaje || 'Error al crear la reserva. Inténtalo de nuevo.')
      }
    } catch {
      setError('Error de conexión. Inténtalo de nuevo.')
    } finally {
      setLoading(false)
    }
  }

  const handleSubmit = (e) => {
    e.preventDefault()
    reservar()
  }

  // La reserva vieja se muestra en la MISMA zona horaria que el visitante eligió
  // para ver los slots, para que pueda comparar las dos horas sin traducir nada.
  const fechaVieja = formatearEnTz(duplicado?.inicio_utc, slot.tz)

  return (
    <div className={`bk-wrapper ${theme?.hexboard ? 'bk-wrapper--plain' : ''}`}>
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
              {mostrarNotas && (
                <div>
                  <label className="bk-label" htmlFor="bd-notas">Notas (opcional)</label>
                  <textarea id="bd-notas" className="bk-input" rows={3}
                    style={{ resize: 'vertical' }}
                    value={notas} onChange={e => setNotas(e.target.value)} />
                </div>
              )}
              <button type="submit" className="bk-submit" disabled={loading}>
                {loading ? 'Reservando…' : 'Confirmar reserva'}
              </button>
            </div>
          </form>
        </div>
      </div>

      {duplicado && (
        <div className="bk-modal-backdrop" onClick={() => setDuplicado(null)}>
          <div className="bk-modal" role="dialog" aria-modal="true"
            aria-labelledby="bd-modal-title" onClick={e => e.stopPropagation()}>
            <h3 id="bd-modal-title">Ya tienes una reserva</h3>
            <p>
              Detectamos que ya tienes una reserva confirmada
              {duplicado.event_type_nombre ? <> para <strong>{duplicado.event_type_nombre}</strong></> : null}:
            </p>
            <div className="bk-modal-existing">
              <strong>{fechaVieja.fecha}</strong><br />
              <strong>{fechaVieja.hora} h</strong>
              {duplicado.host ? <> &middot; con {duplicado.host}</> : null}
            </div>
            <p>
              ¿Quieres <strong>cancelar esa reserva</strong> y agendar esta nueva para
              el <strong>{slot.fechaDisplay} a las {slot.label}</strong>?
            </p>
            <div className="bk-modal-actions">
              <button type="button" className="bk-modal-btn cancel"
                onClick={() => setDuplicado(null)} disabled={loading}>
                No, volver
              </button>
              <button type="button" className="bk-modal-btn primary" disabled={loading}
                onClick={() => reservar(duplicado.confirmacion_token)}>
                {loading ? 'Reservando…' : 'Sí, cancelar y agendar nueva'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
