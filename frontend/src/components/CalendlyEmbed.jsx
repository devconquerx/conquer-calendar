import React, { useEffect, useRef, useState } from 'react'
import { getCalendlyWidgetLayout, extractCalendlyEventUuid } from '../lib/calendly'

const WIDGET_SRC = 'https://assets.calendly.com/assets/external/widget.js'

/**
 * Widget inline de Calendly (port de renderCalendlyWidget de funnels-new).
 * Inyecta widget.js, bloquea el scroll del body en móvil y captura el UUID
 * del evento agendado (postMessage) en localStorage para tracking.
 */
export default function CalendlyEmbed({ url, onScheduled }) {
  const containerRef = useRef(null)
  const [loading, setLoading] = useState(true)
  const layout = getCalendlyWidgetLayout(
    typeof window !== 'undefined' ? window.innerWidth : 1024
  )

  useEffect(() => {
    if (layout.shouldLockScroll) {
      document.body.style.overflow = 'hidden'
      document.documentElement.style.overflow = 'hidden'
    }
    window.scrollTo({ top: 0, behavior: 'smooth' })

    const done = () => setTimeout(() => setLoading(false), 1500)
    const existing = document.querySelector(`script[src="${WIDGET_SRC}"]`)
    if (!existing) {
      const script = document.createElement('script')
      script.src = WIDGET_SRC
      script.async = true
      script.addEventListener('load', done)
      document.body.appendChild(script)
    } else if (window.Calendly && containerRef.current) {
      // widget.js ya cargado: inicializa este widget explícitamente.
      containerRef.current.innerHTML = ''
      window.Calendly.initInlineWidget({ url, parentElement: containerRef.current })
      done()
    } else {
      done()
    }

    const onMessage = (e) => {
      const uuid = extractCalendlyEventUuid(e)
      if (uuid) {
        try { localStorage.setItem('cqx_calendly_event_uuid', uuid) } catch (_) {}
        console.log('[Tracking] Calendly event UUID:', uuid)
        if (onScheduled) onScheduled(uuid)
      }
    }
    window.addEventListener('message', onMessage)

    return () => {
      window.removeEventListener('message', onMessage)
      document.body.style.overflow = ''
      document.documentElement.style.overflow = ''
    }
  }, [url])

  return (
    <div style={{ position: 'relative', minHeight: layout.sectionMinHeight }}>
      {loading && (
        <div
          style={{
            position: 'fixed',
            top: '50%',
            left: '50%',
            transform: 'translate(-50%, -50%)',
            zIndex: 9999,
          }}
        >
          <div className="calendly-loader" />
          <style>{`
            .calendly-loader {
              border: 16px solid #f3f3f3;
              border-top: 16px solid #000;
              border-radius: 50%;
              width: 120px;
              height: 120px;
              animation: calendly-spin 2s linear infinite;
            }
            @keyframes calendly-spin {
              0% { transform: rotate(0deg); }
              100% { transform: rotate(360deg); }
            }
          `}</style>
        </div>
      )}
      <div
        ref={containerRef}
        className="calendly-inline-widget"
        data-url={url}
        style={{ minWidth: '320px', width: '100%', height: layout.widgetHeight }}
      />
    </div>
  )
}
