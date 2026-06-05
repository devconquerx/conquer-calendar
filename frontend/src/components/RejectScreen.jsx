import React from 'react'

export default function RejectScreen({ cancelScreen }) {
  const titulo = cancelScreen?.titulo || 'No cumples los requisitos en este momento'
  const mensaje = cancelScreen?.mensaje || 'Gracias por tu interés. En este momento no podemos atenderte.'
  const ctaUrl = cancelScreen?.cta_url
  const ctaTexto = cancelScreen?.cta_texto || 'Más información'

  return (
    <div className="reject-wrap">
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
