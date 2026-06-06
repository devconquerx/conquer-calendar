import HeroSection from '../components/landing/HeroSection'
import LandingForm from '../components/landing/LandingForm'
import BulletPoints from '../components/landing/BulletPoints'
import { getTheme } from '../themes'
import { CB_CARD_SHADOW } from '../themes/conquerblocks'
import { safeHtml } from '../lib/sanitize'

export default function Landing({ school, program, region, formConfig, nextUrl, funnelSlug }) {
  const theme = getTheme(school?.slug)
  const t = theme.landing
  const isCB = theme.id === 'conquerblocks'
  const assets = theme.assets

  const landing = formConfig?.landing || formConfig?.welcome || {}
  const instructor = landing.instructor
  const disclaimer = landing.disclaimer

  if (isCB) {
    return <CBLanding
      school={school} program={program} region={region}
      formConfig={formConfig} theme={theme} assets={assets}
      instructor={instructor} disclaimer={disclaimer}
      nextUrl={nextUrl} funnelSlug={funnelSlug}
    />
  }

  return <DefaultLanding
    school={school} program={program} region={region}
    formConfig={formConfig} theme={theme} t={t}
    instructor={instructor} disclaimer={disclaimer}
    nextUrl={nextUrl} funnelSlug={funnelSlug}
  />
}


/* ═══ ConquerBlocks Landing — réplica de producción en React + Tailwind ═══
   Fondo casi blanco (#FAFAFA) con textura sutil, columna central de 1024px,
   tarjetas planas grises con borde arena, formulario con glow aurora animado. */
function CBLanding({ school, program, region, formConfig, theme, assets, instructor, disclaimer, nextUrl, funnelSlug }) {
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
  // Máscara con el borde pixelado a la derecha (como en producción). El volteo
  // está hecho dentro del propio SVG, no sobre la imagen.
  const pixelMaskStyle = assets?.instructorMask ? {
    WebkitMaskImage: `url(${assets.instructorMask})`,
    maskImage: `url(${assets.instructorMask})`,
    WebkitMaskSize: '100% 100%',
    maskSize: '100% 100%',
    WebkitMaskRepeat: 'no-repeat',
    maskRepeat: 'no-repeat',
  } : undefined

  return (
    <div className="min-h-screen overflow-x-hidden relative flex flex-col font-funnel bg-cb-bg text-cb-ink" style={pageStyle}>
      {/* Pixeles decorativos (réplica de producción: 150px, opacidad 0.2) */}
      {assets?.pixels?.deco && (
        <>
          <img src={assets.pixels.deco} alt="" aria-hidden="true" className="hidden lg:block absolute top-0 left-[6%] w-[150px] opacity-20 pointer-events-none select-none" />
          <img src={assets.pixels.deco} alt="" aria-hidden="true" className="hidden lg:block absolute top-[280px] right-[2%] w-[150px] opacity-20 pointer-events-none select-none" />
          <img src={assets.pixels.deco} alt="" aria-hidden="true" className="hidden lg:block absolute bottom-[120px] right-[8%] w-[150px] opacity-20 pointer-events-none select-none" />
        </>
      )}
      <main className="relative z-10 flex-1 w-full max-w-[1064px] mx-auto px-5 flex flex-col">
        {/* Logo: imagen centrada (sin tarjeta) */}
        <div className="py-4 flex justify-center">
          <img src={assets.logo} alt="ConquerBlocks" className="h-9 w-auto" />
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
        <div className="relative mt-10 animate-fade-in">
          <div className="absolute inset-0 rounded-2xl bg-[linear-gradient(60deg,#FFBF00,#FF4000,#FFBF00,#FF4000)] bg-[length:300%_300%] blur-[20px] animate-aurora" aria-hidden="true" />
          <div className="relative z-10 rounded-2xl border border-cb-line px-5 py-5 md:px-12 md:py-6" style={cardStyle}>
            <LandingForm
              program={program}
              region={region}
              formConfig={formConfig}
              school={school}
              nextUrl={nextUrl}
              funnelSlug={funnelSlug}
            />
          </div>
        </div>

        {/* Instructor */}
        {instructor && (
          <div className="mt-10 animate-fade-in rounded-2xl border border-cb-line overflow-hidden flex flex-col md:flex-row md:min-h-[341px]" style={cardStyle}>
            <div className="w-full aspect-square md:aspect-auto md:w-[341px] md:self-stretch flex-shrink-0">
              {instructorPhoto && (
                <img
                  src={instructorPhoto}
                  alt={instructor.name}
                  className="w-full h-full object-cover bg-black"
                  style={pixelMaskStyle}
                />
              )}
            </div>
            <div className="flex-1 p-8 md:p-12 flex flex-col gap-4 justify-center">
              <h2 className="text-4xl md:text-[48px] font-semibold leading-[1.1] text-cb-ink2">
                {instructor.name}
              </h2>
              <div className="text-base font-light text-cb-ink2 leading-relaxed">
                {instructor.role && <p>{instructor.role}</p>}
                <p className="mt-4" dangerouslySetInnerHTML={safeHtml(instructor.description)} />
              </div>
            </div>
          </div>
        )}
      </main>

      {/* Footer */}
      <footer className="w-full max-w-[1064px] mx-auto px-5 mt-12 pb-10">
        {disclaimer && (
          <p className="text-base font-light text-cb-ink2 leading-relaxed text-center">
            {disclaimer} Puedes contactarnos enviándonos un email a contacto@conquerblocks.com
          </p>
        )}
        <div className="border-t border-cb-line/60 my-6" />
        <div className="flex flex-col md:flex-row justify-between items-center gap-4 text-sm font-light text-cb-ink2">
          <p className="text-center md:text-left">
            Conquer Blocks {new Date().getFullYear()} &reg; | ConquerX LLC | 16192 Coastal Highway, Lewes 19958, Delaware, USA
          </p>
          <div className="flex gap-5 flex-shrink-0">
            <a href="https://www.conquerblocks.com/legal/politica-de-cookies" target="_blank" rel="noopener noreferrer" className="hover:text-cb-ink">Política de Cookies</a>
            <a href="https://www.conquerblocks.com/legal/politica-de-privacidad" target="_blank" rel="noopener noreferrer" className="hover:text-cb-ink">Política de Privacidad</a>
            <a href="https://www.conquerblocks.com/legal/terminos-y-condiciones" target="_blank" rel="noopener noreferrer" className="hover:text-cb-ink">Términos y Condiciones</a>
          </div>
        </div>
      </footer>
    </div>
  )
}


/* ═══ Default Theme Landing ═══ */
function DefaultLanding({ school, program, region, formConfig, theme, t, instructor, disclaimer, nextUrl, funnelSlug }) {
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
