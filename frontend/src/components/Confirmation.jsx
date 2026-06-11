import { useEffect } from 'react'
import { getTheme } from '../themes'
import useTracking from '../hooks/useTracking'
import { fireAllSchedule } from '../lib/pixelEvents'

// Los assets y textos de la confirmación paperboard viven en el tema
// (theme.confirmation): cada marca aporta sus iconos, fotos, vídeos y copy.

/**
 * Página de confirmación de llamada — port 1:1 del funnel de Django (funnels).
 * Se muestra tras agendar en Calendly. Dispara el evento Schedule en todas las
 * plataformas (Meta/Google Ads/TikTok/GA4) al montar, usando el UUID de Calendly
 * y el schedule_event_id guardados en localStorage (igual que funnels).
 */
export default function Confirmation({ escuela = '', slug = '' }) {
  const theme = getTheme(escuela, slug)
  const isPaper = !!theme.paperboard && !!theme.confirmation
  const assets = theme.assets
  const { eventId, journeyId } = useTracking()

  useEffect(() => {
    const calendlyEventUuid =
      (typeof localStorage !== 'undefined' && localStorage.getItem('cqx_calendly_event_uuid')) || ''
    const scheduleEventId =
      (typeof localStorage !== 'undefined' && localStorage.getItem('cqx_schedule_event_id')) || ''

    fireAllSchedule({
      eventId,
      journeyId,
      schoolSlug: escuela,
      calendlyEventUuid,
      scheduleEventId,
    })
  }, [eventId, journeyId, escuela])

  if (isPaper) {
    return <PaperboardConfirmation theme={theme} assets={assets} />
  }

  return <DefaultConfirmation escuela={escuela} theme={theme} />
}


/* ═══════════════════════════════════════════════════════
   Paperboard Confirmation (Blocks / Legal) — réplica de producción
   Renderer compartido dirigido por theme.confirmation + theme.accent.
   ═══════════════════════════════════════════════════════ */

const cardShadow =
  'shadow-[0px_2px_5px_rgba(0,0,0,0.1),0px_9px_9px_rgba(0,0,0,0.09),0px_20px_12px_rgba(0,0,0,0.05),0px_36px_14px_rgba(0,0,0,0.01)]'

// Texto con relleno de gradiente (bg-clip-text) por estilo inline.
const gradText = (grad) => ({
  backgroundImage: grad,
  WebkitBackgroundClip: 'text',
  backgroundClip: 'text',
  color: 'transparent',
})

// Badge pill de cada paso. `big` = estilo Blocks (32px + icono); si no, pill
// pequeño de texto (estilo Legal). `texture` aplica el papel paperboard de fondo.
function StepBadge({ children, icon, big, texture }) {
  return (
    <div
      className={`relative inline-flex items-center gap-3 ${
        big ? 'px-4 py-1 rounded-2xl' : 'px-5 py-1.5 rounded-full'
      } border border-[#BBB49B] ${cardShadow} overflow-hidden`}
    >
      <div
        className="absolute inset-0 pointer-events-none"
        style={{
          backgroundImage: texture
            ? `linear-gradient(rgba(255,255,255,0.5), rgba(255,255,255,0.5)), url(${texture})`
            : undefined,
          backgroundSize: 'cover',
          backgroundPosition: 'center',
        }}
      />
      <p
        className={`relative font-['Funnel_Display',sans-serif] font-semibold ${
          big ? 'text-2xl md:text-[32px]' : 'text-base md:text-lg'
        } leading-[1.3] text-black whitespace-nowrap`}
      >
        {children}
      </p>
      {icon && <img src={icon} alt="" className={`relative ${big ? 'w-8 h-8' : 'w-5 h-5'}`} />}
    </div>
  )
}

// Marco del vídeo: si el tema trae un SVG de marco (Blocks), se superpone; si no,
// borde azul redondeado con glow (Legal).
function VideoFrame({ frame, accent, children }) {
  if (frame) {
    return (
      <div className="aspect-video relative">
        {children}
        <img src={frame} alt="" className="absolute inset-0 w-full h-full pointer-events-none z-10" />
      </div>
    )
  }
  return (
    <div
      className="aspect-video relative rounded-xl overflow-hidden"
      style={{
        border: `2px solid ${accent?.ring || '#3E76FF'}`,
        boxShadow: '0 0 30px rgba(62,118,255,0.25)',
      }}
    >
      {children}
    </div>
  )
}

function PaperboardConfirmation({ theme, assets }) {
  const c = theme.confirmation
  const texture = assets?.paperboardTexture
  const px = assets?.pixels || {}

  const paperboardBg = texture
    ? { backgroundImage: `url(${texture})`, backgroundSize: 'cover', backgroundPosition: 'center' }
    : undefined
  const cardBg = texture
    ? {
        backgroundImage: `linear-gradient(rgba(255,255,255,0.5), rgba(255,255,255,0.5)), url(${texture})`,
        backgroundSize: 'cover',
        backgroundPosition: 'center',
      }
    : undefined
  const gridBg = {
    backgroundImage:
      'linear-gradient(rgba(255,255,255,0.07) 1px, transparent 1px), linear-gradient(90deg, rgba(255,255,255,0.07) 1px, transparent 1px)',
    backgroundSize: '48px 48px',
  }

  const heroWeight = c.heroWeight || 'font-semibold'
  const isInstr = c.paso2ImageMode === 'instructor'
  const paso2ImgStyle = {
    backgroundImage: `url(${c.paso2Image})`,
    backgroundSize: isInstr ? '120%' : 'cover',
    backgroundPosition: isInstr ? '40% 32%' : 'center',
    backgroundRepeat: 'no-repeat',
    WebkitMaskImage: assets?.instructorMask ? `url(${assets.instructorMask})` : undefined,
    maskImage: assets?.instructorMask ? `url(${assets.instructorMask})` : undefined,
    WebkitMaskSize: '100% 100%',
    maskSize: '100% 100%',
    WebkitMaskRepeat: 'no-repeat',
    maskRepeat: 'no-repeat',
    transform: isInstr ? 'scaleX(-1)' : undefined,
  }

  return (
    <div className="min-h-screen overflow-x-hidden relative flex flex-col font-['Funnel_Display',sans-serif] bg-black">

      {/* ═══ SECTION 1: Hero ═══ */}
      <section className="relative bg-[#F5EDE3] px-4 lg:px-16 pt-12 pb-12" style={paperboardBg}>
        {px.deco2 && (
          <>
            <img src={px.deco2} alt="" className="absolute top-8 left-6 w-24 opacity-40 pointer-events-none hidden lg:block" />
            <img src={px.deco2} alt="" className="absolute top-16 right-6 w-28 opacity-20 pointer-events-none hidden lg:block" />
          </>
        )}

        {/* Navbar con logo */}
        <header className="relative z-10 mb-12">
          <div className="max-w-[1280px] mx-auto">
            <div
              className={`flex items-center justify-center py-5 rounded-lg border border-[#BBB49B] ${cardShadow} overflow-hidden`}
              style={cardBg}
            >
              <img src={assets?.logo} alt="" className="h-6" />
            </div>
          </div>
        </header>

        <div className="relative z-10 max-w-[1280px] mx-auto text-center">
          {c.heroIcon && (
            <div className="mx-auto mb-8">
              <img src={c.heroIcon} alt="" className="w-24 h-24 mx-auto" />
            </div>
          )}

          <h1 className={`text-3xl md:text-[40px] ${heroWeight} leading-[1.2] text-black mb-8`}>
            <span className="block text-4xl md:text-[40px]" style={gradText(c.felicidadesGradient)}>
              {c.felicidades}
            </span>
            {c.heroTitle}
          </h1>

          {/* Caja Importante */}
          <div
            className={`relative inline-flex flex-col items-center justify-center rounded-lg ${cardShadow} max-w-[640px] w-full overflow-hidden`}
            style={{ backgroundImage: c.boxGradient }}
          >
            <div className="relative w-full px-8 md:px-12 py-6">
              <p className="font-semibold text-white text-2xl md:text-[32px] leading-[1.3] text-center mb-2">
                {c.importanteTitle}
              </p>
              <p className="font-medium text-white text-lg md:text-xl leading-[1.25] text-center">
                {c.importanteText}
              </p>
            </div>
            {c.heroIconSmall && (
              <img src={c.heroIconSmall} alt="" className="absolute -top-4 -right-4 w-16 h-16 pointer-events-none hidden md:block" />
            )}
          </div>
        </div>
      </section>

      {/* ═══ TORN: cream → black ═══ */}
      {assets?.tornTransition2000 && (
        <div className="relative z-10 bg-black -mt-[2px]">
          <img src={assets.tornTransition2000} alt="" className="w-full block scale-y-[-1]" />
        </div>
      )}

      {/* ═══ SECTION 2: Paso 1 — vídeo ═══ */}
      <section className="relative bg-black px-4 lg:px-16 py-20 lg:py-28" style={gridBg}>
        <div className="relative z-10 max-w-[1280px] mx-auto text-center">
          <div className="mb-8">
            <StepBadge big={c.badgeBig} icon={c.paso1BadgeIcon} texture={texture}>
              {c.paso1Badge}
            </StepBadge>
          </div>
          <p className="font-medium text-white text-lg md:text-xl leading-[1.3] mb-12 max-w-[820px] mx-auto">
            {c.paso1Text}
          </p>
          <div className="max-w-[1024px] mx-auto">
            <VideoFrame frame={c.videoFrame} accent={theme.accent}>
              <iframe
                src={c.paso1Video}
                className="w-full h-full relative z-0"
                allow="autoplay; fullscreen; picture-in-picture"
                allowFullScreen
                title="Paso 1"
                style={{ border: 'none' }}
              />
            </VideoFrame>
          </div>
        </div>
      </section>

      {/* ═══ SECTION 3: Paso 2 — confirma tu cita ═══ */}
      <section className="relative px-4 lg:px-16 py-20 bg-[#F5EDE3]" style={paperboardBg}>
        {px.deco && (
          <img src={px.deco} alt="" className="absolute top-8 left-8 w-28 opacity-20 pointer-events-none hidden lg:block" />
        )}
        <div className="relative z-10 max-w-[1280px] mx-auto">
          <div className="text-center mb-16">
            <StepBadge big={c.badgeBig} icon={c.paso2BadgeIcon} texture={texture}>
              {c.paso2Badge}
            </StepBadge>
          </div>

          {/* Tarjeta: foto + texto */}
          <div
            className={`rounded-2xl overflow-hidden ${cardShadow} flex flex-col lg:flex-row border border-[#BBB49B]`}
            style={{ ...cardBg, minHeight: c.paso2MinHeight || undefined }}
          >
            <div className="lg:w-[540px] flex-shrink-0 self-stretch h-64 lg:h-auto" style={paso2ImgStyle} />

            <div className="flex-1 p-8 lg:p-12 flex flex-col justify-center">
              {c.paso2Heading && (
                <div className="flex items-center gap-4 mb-6">
                  {c.paso2HeadingIcon && <img src={c.paso2HeadingIcon} alt="" className="w-12 h-12 flex-shrink-0" />}
                  <h3 className="text-2xl md:text-[32px] font-semibold text-black leading-[1.1]">
                    {c.paso2Heading}
                  </h3>
                </div>
              )}
              <div className="text-base md:text-lg text-[#333] leading-[1.5] font-normal space-y-5">
                {c.paso2Paragraphs.map((p, i) => (
                  <p key={i}>{p}</p>
                ))}
              </div>
              {c.paso2Divider && <div className="border-t border-[#BBB49B]/60 mt-8" />}
            </div>
          </div>

          {/* Caja recordatorio */}
          <div
            className={`mt-12 relative ${cardShadow} rounded-lg overflow-hidden w-full`}
            style={{ backgroundImage: c.boxGradient }}
          >
            <div className="relative px-8 md:px-12 py-6">
              <p className="font-semibold text-white text-xl md:text-[28px] leading-[1.3] text-center">
                {c.reminderText}
              </p>
            </div>
          </div>
        </div>
      </section>

      {/* ═══ TORN: cream → black ═══ */}
      {assets?.tornTransition2000 && (
        <div className="relative z-10 bg-black -mt-[2px]">
          <img src={assets.tornTransition2000} alt="" className="w-full block scale-y-[-1]" />
        </div>
      )}

      {/* ═══ SECTION 4: Paso 3 — perspectivas ═══ */}
      <section className="relative bg-black px-4 lg:px-16 py-20 lg:py-28 overflow-hidden" style={gridBg}>
        {px.deco && (
          <img src={px.deco} alt="" className="absolute top-20 left-6 w-20 opacity-60 pointer-events-none hidden lg:block" />
        )}
        <div className="relative z-10 max-w-[1280px] mx-auto text-center">
          <div className="mb-8">
            <StepBadge big={c.badgeBig} icon={c.paso3BadgeIcon} texture={texture}>
              {c.paso3Badge}
            </StepBadge>
          </div>

          <h2 className="font-semibold text-white text-3xl md:text-[40px] leading-[1.2] mb-6 max-w-[820px] mx-auto">
            {c.paso3TitlePre}
            <span style={gradText(c.accentGradient)}>{c.paso3TitleAccent}</span>
          </h2>

          <div className="max-w-[760px] mx-auto mb-12">
            <p className="text-white text-lg md:text-xl leading-[1.3] mb-1">{c.paso3Subtitle}</p>
            {c.paso3SubtitleAccent && (
              <p className="text-lg md:text-xl leading-[1.3] font-semibold" style={gradText(c.accentGradient)}>
                {c.paso3SubtitleAccent}
              </p>
            )}
          </div>

          <div className="max-w-[1024px] mx-auto">
            <a href={c.paso3Video} target="_blank" rel="noopener noreferrer" className="block group">
              <VideoFrame frame={c.videoFrame} accent={theme.accent}>
                <img src={c.paso3Thumbnail} alt="" className="w-full h-full object-cover" />
                <div className="absolute inset-0 flex items-center justify-center z-[5]">
                  {c.paso3PlayIcon ? (
                    <img src={c.paso3PlayIcon} alt="" className="w-16 h-16 md:w-20 md:h-20 group-hover:scale-110 transition-transform" />
                  ) : (
                    <div className="w-16 h-16 md:w-20 md:h-20 bg-white/90 rounded-full flex items-center justify-center group-hover:scale-110 transition-transform">
                      <svg className="w-8 h-8 md:w-10 md:h-10 ml-1 text-black" fill="currentColor" viewBox="0 0 24 24">
                        <path d="M8 5v14l11-7z" />
                      </svg>
                    </div>
                  )}
                </div>
              </VideoFrame>
            </a>
          </div>
        </div>
      </section>

      {/* ═══ TORN: black → footer ═══ */}
      {assets?.tornTransition2000 && (
        <div className="relative z-10 bg-black -mb-[2px]">
          <img src={assets.tornTransition2000} alt="" className="w-full block" />
        </div>
      )}

      {/* ═══ FOOTER ═══ */}
      <footer className="relative flex-shrink-0 z-10 overflow-hidden bg-[#F5EDE3]" style={paperboardBg}>
        {c.footerMode === 'minimal' ? (
          <div className="relative w-full max-w-[1280px] mx-auto px-6 py-16 flex justify-center">
            {px.deco2 && (
              <img src={px.deco2} alt="" className="absolute top-8 right-10 w-24 opacity-40 pointer-events-none hidden lg:block" />
            )}
            <img src={assets?.logo} alt="" className="h-16" />
          </div>
        ) : (
          <>
            {px.deco && (
              <img src={px.deco} alt="" className="absolute top-12 right-16 w-36 opacity-30 pointer-events-none hidden lg:block" />
            )}
            <div className="w-full max-w-[1280px] mx-auto px-6 lg:px-24 pt-20 pb-8 relative">
              <div className="flex flex-col gap-8 items-start">
                <img src={assets?.footerLogo || assets?.logo} alt="" className="h-16" />
                <div className="text-[#222] text-sm leading-[1.5]">
                  <p className="font-medium text-base">Contacto:</p>
                  <p>{c.footer?.contactPhone}</p>
                  <p>{c.footer?.contactEmail}</p>
                </div>
              </div>
              <div className="border-t border-[#222]/20 mt-12 mb-8" />
              <div className="flex flex-col md:flex-row justify-between items-start md:items-center gap-4 text-sm text-[#222]">
                <p>
                  {c.footer?.copyrightBrand} {new Date().getFullYear()} &reg; | {c.footer?.copyrightBrand} &reg; es un trademark de Conquer X &reg;
                </p>
                <div className="flex gap-6">
                  <a href="#" className="underline hover:text-black">Términos de uso</a>
                  <a href="#" className="underline hover:text-black">Aviso legal</a>
                </div>
              </div>
            </div>
          </>
        )}
      </footer>
    </div>
  )
}

/* ═══════════════════════════════════════════════════════
   Default Theme Confirmation (sin marca)
   ═══════════════════════════════════════════════════════ */

const STEP1_VIDEO_DEFAULT =
  'https://iframe.mediadelivery.net/embed/146448/b13e87cd-570a-4f6b-aba2-23f2bbdebd8e?autoplay=false&loop=false&muted=false&preload=true&responsive=true'
const STEP3_THUMBNAIL_DEFAULT =
  'https://cdn.prod.website-files.com/63c2c7b1f3d9c51c32335fb0/6972487d4779e4b685dfdbf5_video-confirmacion-cb.jpg'
const STEP3_VIDEO_URL_DEFAULT = 'https://youtu.be/70NzkcJa5oA'

function DefaultConfirmation({ escuela, theme }) {
  const c = theme.confirmation

  return (
    <div className={`min-h-screen ${c.heroBg}`}>
      <header className="relative px-5 lg:px-12 py-3 lg:py-4 flex-shrink-0 z-10">
        <span className="text-lg lg:text-2xl font-bold text-gray-900 tracking-tight">
          {escuela || 'ConquerX'}
        </span>
      </header>

      <section className="pt-10 pb-8 px-4 text-center">
        <div className="max-w-4xl mx-auto">
          <h1 className={`text-3xl md:text-4xl font-bold ${c.stepTitle} mb-1`}>
            <span className={`block ${c.felicidades} font-script text-4xl md:text-5xl mb-1`} style={{ fontFamily: 'Georgia, serif', fontStyle: 'italic' }}>
              ¡Felicidades!
            </span>
            Tu llamada ha sido reservada
          </h1>
          <div className={`mt-6 ${c.importantBanner} text-white rounded-xl px-6 py-3.5 inline-block max-w-xl`}>
            <p className="text-sm md:text-base">
              <strong>Importante:</strong> completa estos <strong><em>3 pasos</em></strong> ahora para poder aprovechar tu llamada al máximo
            </p>
          </div>
        </div>
      </section>

      <section className="py-10 px-4">
        <div className="max-w-4xl mx-auto text-center">
          <h2 className={`text-xl md:text-2xl font-bold ${c.stepTitle} mb-3`}>
            <span className={`${c.stepLabel} font-normal`}>PASO 1 ·</span> Mira este video
          </h2>
          <p className={`${c.bodyText} mb-6`}>
            <strong>Mira este video</strong> de 47 segundos para entender tus siguientes pasos lógicos
          </p>
          <div className={`aspect-video rounded-xl overflow-hidden ${c.videoShadow} border ${c.videoBorder}`}>
            <iframe
              src={STEP1_VIDEO_DEFAULT}
              className="w-full h-full"
              allow="autoplay; fullscreen; picture-in-picture"
              allowFullScreen
              title="Paso 1"
              style={{ border: 'none' }}
            />
          </div>
        </div>
      </section>

      <section className={`py-10 px-4 ${c.altSectionBg}`}>
        <div className="max-w-4xl mx-auto text-center">
          <h2 className={`text-xl md:text-2xl font-bold ${c.stepTitle} mb-3`}>
            <span className={`${c.stepLabel} font-normal`}>PASO 2 ·</span> Confirma tu cita
          </h2>
          <p className={`${c.bodyText} leading-relaxed mb-4`}>
            Mantente al tanto de tu teléfono porque te contactaremos por llamada para confirmar la cita.
          </p>
          <div className={`mt-4 ${c.reminderBg} rounded-lg px-6 py-3.5`}>
            <p className={`${c.bodyText} text-sm`}>
              Recuerda conectarte <strong>puntual</strong> y estando en un lugar tranquilo y cómodo.
            </p>
          </div>
        </div>
      </section>

      <section className="py-10 px-4">
        <div className="max-w-4xl mx-auto text-center">
          <h2 className={`text-xl md:text-2xl font-bold ${c.stepTitle} mb-6`}>
            <span className={`${c.stepLabel} font-normal`}>PASO 3 ·</span> Descubre
          </h2>
          <a
            href={STEP3_VIDEO_URL_DEFAULT}
            target="_blank"
            rel="noopener noreferrer"
            className={`block aspect-video rounded-xl overflow-hidden ${c.videoShadow} border ${c.videoBorder} group relative`}
          >
            <img src={STEP3_THUMBNAIL_DEFAULT} alt="Descubre" className="w-full h-full object-cover" />
            <div className="absolute inset-0 bg-black/20 group-hover:bg-black/30 transition-colors flex items-center justify-center">
              <div className="w-16 h-16 bg-white/90 rounded-full flex items-center justify-center group-hover:scale-110 transition-transform">
                <svg className="w-8 h-8 text-gray-900 ml-1" fill="currentColor" viewBox="0 0 24 24">
                  <path d="M8 5v14l11-7z" />
                </svg>
              </div>
            </div>
          </a>
        </div>
      </section>

      <footer className="text-center px-5 lg:px-12 py-4">
        <p className={`text-sm ${c.footer?.text || 'text-gray-400'}`}>
          &copy; {new Date().getFullYear()} Todos los derechos reservados por ConquerX
        </p>
      </footer>
    </div>
  )
}
