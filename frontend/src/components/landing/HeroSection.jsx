import { safeHtml } from '../../lib/sanitize'

export default function HeroSection({ formConfig, theme }) {
  const landing = formConfig?.landing || formConfig?.welcome || {}
  const subtitle = landing.subtitle || ''
  const title = landing.title || 'Sesion de Consultoria Gratuita'
  const description = landing.description || ''
  const t = theme.landing.hero
  const isCB = theme.id === 'conquerblocks'
  const tape = theme.assets?.tape1

  // CB: réplica de producción — badge pill + título h5 (24px) + descripción.
  // Convención del título: <strong> = degradado naranja; <strong><em> = negro en negrita.
  if (isCB) {
    return (
      <div className="text-center flex flex-col items-center gap-5">
        {subtitle && (
          <div className="inline-flex items-center gap-2 rounded-full border border-cb-line px-4 py-1 text-sm font-medium text-cb-ink shadow-[0_1px_2px_rgba(0,0,0,0.04)]">
            <svg className="w-2.5 h-2.5 fill-current" viewBox="0 0 24 24"><path d="M8 5v14l11-7z" /></svg>
            {subtitle}
          </div>
        )}
        <h1
          className="max-w-[820px] mx-auto text-[22px] md:text-2xl font-medium leading-[1.1] text-cb-ink [&_strong]:font-medium [&_strong]:[background-image:linear-gradient(135deg,#FF4000,#FF9800)] [&_strong]:bg-clip-text [&_strong]:text-transparent [&_em]:not-italic [&_em]:font-bold [&_em]:[-webkit-text-fill-color:#0A0A0A] [&_em]:[background-image:none]"
          dangerouslySetInnerHTML={safeHtml(title)}
        />
        {description && (
          <p className="max-w-[760px] mx-auto text-base font-light text-cb-ink leading-[1.35]">
            {description}
          </p>
        )}
      </div>
    )
  }

  return (
    <div>
      {subtitle && (
        <div className="mb-2 lg:mb-3 inline-block relative">
          {tape && (
            <img
              src={tape}
              alt=""
              className="absolute inset-0 w-full h-full object-cover opacity-80 pointer-events-none"
            />
          )}
          <p className={`relative text-[11px] md:text-xs font-bold tracking-[0.25em] uppercase ${t.subtitle}`}>
            {subtitle}
          </p>
        </div>
      )}
      <h1
        className={`text-lg md:text-2xl lg:text-[1.7rem] xl:text-[2rem] font-bold leading-snug [&_br]:hidden md:[&_br]:inline [&_em]:italic ${t.title}`}
        dangerouslySetInnerHTML={safeHtml(title)}
      />
      {description && (
        <p className={`hidden md:block text-sm lg:text-base ${t.description} leading-relaxed mt-3 max-w-xl mx-auto lg:mx-0`}>
          {description}
        </p>
      )}
    </div>
  )
}
