import { useEffect } from 'react'
import { getTheme } from '../themes'
import useTracking from '../hooks/useTracking'
import { fireAllSchedule } from '../lib/pixelEvents'

// Assets específicos de la confirmación (resueltos por Vite vía import ES6).
import paperboardTexture from '../assets/img/cb/paperboard-texture.avif'
import instructorPhotoFallback from '../assets/img/cb/bienvenido-saez-2.avif'
import CONFETTI_ICON from '../assets/img/cb/confirmation/confetti-icon.svg'
import CONFETTI_ICON_SMALL from '../assets/img/cb/confirmation/confetti-icon-small.svg'
import YOUTUBE_ICON from '../assets/img/cb/confirmation/youtube-icon.svg'
import VIDEO_FRAME from '../assets/img/cb/confirmation/video-frame.svg'
import CHECK_CIRCLE_ICON from '../assets/img/cb/confirmation/check-circle-icon.svg'
import LIGHTBULB_ICON from '../assets/img/cb/confirmation/lightbulb-icon.svg'
import STEP3_THUMBNAIL from '../assets/img/cb/confirmation/video-thumbnail-1.png'

/**
 * Página de confirmación de llamada — port 1:1 del funnel de Django (funnels).
 * Se muestra tras agendar en Calendly. Dispara el evento Schedule en todas las
 * plataformas (Meta/Google Ads/TikTok/GA4) al montar, usando el UUID de Calendly
 * y el schedule_event_id guardados en localStorage (igual que funnels).
 */
export default function Confirmation({ escuela = '', slug = '' }) {
  const theme = getTheme(escuela, slug)
  const isCB = theme.id === 'conquerblocks'
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

  if (isCB) {
    return <CBConfirmation assets={assets} />
  }

  return <DefaultConfirmation escuela={escuela} theme={theme} />
}


/* ═══════════════════════════════════════════════════════
   ConquerBlocks Confirmation — Figma 1:1
   ═══════════════════════════════════════════════════════ */

const STEP1_VIDEO =
  'https://iframe.mediadelivery.net/embed/146448/b13e87cd-570a-4f6b-aba2-23f2bbdebd8e?autoplay=false&loop=false&muted=false&preload=true&responsive=true'
const STEP3_VIDEO_URL = 'https://youtu.be/70NzkcJa5oA'

const cbShadow =
  'shadow-[0px_2px_5px_rgba(0,0,0,0.1),0px_9px_9px_rgba(0,0,0,0.09),0px_20px_12px_rgba(0,0,0,0.05),0px_36px_14px_rgba(0,0,0,0.01)]'

function StepBadge({ children, icon }) {
  return (
    <div className={`relative inline-flex items-center gap-3 px-4 py-1 rounded-2xl border border-[#BBB49B] ${cbShadow} overflow-hidden`}>
      <div className="absolute inset-0 pointer-events-none rounded-2xl"
        style={{
          backgroundImage: `linear-gradient(rgba(255,255,255,0.5), rgba(255,255,255,0.5)), url(${paperboardTexture})`,
          backgroundSize: 'cover',
          backgroundPosition: 'center',
        }}
      />
      <p className="relative font-['Funnel_Display',sans-serif] font-semibold text-2xl md:text-[32px] leading-[1.3] text-black whitespace-nowrap">
        {children}
      </p>
      {icon && (
        <img src={icon} alt="" className="relative w-8 h-8" />
      )}
    </div>
  )
}

function CBConfirmation({ assets }) {
  const paperboardBg = assets?.paperboardTexture ? {
    backgroundImage: `url(${assets.paperboardTexture})`,
    backgroundSize: 'cover',
    backgroundPosition: 'center',
  } : undefined

  const cardBg = assets?.paperboardTexture ? {
    backgroundImage: `linear-gradient(rgba(255,255,255,0.5), rgba(255,255,255,0.5)), url(${assets.paperboardTexture})`,
    backgroundSize: 'cover',
    backgroundPosition: 'center',
  } : undefined

  const instructorPhoto = assets?.instructorPhoto || instructorPhotoFallback

  return (
    <div className="min-h-screen overflow-x-hidden relative flex flex-col font-['Funnel_Display',sans-serif] bg-black">

      {/* ═══ SECTION 1: Hero — Paperboard background ═══ */}
      <section
        className="relative bg-[#F5EDE3] px-4 lg:px-16 pt-12 pb-12"
        style={paperboardBg}
      >
        {/* Decorative pixels */}
        {assets && (
          <>
            <img src={assets.pixels.sm4} alt="" className="absolute top-8 left-6 w-24 opacity-40 pointer-events-none hidden lg:block" />
            <img src={assets.pixels.lg6} alt="" className="absolute top-16 right-6 w-28 opacity-20 pointer-events-none hidden lg:block" />
          </>
        )}

        {/* Navbar */}
        <header className="relative z-10 mb-12">
          <div className="max-w-[1280px] mx-auto">
            <div
              className={`flex items-center justify-center py-5 rounded-lg border border-[#BBB49B] ${cbShadow} overflow-hidden`}
              style={cardBg}
            >
              <img src={assets?.logo} alt="ConquerBlocks" className="h-6" />
            </div>
          </div>
        </header>

        {/* Hero content */}
        <div className="relative z-10 max-w-[1280px] mx-auto text-center">
          {/* Confetti icon */}
          <div className="mx-auto mb-8">
            <img src={CONFETTI_ICON} alt="" className="w-24 h-24 mx-auto" />
          </div>

          {/* Title */}
          <h1 className="text-3xl md:text-[40px] font-semibold leading-[1.2] text-black mb-8">
            <span className="block bg-gradient-to-r from-yellow-400 via-[#f70] to-red-500 bg-clip-text text-transparent text-4xl md:text-[40px]">
              ¡Felicidades!
            </span>
            Tu llamada ha sido reservada
          </h1>

          {/* Important card */}
          <div className={`relative inline-flex flex-col items-start justify-center rounded-lg ${cbShadow} max-w-[640px] w-full overflow-hidden bg-gradient-to-r from-[#FFBF00] to-[#FF4000]`}>
            <div className="relative w-full px-8 md:px-12 py-6">
              <p className="font-semibold text-white text-2xl md:text-[32px] leading-[1.3] text-center mb-4">
                Importante
              </p>
              <p className="font-semibold text-white text-lg md:text-xl leading-[1.2] text-center">
                completa estos 3 pasos ahora para poder aprovechar tu llamada al máximo
              </p>
            </div>
            {/* Small confetti on top-right */}
            <img
              src={CONFETTI_ICON_SMALL}
              alt=""
              className="absolute -top-4 -right-4 w-16 h-16 pointer-events-none hidden md:block"
            />
          </div>
        </div>
      </section>

      {/* ═══ TORN-PAPER: Cream → Black ═══ */}
      {assets?.tornTransition2000 && (
        <div className="relative z-10 bg-black -mt-[2px]">
          <img src={assets.tornTransition2000} alt="" className="w-full block scale-y-[-1]" />
        </div>
      )}

      {/* ═══ SECTION 2: Paso 1 — Video ═══ */}
      <section
        className="relative bg-black px-4 lg:px-16 py-20 lg:py-28"
        style={{
          backgroundImage: 'linear-gradient(rgba(255,255,255,0.07) 1px, transparent 1px), linear-gradient(90deg, rgba(255,255,255,0.07) 1px, transparent 1px)',
          backgroundSize: '48px 48px',
        }}
      >

        <div className="relative z-10 max-w-[1280px] mx-auto text-center">
          <div className="mb-8">
            <StepBadge icon={YOUTUBE_ICON}>
              Paso 1 • Mira este vídeo
            </StepBadge>
          </div>

          <p className="font-semibold text-white text-lg md:text-xl leading-[1.2] mb-12">
            Mira este vídeo de 47 segundos para entender tus siguientes pasos lógicos
          </p>

          <div className="max-w-[1024px] mx-auto">
            <div className="aspect-video relative">
              <iframe
                src={STEP1_VIDEO}
                className="w-full h-full relative z-0"
                allow="autoplay; fullscreen; picture-in-picture"
                allowFullScreen
                title="Paso 1 - Siguientes pasos"
                style={{ border: 'none' }}
              />
              <img
                src={VIDEO_FRAME}
                alt=""
                className="absolute inset-0 w-full h-full pointer-events-none z-10"
              />
            </div>
          </div>
        </div>
      </section>

      {/* ═══ SECTION 3: Paso 2 — Confirma tu cita ═══ */}
      <section
        className="relative px-4 lg:px-16 py-20 lg:py-20 bg-[#F5EDE3]"
        style={paperboardBg}
      >
        {/* Decorative pixels */}
        {assets && (
          <>
            <img src={assets.pixels.lg5} alt="" className="absolute top-8 left-8 w-28 opacity-20 pointer-events-none hidden lg:block" />
          </>
        )}

        <div className="relative z-10 max-w-[1280px] mx-auto">
          <div className="text-center mb-16">
            <StepBadge icon={CHECK_CIRCLE_ICON}>
              Paso 2 • Confirma tu cita
            </StepBadge>
          </div>

          {/* Instructor + text card */}
          <div
            className={`rounded-2xl overflow-hidden ${cbShadow} flex flex-col lg:flex-row lg:h-[640px] border border-[#BBB49B]`}
            style={cardBg}
          >
            {/* Instructor photo */}
            <div className="lg:w-[540px] flex-shrink-0">
              <div
                className="w-full h-64 lg:h-[640px]"
                style={{
                  backgroundImage: `url(${instructorPhoto})`,
                  backgroundSize: '120%',
                  backgroundPosition: '40% 32%',
                  backgroundRepeat: 'no-repeat',
                  WebkitMaskImage: assets?.instructorMask ? `url(${assets.instructorMask})` : undefined,
                  maskImage: assets?.instructorMask ? `url(${assets.instructorMask})` : undefined,
                  WebkitMaskSize: '100% 100%',
                  maskSize: '100% 100%',
                  WebkitMaskRepeat: 'no-repeat',
                  maskRepeat: 'no-repeat',
                  transform: 'scaleX(-1)',
                }}
              />
            </div>

            {/* Text content */}
            <div className="flex-1 p-8 lg:p-12 flex flex-col justify-center">
              <div className="text-base md:text-xl text-black leading-[1.5] font-medium">
                <p className="mb-6">
                  Mantente al tanto de tu teléfono porque te contactaremos por llamada para confirmar la cita el día y la hora acordadas, una vez confirmada la sesión con tu asesor te enviaremos el enlace de la videollamada.
                </p>
                <p>
                  Es importante que contestes confirmando 👍 tu llamada, ya que estamos recibiendo muchísimas solicitudes y queremos hablar con personas que estén comprometidas en ser un caso de éxito.
                </p>
              </div>
            </div>
          </div>

          {/* Reminder card */}
          <div className={`mt-16 relative ${cbShadow} rounded-lg overflow-hidden w-full bg-gradient-to-r from-[#FFBF00] to-[#FF4000]`}>
            <div className="relative px-8 md:px-12 py-6">
              <p className="font-semibold text-white text-xl md:text-[32px] leading-[1.3] text-center">
                Recuerda conectarte puntual y estando en un lugar tranquilo y cómodo.
              </p>
            </div>
          </div>
        </div>
      </section>

      {/* ═══ TORN-PAPER: Cream → Black ═══ */}
      {assets?.tornTransition2000 && (
        <div className="relative z-10 bg-black -mt-[2px]">
          <img src={assets.tornTransition2000} alt="" className="w-full block scale-y-[-1]" />
        </div>
      )}

      {/* ═══ SECTION 4: Paso 3 — Descubre ═══ */}
      <section
        className="relative bg-black px-4 lg:px-16 py-20 lg:py-28 overflow-hidden"
        style={{
          backgroundImage: 'linear-gradient(rgba(255,255,255,0.07) 1px, transparent 1px), linear-gradient(90deg, rgba(255,255,255,0.07) 1px, transparent 1px)',
          backgroundSize: '48px 48px',
        }}
      >
        {/* Decorative pixels */}
        {assets && (
          <>
            <img src={assets.pixels.sm4} alt="" className="absolute top-20 left-6 w-20 opacity-60 pointer-events-none hidden lg:block" />
            <img src={assets.pixels.lg8} alt="" className="absolute top-32 left-4 w-10 opacity-60 pointer-events-none hidden lg:block" />
          </>
        )}

        <div className="relative z-10 max-w-[1280px] mx-auto text-center">
          <div className="mb-8">
            <StepBadge icon={LIGHTBULB_ICON}>
              Paso 3 • Descubre
            </StepBadge>
          </div>

          <h2 className="font-semibold text-white text-3xl md:text-[40px] leading-[1.2] mb-6 max-w-[720px] mx-auto">
            Descubre más acerca de la oportunidad de convertirte en{' '}
            <span className="bg-gradient-to-r from-[#FFBF00] to-[#FF4000] bg-clip-text text-transparent">
              Desarrollador Full-Stack
            </span>
          </h2>

          <div className="max-w-[720px] mx-auto mb-12">
            <p className="text-white text-lg md:text-xl leading-[1.2] mb-1">
              Disfruta de este video donde revelamos más datos, errores comunes y falsas creencias acerca del Desarrollo Full-Stack.
            </p>
            <p className="bg-gradient-to-r from-[#FFBF00] to-[#FF4000] bg-clip-text text-transparent text-lg md:text-xl leading-[1.2] font-semibold">
              Además te enseñaremos nuestra academia por dentro
            </p>
          </div>

          <div className="max-w-[1024px] mx-auto">
            <a
              href={STEP3_VIDEO_URL}
              target="_blank"
              rel="noopener noreferrer"
              className="block aspect-video relative group"
            >
              <img
                src={STEP3_THUMBNAIL}
                alt="Descubre la oportunidad"
                className="w-full h-full object-cover"
              />
              <div className="absolute inset-0 bg-black/40 group-hover:bg-black/50 transition-colors flex items-center justify-center z-0">
                <div className="w-16 h-16 md:w-20 md:h-20 bg-white/90 rounded-full flex items-center justify-center group-hover:scale-110 transition-transform">
                  <svg className="w-8 h-8 md:w-10 md:h-10 text-orange-500 ml-1" fill="currentColor" viewBox="0 0 24 24">
                    <path d="M8 5v14l11-7z" />
                  </svg>
                </div>
              </div>
              <img
                src={VIDEO_FRAME}
                alt=""
                className="absolute inset-0 w-full h-full pointer-events-none z-10"
              />
            </a>
          </div>
        </div>
      </section>

      {/* ═══ TORN-PAPER: Black → Footer (cream) ═══ */}
      {assets?.tornTransition2000 && (
        <div className="relative z-10 bg-black -mb-[2px]">
          <img src={assets.tornTransition2000} alt="" className="w-full block" />
        </div>
      )}

      {/* ═══ FOOTER ═══ */}
      <footer
        className="relative flex-shrink-0 z-10 overflow-hidden bg-[#F5EDE3]"
        style={paperboardBg}
      >
        {assets && (
          <img src={assets.pixels.lg5} alt="" className="absolute top-12 right-16 w-36 opacity-30 pointer-events-none hidden lg:block" />
        )}

        <div className="w-full max-w-[1280px] mx-auto px-6 lg:px-24 pt-20 pb-8 relative">
          <div className="flex flex-col gap-8 items-start">
            {assets?.footerLogo ? (
              <img src={assets.footerLogo} alt="ConquerBlocks" className="h-24" />
            ) : (
              <img src={assets?.logo} alt="ConquerBlocks" className="h-10" />
            )}
            <div className="text-[#222] text-sm leading-[1.5]">
              <p className="font-medium text-base">Contacto:</p>
              <p>+971 58 848 2637</p>
              <p>admisiones@conquerx.com</p>
            </div>
          </div>

          <div className="border-t border-[#222]/20 mt-12 mb-8" />

          <div className="flex flex-col md:flex-row justify-between items-start md:items-center gap-4 text-sm text-[#222]">
            <p>
              Conquer Blocks {new Date().getFullYear()} &reg; | Conquer Blocks &reg; es un trademark de Conquer X &reg;
            </p>
            <div className="flex gap-6">
              <a href="#" className="underline hover:text-black">Términos de uso</a>
              <a href="#" className="underline hover:text-black">Aviso legal</a>
            </div>
          </div>
        </div>
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
