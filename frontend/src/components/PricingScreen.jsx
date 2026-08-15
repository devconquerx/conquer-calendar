import React, { useState } from 'react'
import CalendlyEmbed from './CalendlyEmbed'

/**
 * Pantalla de transparencia de precio para leads descalificados con
 * alternativa de agendar igual (`config.calendlys_for_cancelled` del funnel).
 * Réplica de `renderPricingScreen`/`handleCancelledUser` de
 * conquerx-funnels-new/src/components/MainForm.jsx — hoy solo la usa Conquer
 * Blocks US (`blocks_us.json`); el resto de funnels sigue viendo <RejectScreen>.
 */
export default function PricingScreen({ price, calendlyUrl, theme, funnelFont, onScheduled }) {
  const [stage, setStage] = useState('offer') // 'offer' | 'declined' | 'calendar'

  if (stage === 'calendar') {
    return <CalendlyEmbed url={calendlyUrl} onScheduled={onScheduled} />
  }

  const paperboard = !!theme?.paperboard
  const brandLogo = theme?.assets?.logo
  const wrapStyle = paperboard && funnelFont
    ? { fontFamily: `'${funnelFont}', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif` }
    : undefined

  return (
    <div className={`reject-wrap${paperboard ? ' reject-paperboard' : ''}`} style={wrapStyle}>
      {paperboard && brandLogo && <img className="bk-brand-logo" src={brandLogo} alt="" />}
      <div className="reject-card">
        {stage === 'offer' ? (
          <>
            <p className="reject-msg">
              Para asegurarnos de que esta llamada sea de máximo valor para ti y no hacerte perder el tiempo,
              nos gusta ser 100% transparentes desde el principio. Nuestros servicios requieren una inversión
              a partir de <strong>{price}</strong>.
            </p>
            <p className="reject-msg">Este precio se puede pagar a cuotas durante un periodo máximo de 12 meses.</p>
            <p className="reject-msg">
              Si estás en el momento adecuado para hacer esta inversión en ti, haz clic en el botón de abajo
              para entrar a nuestro calendario y agendar una cita.
            </p>
            <div className="pricing-cta-row">
              <button type="button" className="pricing-cta pricing-cta-no" onClick={() => setStage('declined')}>
                No puedo hacer esa inversión
              </button>
              <button type="button" className="pricing-cta pricing-cta-yes" onClick={() => setStage('calendar')}>
                Sí puedo hacer esa inversión, agendar mi cita
              </button>
            </div>
          </>
        ) : (
          <p className="reject-msg">
            Gracias por tu honestidad y tu tiempo. En ese caso, no podremos ayudarte. Te deseamos mucho éxito
            y te recomendamos seguirnos en redes sociales, si en el futuro tu situación cambia, no dudes en
            volver a agendar una llamada y estaremos encantados de ayudarte. ¡Un saludo!
          </p>
        )}
      </div>
    </div>
  )
}
