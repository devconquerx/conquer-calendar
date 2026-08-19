import HeroSection from '../components/landing/HeroSection'
import LandingForm from '../components/landing/LandingForm'
import BulletPoints from '../components/landing/BulletPoints'
import { getTheme, useVariantTheme } from '../themes'
import { CB_CARD_SHADOW } from '../themes/conquerblocks'
import { safeHtml } from '../lib/sanitize'

export default function Landing({ school, program, region, formConfig, nextUrl, funnelSlug, videoEnabled = false }) {
  const baseTheme = getTheme(school?.slug)
  // Rediseño por página: un tema puede pedir que SOLO su landing use el sistema
  // paperboard (hoy: Finance, que toma prestados los tokens de Legal vía
  // `landingPaper`) sin cambiar de sistema en el resto de etapas del funnel.
  const pageTheme = !baseTheme.paperboard && baseTheme.landingVariant === 'paperboard'
    ? { ...baseTheme, ...baseTheme.landingPaper, paperboard: true, hexboard: false }
    : baseTheme
  // Variante A/B de diseño (Blocks LATAM 58: fondo blanco en vez de papel).
  const theme = useVariantTheme(pageTheme)
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

  if (theme.hexboard) {
    return <HexLanding
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
  // Variante de fondo blanco (A/B): sin textura y con el papel de las tarjetas
  // en blanco. El resto (bordes arena, sombras, acento naranja) no cambia.
  const isWhite = !!theme.whiteBackground
  const pageStyle = assets?.paperboardTexture ? {
    backgroundImage: `linear-gradient(rgba(255,255,255,0.55), rgba(255,255,255,0.55)), url(${assets.paperboardTexture})`,
    backgroundSize: 'cover',
    backgroundPosition: 'center',
    backgroundAttachment: 'fixed',
  } : undefined
  // Tarjetas: textura paperboard (overlay blanco 0.6 sobre #F6F6F6) + sombra en
  // capas de producción (inline para evitar el bug de color de Tailwind).
  const cardStyle = {
    backgroundColor: isWhite ? '#FFFFFF' : '#F6F6F6',
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
    <div className={`min-h-screen overflow-x-hidden relative flex flex-col font-funnel text-cb-ink ${isWhite ? 'bg-white' : 'bg-cb-bg'}`} style={pageStyle}>
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
              themeOverride={theme}
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
                    // Eje X aparte del position shorthand de arriba — el longhand
                    // gana solo en ese eje, así se puede desplazar el encuadre
                    // horizontal sin tocar el vertical. Opcional, sin efecto
                    // hasta que el tema lo defina.
                    ...(assets?.instructorBgPositionX ? { backgroundPositionX: assets.instructorBgPositionX } : {}),
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
          // `disclaimer` admite un array de párrafos (ej. Finance EU en prod trae
          // 3 notas al pie separadas, no una sola línea larga); el email de
          // contacto se auto-añade siempre al último párrafo.
          Array.isArray(disclaimer)
            ? disclaimer.map((line, i) => (
                <p key={i} className="max-w-[90%] mx-auto text-xs font-light text-neutral-500 leading-[1.25] text-center mb-1.5 last:mb-0">
                  {line}
                  {i === disclaimer.length - 1 && footer.contactEmail && ` Puedes contactarnos enviándonos un email a ${footer.contactEmail}`}
                </p>
              ))
            : (
              <p className="max-w-[90%] mx-auto text-xs font-light text-neutral-500 leading-[1.25] text-center">
                {disclaimer}
                {footer.contactEmail && ` Puedes contactarnos enviándonos un email a ${footer.contactEmail}`}
              </p>
            )
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


/* ═══ Landing "hexboard" — réplica 1:1 de conquerfinance.com (Webflow) ═══
   Medida en vivo contra producción (desktop 1440 / móvil ≤479):
   navbar 70px con logo de 180px · columna de 1140px · form de 980px ·
   tarjeta de instructor r10 con sombra rgba(6,34,99,.17) · logos de prensa
   max 120px justify-between · disclaimer Arial 12 · footer full-width con
   "ConquerX" en degradado Webflow. El cluster hexagonal va en el body
   (posición 150% 23%, 800px, no-repeat). */
const CONQUERX_GRADIENT =
  'linear-gradient(90deg, rgb(177,108,234) 20%, rgb(255,94,105) 60%, rgb(255,138,86) 80%, rgb(255,168,75) 90%)'

function HexLanding({ school, program, region, formConfig, theme, assets, instructor, disclaimer, nextUrl, funnelSlug, videoEnabled }) {
  const t = theme.landing || {}
  const footer = theme.footer || {}
  const contentWidth = t.contentWidth || '1140px'
  // La imagen va inline (URL del bundle); posición/tamaño por clases para poder
  // variar por breakpoint: en móvil el cluster asoma arriba (40px), en desktop
  // al 23% de la altura — como el body de producción.
  const pageStyle = {
    backgroundColor: '#ffffff',
    ...(assets?.hexBackground ? { backgroundImage: `url(${assets.hexBackground})` } : {}),
    fontFamily: 'Poppins, sans-serif',
  }
  const instructorPhoto = assets?.instructorPhoto || instructor?.imageUrl
  const pressLogos = t.pressLogos || []

  return (
    <div className="min-h-screen overflow-x-hidden relative flex flex-col text-black bg-no-repeat bg-[length:800px] bg-[position:150%_40px] md:bg-[position:150%_23%]" style={pageStyle}>
      {/* Navbar: logo 180px centrado; 75px de alto en móvil, 70px en desktop */}
      <header className="w-full h-[75px] md:h-[70px] flex items-center justify-center">
        <img src={assets.logo} alt={footer.copyrightBrand || 'Conquer Finance'} className="w-[180px] h-auto" />
      </header>

      <main className="relative z-10 flex-1 w-full mx-auto px-5 flex flex-col" style={{ maxWidth: `calc(${contentWidth} + 40px)` }}>
        {/* Hero: eyebrow + título + subtítulo (a 5px del navbar, como producción) */}
        <div className="mt-[5px]">
          <HeroSection formConfig={formConfig} theme={theme} />
        </div>

        {/* Bullets con check azul (a 10px del subtítulo) */}
        <div className="mt-[10px]">
          <BulletPoints formConfig={formConfig} theme={theme} />
        </div>

        {/* Doble chevron azul: producción usa un Lottie dentro de un hueco de
            ~56px entre bullets y form — aquí un SVG estático con la misma forma. */}
        <div className="h-[45px] md:h-[56px] flex items-center justify-center" aria-hidden="true">
          <svg viewBox="0 0 24 24" className="w-9 h-9 animate-bounce" fill="none" stroke={t.accentText || '#345bb8'} strokeWidth="3.2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M4 6l8 7 8-7" />
            <path d="M4 13l8 7 8-7" />
          </svg>
        </div>

        {/* Formulario inline (sin tarjeta; el .container-form de Webflow mide
            980px en desktop y 95% del viewport en móvil, con 25px arriba y
            20px abajo) */}
        <div className="-mx-[10px] md:mx-auto md:w-full max-w-[980px] pt-[25px] pb-[20px]">
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

        {/* Instructor: tarjeta blanca r10 con avatar circular de 150px.
            Sombra desktop rgba(6,34,99,.17) / móvil 0 2px 11px #0003 (Webflow). */}
        {instructor && (
          <div className="mt-[40px] rounded-[10px] bg-white shadow-[0_2px_11px_rgba(0,0,0,0.2)] md:shadow-[0_2px_5px_2px_rgba(6,34,99,0.17)] px-[17px] py-[20px] md:py-[40px] md:pl-[98px] md:pr-[60px] flex flex-col md:flex-row items-center gap-[10px] md:gap-[41px]">
            {instructorPhoto && (
              <img
                src={instructorPhoto}
                alt={instructor.name}
                className="w-[150px] h-[150px] rounded-full object-cover flex-shrink-0"
              />
            )}
            <div className="min-w-0 max-w-[755px] text-center md:text-left">
              <p className="text-[17px] md:text-[18px] font-extrabold leading-[32px]" style={{ color: t.accentText || '#1c48af' }}>{instructor.name}</p>
              {instructor.role && <p className="text-sm text-gray-500 mb-1">{instructor.role}</p>}
              <p
                className="text-[14px] font-medium leading-[21px] text-black/80 [&_strong]:font-bold [&_em]:italic"
                dangerouslySetInnerHTML={safeHtml(instructor.description)}
              />
            </div>
          </div>
        )}

        {/* Logos de prensa: título Poppins 800 16 + logos de hasta 120px.
            Desktop: una fila justify-between; móvil: filas de 2 sin gap vertical. */}
        {pressLogos.length > 0 && (
          <div className="mt-[40px] md:mt-[70px] flex flex-col md:flex-row items-center justify-between md:gap-[40px]">
            <p className="text-[16px] font-extrabold leading-[21px] text-[#333] flex-shrink-0 mb-[30px] md:mb-0">{t.pressTitle || 'Nos has visto en...'}</p>
            <div className="max-md:flex max-md:flex-wrap max-md:justify-center max-md:gap-x-[40px] max-md:gap-y-0 md:contents">
              {pressLogos.map((src, i) => (
                <img key={i} src={src} alt="" className="max-w-[120px] h-auto object-contain" />
              ))}
            </div>
          </div>
        )}

        {/* Disclaimer + contacto: Arial 12/lh20 #333 centrado */}
        <div className="mt-[40px] md:mt-[55px] text-center text-[12px] leading-[20px] text-[#333]" style={{ fontFamily: 'Arial, sans-serif' }}>
          {disclaimer && <p>{disclaimer}</p>}
          {footer.contactEmail && (
            <p className="mt-[20px]">Puedes contactarnos enviándonos un email a {footer.contactEmail}</p>
          )}
        </div>
      </main>

      {/* Footer dentro del contenedor de contenido (1140px): © Arial 14 +
          ConquerX en degradado Webflow + enlaces legales Poppins 14 con "/" */}
      <footer className="w-full mx-auto px-5 mt-[60px] py-[20px] flex flex-col md:flex-row justify-between items-center gap-3 text-[14px] text-[#333]" style={{ maxWidth: `calc(${contentWidth} + 40px)` }}>
        <p className="text-center md:text-left" style={{ fontFamily: 'Arial, sans-serif' }}>
          &copy; {new Date().getFullYear()} Todos los derechos reservados por{' '}
          <span
            className="font-extrabold align-middle"
            style={{
              fontFamily: 'Montserrat, sans-serif',
              backgroundImage: CONQUERX_GRADIENT,
              WebkitBackgroundClip: 'text',
              backgroundClip: 'text',
              color: 'transparent',
            }}
          >
            {footer.copyrightBrand || 'ConquerX'}
          </span>
        </p>
        <div className="flex flex-wrap justify-center gap-2 flex-shrink-0" style={{ fontFamily: 'Poppins, sans-serif' }}>
          <a href={footer.legal?.terms} target="_blank" rel="noopener noreferrer" className="hover:underline">Términos y condiciones</a>
          <span>/</span>
          <a href={footer.legal?.privacy} target="_blank" rel="noopener noreferrer" className="hover:underline">Política de privacidad</a>
          <span>/</span>
          <a href={footer.legal?.cookies} target="_blank" rel="noopener noreferrer" className="hover:underline">Política de cookies</a>
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
