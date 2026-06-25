import HeroSection from '../components/landing/HeroSection'
import LandingForm from '../components/landing/LandingForm'
import BulletPoints from '../components/landing/BulletPoints'
import { getTheme } from '../themes'
import { CB_CARD_SHADOW } from '../themes/conquerblocks'
import { safeHtml } from '../lib/sanitize'

export default function Landing({ school, program, region, formConfig, nextUrl, funnelSlug, videoEnabled = false }) {
  const theme = getTheme(school?.slug)
  const t = theme.landing
  const isPaper = !!theme.paperboard
  const assets = theme.assets

  const landing = formConfig?.landing || formConfig?.welcome || {}
  const instructor = landing.instructor
  const disclaimer = landing.disclaimer

  if (isPaper) {
    return <PaperboardLanding
      school={school} program={program} region={region}
      formConfig={formConfig} theme={theme} assets={assets}
      instructor={instructor} disclaimer={disclaimer}
      nextUrl={nextUrl} funnelSlug={funnelSlug} videoEnabled={videoEnabled}
    />
  }

  return <DefaultLanding
    school={school} program={program} region={region}
    formConfig={formConfig} theme={theme} t={t}
    instructor={instructor} disclaimer={disclaimer}
    nextUrl={nextUrl} funnelSlug={funnelSlug} videoEnabled={videoEnabled}
  />
}


/* ═══ Landing "paperboard" — réplica del sistema Webflow (Blocks / Legal) ═══
   Fondo casi blanco (#FAFAFA) con textura sutil, columna central de 1024px,
   tarjetas planas grises con borde arena, formulario con glow aurora animado.
   El acento de color (naranja Blocks / azul Legal) viene de `theme.accent`. */
function PaperboardLanding({ school, program, region, formConfig, theme, assets, instructor, disclaimer, nextUrl, funnelSlug, videoEnabled }) {
  const accent = theme.accent || {}
  const footer = theme.footer || {}
  // Ancho de la columna de contenido (réplica del `container-large` de Webflow:
  // 1280px en Legal, 1064px en Blocks). Inline porque Tailwind no genera clases
  // arbitrarias construidas en runtime.
  const contentWidth = theme.landing?.contentWidth || '1064px'
  // El px-5 (20px) se suma al ancho de columna para que las tarjetas lleguen al
  // ancho real de producción (container-large 1280/1064) en desktop, conservando
  // el padding lateral en móvil. Equivale al `padding-global` externo de Webflow.
  const columnMaxWidth = `calc(${contentWidth} + 40px)`
  const pageStyle = assets?.paperboardTexture ? {
    backgroundImage: `linear-gradient(rgba(255,255,255,0.55), rgba(255,255,255,0.55)), url(${assets.paperboardTexture})`,
    backgroundSize: 'cover',
    backgroundPosition: 'center',
    backgroundAttachment: 'fixed',
  } : undefined
  // Tarjetas: textura paperboard (overlay blanco 0.6 sobre #F6F6F6) + sombra en
  // capas de producción (inline para evitar el bug de color de Tailwind).
  const cardStyle = {
    backgroundColor: '#F6F6F6',
    backgroundImage: assets?.paperboardTexture
      ? `linear-gradient(rgba(255,255,255,0.6), rgba(255,255,255,0.6)), url(${assets.paperboardTexture})`
      : undefined,
    backgroundSize: 'cover',
    backgroundPosition: 'center',
    boxShadow: CB_CARD_SHADOW,
  }
  const instructorPhoto = assets?.instructorPhoto || instructor?.imageUrl
  // Borde pixelado: en móvil la tarjeta se apila (imagen arriba), así que el
  // borde va ABAJO; en desktop (md+) va a la DERECHA. Si el tema trae la máscara
  // inferior, `--imask` se conmuta por clases (`[--imask:bottom] md:[--imask:right]`
  // en la imagen): se hace por CLASE y NO inline, porque un estilo inline ganaría
  // siempre y el breakpoint md no podría sobreescribirlo. El volteo está dentro
  // del propio SVG.
  const maskRight = assets?.instructorMask ? `url(${assets.instructorMask})` : undefined
  const maskBottom = assets?.instructorMaskBottom ? `url(${assets.instructorMaskBottom})` : undefined
  const pixelMaskStyle = maskRight ? {
    WebkitMaskSize: '100% 100%',
    maskSize: '100% 100%',
    WebkitMaskRepeat: 'no-repeat',
    maskRepeat: 'no-repeat',
    ...(maskBottom ? {
      '--imask-right': maskRight,
      '--imask-bottom': maskBottom,
      WebkitMaskImage: 'var(--imask)',
      maskImage: 'var(--imask)',
    } : { WebkitMaskImage: maskRight, maskImage: maskRight }),
  } : undefined

  return (
    <div className="min-h-screen overflow-x-hidden relative flex flex-col font-funnel bg-cb-bg text-cb-ink" style={pageStyle}>
      {/* Pixeles decorativos (réplica de producción: 150px, opacidad 0.2).
          Posiciones definidas por theme; se alternan los dos SVG. */}
      {assets?.pixels?.deco && (theme.landing?.decoPixels || []).map((pos, i) => (
        <img
          key={i}
          src={(i % 2 && assets.pixels.deco2) ? assets.pixels.deco2 : assets.pixels.deco}
          alt=""
          aria-hidden="true"
          className={`hidden lg:block absolute w-[150px] opacity-20 pointer-events-none select-none ${pos}`}
        />
      ))}
      {/* Píxeles de fondo en móvil (réplica de producción) */}
      {(theme.landing?.decoPixelsMobile || []).map((p, i) => (
        <img
          key={`m${i}`}
          src={assets?.pixels?.[p.img]}
          alt=""
          aria-hidden="true"
          className={`lg:hidden absolute z-0 opacity-20 pointer-events-none select-none ${p.cls}`}
        />
      ))}
      <main className="relative z-10 flex-1 w-full mx-auto px-5 flex flex-col" style={{ maxWidth: columnMaxWidth }}>
        {/* Logo: imagen centrada (sin tarjeta) */}
        <div className="py-4 flex justify-center">
          <img src={assets.logo} alt={footer.copyrightBrand || 'Conquer'} className="w-auto" style={{ height: theme.landing?.logoHeight || '36px' }} />
        </div>

        {/* Hero: badge + título + descripción */}
        <div className="animate-fade-in">
          <HeroSection formConfig={formConfig} theme={theme} />
        </div>

        {/* Bullets */}
        <div className="mt-6 animate-fade-in">
          <BulletPoints formConfig={formConfig} theme={theme} />
        </div>

        {/* Formulario con glow aurora naranja animado por detrás */}
        <div className="relative mt-6 md:mt-10 animate-fade-in">
          <div className="absolute inset-0 rounded-2xl bg-[length:300%_300%] blur-[20px] animate-aurora" style={{ backgroundImage: accent.auroraGradient }} aria-hidden="true" />
          <div className="relative z-10 rounded-2xl border border-cb-line px-5 py-5 md:px-12 md:py-6" style={cardStyle}>
            <LandingForm
              program={program}
              region={region}
              formConfig={formConfig}
              school={school}
              nextUrl={nextUrl}
              funnelSlug={funnelSlug}
              videoEnabled={videoEnabled}
            />
          </div>
        </div>

        {/* Instructor */}
        {instructor && (
          <div className="mt-10 animate-fade-in rounded-2xl border border-cb-line overflow-hidden flex flex-col md:flex-row md:min-h-[426px]" style={cardStyle}>
            <div className="w-full aspect-square md:aspect-auto md:w-[426px] md:h-[426px] flex-shrink-0 self-start">
              {instructorPhoto && (
                <div
                  role="img"
                  aria-label={instructor.name}
                  className="w-full h-full bg-black bg-no-repeat [--imask:var(--imask-bottom)] md:[--imask:var(--imask-right)]"
                  style={{
                    ...pixelMaskStyle,
                    backgroundImage: `url(${instructorPhoto})`,
                    backgroundSize: assets?.instructorBgSize || 'cover',
                    backgroundPosition: assets?.instructorBgPosition || 'center top',
                  }}
                />
              )}
            </div>
            <div className="flex-1 p-6 md:p-12 flex flex-col justify-center">
              <h2 className="text-4xl md:text-[48px] font-semibold leading-[1.1] text-cb-ink2">
                {instructor.name}
              </h2>
              <div className="mt-7 text-sm md:text-base font-light text-cb-ink2 leading-[1.25]">
                {instructor.role && <p className="mb-4">{instructor.role}</p>}
                <p dangerouslySetInnerHTML={safeHtml(instructor.description)} />
              </div>
            </div>
          </div>
        )}
      </main>

      {/* Footer */}
      <footer className="w-full mx-auto px-5 mt-12 pb-10" style={{ maxWidth: columnMaxWidth }}>
        {disclaimer && (
          <p className="max-w-[90%] mx-auto text-xs font-light text-neutral-500 leading-[1.25] text-center">
            {disclaimer}
            {footer.contactEmail && ` Puedes contactarnos enviándonos un email a ${footer.contactEmail}`}
          </p>
        )}
        <div className="border-t border-[#404040] my-6" />
        <div className="flex flex-col md:flex-row justify-between items-center gap-4 text-xs font-light text-cb-ink2 leading-tight">
          <p className="text-center md:text-left">
            {footer.copyrightBrand || 'Conquer'} {new Date().getFullYear()} &reg; | ConquerX LLC | 16192 Coastal Highway, Lewes 19958, Delaware, USA
          </p>
          <div className="flex gap-4 flex-shrink-0 text-xs">
            <a href={footer.legal?.cookies} target="_blank" rel="noopener noreferrer" className="hover:text-cb-ink">Política de Cookies</a>
            <a href={footer.legal?.privacy} target="_blank" rel="noopener noreferrer" className="hover:text-cb-ink">Política de Privacidad</a>
            <a href={footer.legal?.terms} target="_blank" rel="noopener noreferrer" className="hover:text-cb-ink">Términos y Condiciones</a>
          </div>
        </div>
      </footer>
    </div>
  )
}


/* ═══ Default Theme Landing ═══ */
function DefaultLanding({ school, program, region, formConfig, theme, t, instructor, disclaimer, nextUrl, funnelSlug, videoEnabled }) {
  return (
    <div className={`min-h-screen overflow-x-hidden ${t.bg} relative flex flex-col`}>
      <div className={`absolute inset-0 ${t.dotPattern}`} />
      <div className={`absolute top-1/2 right-[20%] -translate-y-1/2 w-[600px] h-[600px] ${t.ambientGlow} rounded-full blur-[150px] pointer-events-none hidden lg:block`} />

      <header className="relative px-5 lg:px-12 py-3 lg:py-4 flex-shrink-0 z-10">
        {school?.logoUrl ? (
          <img src={school.logoUrl} alt={school.name} className={`h-7 lg:h-9 ${t.logoFilter}`} />
        ) : (
          <span className={`text-lg lg:text-2xl font-bold ${t.logoFallbackText} tracking-tight`}>
            {school?.name || 'ConquerX'}
          </span>
        )}
      </header>

      <main className="relative flex-1 flex items-center py-6 lg:py-0 justify-center px-4 lg:px-8 xl:px-12 z-10">
        <div className="w-full mx-auto max-w-6xl">
          <div className="flex flex-col lg:flex-row items-stretch gap-6 lg:gap-8">
            <div className="flex-1 text-center lg:text-left animate-fade-in">
              <HeroSection formConfig={formConfig} theme={theme} />
              <div className="hidden lg:block mt-6">
                <BulletPoints formConfig={formConfig} theme={theme} />
              </div>
            </div>

            <div className="w-full max-w-sm lg:w-[420px] flex-shrink-0 animate-fade-in relative">
              <div className={`rounded-2xl p-5 lg:p-7 border relative h-full flex flex-col justify-center ${t.form.card}`}>
                <div className="text-center mb-5">
                  <div className="inline-block relative mb-3">
                    <div className={`relative inline-flex items-center gap-2 ${t.form.badge} text-[11px] font-semibold px-3 py-1 rounded-full`}>
                      <span className={`w-1.5 h-1.5 ${t.form.badgeDot} rounded-full animate-pulse`} />
                      Plazas limitadas
                    </div>
                  </div>
                  <h2 className={`text-xl font-bold ${t.form.title}`}>
                    Reserva tu plaza ahora
                  </h2>
                </div>
                <LandingForm
                  program={program}
                  region={region}
                  formConfig={formConfig}
                  school={school}
                  nextUrl={nextUrl}
                  funnelSlug={funnelSlug}
                  videoEnabled={videoEnabled}
                />
              </div>
            </div>
          </div>

          {instructor && (
            <div className={`hidden lg:flex items-center gap-6 mt-6 rounded-xl p-6 border animate-fade-in ${t.instructor.card}`}>
              <img
                src={instructor.imageUrl}
                alt={instructor.name}
                className={`w-24 h-24 rounded-full object-cover flex-shrink-0 ring-2 ${t.instructor.ring}`}
              />
              <div className="min-w-0">
                <p className={`${t.instructor.name} font-bold text-lg`}>{instructor.name}</p>
                <p className={`${t.instructor.role} text-base mb-1.5`}>{instructor.role}</p>
                <p
                  className={`${t.instructor.description} text-base leading-relaxed`}
                  dangerouslySetInnerHTML={safeHtml(instructor.description)}
                />
              </div>
            </div>
          )}
        </div>
      </main>

      <footer className="relative flex-shrink-0 z-10 text-center px-5 lg:px-12 py-2">
        {disclaimer && (
          <p className={`text-sm leading-relaxed mb-1.5 ${t.footer.disclaimer}`}>{disclaimer}</p>
        )}
        <p className={`text-sm ${t.footer.text}`}>
          &copy; {new Date().getFullYear()} Todos los derechos reservados por{' '}
          <span className={t.footer.accent}>ConquerX</span>
        </p>
      </footer>
    </div>
  )
}
