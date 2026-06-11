import { safeHtml } from '../../lib/sanitize'
import { CB_CARD_SHADOW } from '../../themes/conquerblocks'

const DEFAULT_BULLETS = [
  'Clase 100% gratuita y online',
  'Sin compromiso de compra',
  'Aprende de profesionales del sector',
]

export default function BulletPoints({ formConfig, theme }) {
  const landing = formConfig?.landing || formConfig?.welcome || {}
  const bullets = landing.bullets || DEFAULT_BULLETS
  const t = theme.landing.bullets
  const isPaper = !!theme.paperboard

  // Paperboard (Blocks/Legal): filas a ancho completo con textura paperboard
  // (overlay blanco 0.6) y sombra suave en capas, icono 48px + texto 16px.
  if (isPaper) {
    const bulletIcons = theme.assets?.bulletIcons || []
    const iconSize = t?.iconSize || '48px'
    const strongWeight = t?.strongWeight || '600'
    const cardStyle = {
      backgroundColor: '#F6F6F6',
      backgroundImage: theme.assets?.paperboardTexture
        ? `linear-gradient(rgba(255,255,255,0.6), rgba(255,255,255,0.6)), url(${theme.assets.paperboardTexture})`
        : undefined,
      backgroundSize: 'cover',
      backgroundPosition: 'center',
      boxShadow: CB_CARD_SHADOW,
    }

    return (
      <div className="flex flex-col gap-2">
        {bullets.map((item, i) => {
          const iconSrc = bulletIcons[i % bulletIcons.length]
          return (
            <div
              key={i}
              className="flex items-center gap-4 px-3 py-2 rounded-2xl border border-cb-line overflow-hidden"
              style={cardStyle}
            >
              {iconSrc && (
                <img src={iconSrc} alt="" className="flex-shrink-0 object-contain" style={{ width: iconSize, height: iconSize }} />
              )}
              <p
                className="text-base font-light text-cb-ink leading-[1.25] [&_strong]:[font-weight:var(--bw)]"
                style={{ '--bw': strongWeight }}
                dangerouslySetInnerHTML={safeHtml(item)}
              />
            </div>
          )
        })}
      </div>
    )
  }

  return (
    <ul className="space-y-3">
      {bullets.map((item, i) => (
        <li key={i} className={`flex items-start gap-3 ${t.text} text-base leading-relaxed`}>
          <div className={`flex-shrink-0 w-6 h-6 rounded-full ${t.checkBg} flex items-center justify-center`}>
            <svg className={`w-3.5 h-3.5 ${t.checkIcon}`} fill="currentColor" viewBox="0 0 20 20">
              <path fillRule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clipRule="evenodd" />
            </svg>
          </div>
          <span dangerouslySetInnerHTML={safeHtml(item)} />
        </li>
      ))}
    </ul>
  )
}
