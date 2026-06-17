import React from 'react'

export default function RejectScreen({ cancelScreen, theme, funnelFont }) {
  const titulo = cancelScreen?.titulo || 'No cumples los requisitos en este momento'
  const mensaje = cancelScreen?.mensaje || 'Gracias por tu interés. En este momento no podemos atenderte.'
  const ctaUrl = cancelScreen?.cta_url
  const ctaTexto = cancelScreen?.cta_texto || 'Más información'

  // Misma variante "paperboard" que <Calendar>/<BookingDetails>: dentro de un
  // funnel con tema de marca adopta su línea de diseño; fuera, look genérico.
  const paperboard = !!theme?.paperboard
  const brandLogo = theme?.assets?.logo
  const wrapStyle = paperboard && funnelFont
    ? { fontFamily: `'${funnelFont}', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif` }
    : undefined

  return (
    <div className={`reject-wrap${paperboard ? ' reject-paperboard' : ''}`} style={wrapStyle}>
      {paperboard && brandLogo && <img className="bk-brand-logo" src={brandLogo} alt="" />}
      <div className="reject-card">
        <h2 className="reject-title">{titulo}</h2>
        <p className="reject-msg">{mensaje}</p>
        {ctaUrl && (
          <a href={ctaUrl} className="reject-cta" target="_blank" rel="noopener noreferrer">
            {ctaTexto}
          </a>
        )}
      </div>
    </div>
  )
}
