import { useEffect } from 'react'
import { leer } from '../lib/safeStorage'
import { getTheme } from '../themes'
import useTracking from '../hooks/useTracking'
import { fireAllSchedule } from '../lib/pixelEvents'
import { safeHtml } from '../lib/sanitize'

// Los assets y textos de la confirmación paperboard viven en el tema
// (theme.confirmation): cada marca aporta sus iconos, fotos, vídeos y copy.

/**
 * Página de confirmación de llamada — port 1:1 del funnel de Django (funnels).
 * Se muestra tras agendar en Calendly. Dispara el evento Schedule en todas las
 * plataformas (Meta/Google Ads/TikTok/GA4) al montar, usando el UUID de Calendly
 * y el schedule_event_id guardados en localStorage (igual que funnels).
 */
export default function Confirmation({ escuela = '', slug = '' }) {
  const baseTheme = getTheme(escuela, slug)
  // Rediseño por página: un tema puede pedir que SOLO su confirmación use el
  // sistema paperboard (hoy: Finance, que toma el diseño de Legal y conserva su
  // contenido vía `confirmationPaper`) sin cambiar el resto de etapas.
  const theme = !baseTheme.paperboard && baseTheme.confirmationVariant === 'paperboard'
    ? { ...baseTheme, ...baseTheme.confirmationPaper, paperboard: true, hexboard: false }
    : baseTheme
  /* El renderer paperboard necesita los tokens de contenido de ESE sistema
     (los 3 pasos: badges, copy, imágenes). No basta con que el tema tenga un
     bloque `confirmation`: Conquer Languages hereda el del tema por defecto vía
     `...defaultTheme` —que es para el renderer clásico, con clases de color en
     vez de copy— y entraba aquí con tokens ajenos, reventando el render de la
     confirmación en las 5 marcas de Languages. Se comprueba `paso1Badge`, que
     solo existe en las confirmaciones paperboard (Blocks, Legal, Finance). */
  const isPaper = !!theme.paperboard && !!theme.confirmation?.paso1Badge
  const assets = theme.assets
  const { eventId, journeyId } = useTracking()

  useEffect(() => {
    const calendlyEventUuid =
      leer('cqx_calendly_event_uuid') || ''
    const scheduleEventId =
      leer('cqx_schedule_event_id') || ''

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

  if (theme.hexboard && theme.confirmation) {
    return <HexConfirmation theme={theme} assets={assets} />
  }

  return <DefaultConfirmation escuela={escuela} theme={theme} />
}


/* ═══════════════════════════════════════════════════════
   Hexboard Confirmation (Finance) — réplica 1:1 de
   conquerfinance.com/confirmacion-llamada (medida en prod a 1440/768/390):
   fondo hexagonal de página (body contain), confeti + ¡Felicidades! (Ms Madi),
   banner azul con "Importante:" en rojo, 3 pasos con muescas triangulares
   entre secciones. Producción NO tiene PASO 4 ni footer.
   ═══════════════════════════════════════════════════════ */

// Resalta en negrita el fragmento `bold` dentro de `text` (mismo helper que el
// paperboard, con el peso que usa Finance).
function hexBold(text, bold) {
  if (!bold || typeof text !== 'string' || !text.includes(bold)) return text
  const i = text.indexOf(bold)
  return (
    <>
      {text.slice(0, i)}
      <strong className="font-bold">{bold}</strong>
      {text.slice(i + bold.length)}
    </>
  )
}

// Título de paso: "PASO N · resto" — el separador "·" va en Montserrat 700
// (paso-1-mira-este-video-3 en prod); el resto en Poppins 900 30px (20 móvil).
function HexStepHeading({ text, color }) {
  const parts = (text || '').split('·')
  const pre = parts[0]
  const post = parts.slice(1).join('·')
  return (
    <h2 className="text-[20px] leading-[24px] md:text-[30px] md:leading-[36px] font-black" style={{ color }}>
      {post ? (
        <>
          {pre.trim() + ' '}
          <span className="font-bold text-[30px] leading-[36px]" style={{ fontFamily: 'Montserrat, sans-serif' }}>·</span>
          {' ' + post.trim()}
        </>
      ) : text}
    </h2>
  )
}

function HexConfirmation({ theme, assets }) {
  const c = theme.confirmation
  const pageStyle = {
    backgroundColor: '#ffffff',
    ...(assets?.confHexFondo ? {
      backgroundImage: `url(${assets.confHexFondo})`,
      backgroundPosition: '50% 0',
      backgroundRepeat: 'no-repeat',
      backgroundSize: 'contain',
    } : {}),
    fontFamily: 'Poppins, sans-serif',
  }

  return (
    <div className="min-h-screen overflow-x-hidden text-[#212121]" style={pageStyle}>
      {/* Navbar transparente con logo centrado (70px, 75 móvil) */}
      <header className="h-[75px] md:h-[70px] pt-[10px] md:pt-0 flex items-center justify-center">
        <img src={assets?.logo} alt="" className="w-[180px] h-auto" />
      </header>

      {/* ═══ Hero: confeti + ¡Felicidades! + banner Importante + chevron ═══ */}
      <section className="px-[15px] md:px-[110px] pt-[10px] text-center">
        <div className="max-w-[806px] mx-auto">
          <img
            src={assets?.confetti} alt="" aria-hidden="true"
            className="mx-auto w-[80px] h-[86px] md:w-[100px] md:h-[106px] object-contain"
          />
          <p
            className="text-[66px] md:text-[73px] leading-[0.8] text-black"
            style={{ fontFamily: "'Ms Madi', cursive" }}
          >
            {c.felicidades || '¡Felicidades!'}
          </p>
          <h1 className="mt-[10px] text-[26px] leading-[0.97] md:text-[30px] md:leading-[0.7] font-black text-black">
            {c.heroTitle || 'Tu llamada ha sido reservada'}
          </h1>
          <div
            className="mt-5 rounded-[20px] md:rounded-[3px] p-5 md:px-[30px] md:py-[11px]"
            style={{ backgroundImage: c.bannerGradient || 'linear-gradient(90deg, #1c48af 14%, #2e6cff)' }}
          >
            <p className="text-[16px] leading-[1.28] font-normal md:text-[18px] md:leading-[27px] md:font-medium text-white">
              <strong className="font-extrabold text-[18px] leading-[27px]" style={{ color: c.importanteLabelColor || '#f65252' }}>
                {c.importanteLabel || 'Importante:'}
              </strong>{' '}
              {hexBold(c.importanteText, c.importanteTextBold)}
            </p>
          </div>
          <a href="#paso1" aria-label="Ir al paso 1" className="block mx-auto mt-[3px] md:mt-5 w-[86px] h-[57px] md:h-[92px]">
            <img src={assets?.doubleChevron} alt="" className="w-full h-full object-contain animate-bounce" />
          </a>
        </div>
      </section>

      {/* ═══ PASO 1: vídeo ═══ */}
      <section id="paso1" className="px-[10px] md:px-6 md:pt-[10px] text-center">
        <div className="max-w-[960px] mx-auto">
          <HexStepHeading text={c.paso1Badge} color={c.stepColor || '#1c48b0'} />
          <p className="mt-6 mx-auto max-w-[610px] text-[16px] leading-6 font-medium">
            {hexBold(c.paso1Text, c.paso1TextBold)}
          </p>
          {/* Patrón responsive de Bunny/Webflow (padding-top + iframe absoluto):
              en iOS/WebKit un iframe con h-full dentro de aspect-video no se
              dimensiona y el player quedaba en negro. */}
          <div className="mt-10 md:mt-[35px] relative w-full bg-black" style={{ paddingTop: '56.25%' }}>
            <iframe
              src={c.paso1Video}
              className="absolute inset-0 w-full h-full"
              allow="autoplay; fullscreen; picture-in-picture"
              allowFullScreen
              // Bunny valida el dominio que embebe por Referer; Django manda
              // Referrer-Policy: same-origin (el iframe cross-origin iría SIN
              // referer y la CDN responde 403 → player en negro en iOS/WebKit).
              referrerPolicy="strict-origin-when-cross-origin"
              title="Paso 1"
              style={{ border: 'none' }}
            />
          </div>
        </div>
      </section>

      {/* ═══ PASO 2: confirma tu cita (sección gris con muescas) ═══ */}
      <section className="relative mt-[50px] md:mt-[60px] bg-[#f4f4f4] px-[15px] md:px-6 pt-9 md:pt-[42px] pb-[73px] md:pb-[67px] lg:pb-[51px] text-center">
        {/* Muesca blanca (triángulo con brightness(2)) sobre el borde superior */}
        <img
          src={assets?.notchTriangle} alt="" aria-hidden="true"
          className="absolute -top-2 left-1/2 -translate-x-1/2 w-14 h-auto brightness-200"
        />
        <div className="max-w-[960px] mx-auto">
          <HexStepHeading text={c.paso2Badge} color={c.step2Color || '#345bb8'} />
          <div className="mt-6 md:mt-[23px] md:px-10 lg:px-[100px] flex flex-col md:flex-row items-center gap-[30px] text-center md:text-left">
            {c.paso2Image && (
              <img src={c.paso2Image} alt="" className="w-[200px] md:w-[377px] h-auto flex-shrink-0" />
            )}
            <div className="space-y-[26px]">
              {(c.paso2Paragraphs || []).map((p, i) => (
                <p
                  key={i}
                  className="text-[17px] leading-[25.5px] font-light [&_strong]:font-bold"
                  dangerouslySetInnerHTML={safeHtml(p)}
                />
              ))}
            </div>
          </div>
          <div className="mt-[37px] md:mt-[25px] inline-block w-full md:w-auto bg-[#e8e8e8] rounded-[20px] p-[10px] md:px-10">
            <p className="text-[17px] leading-[1.22] md:leading-[1.34] font-medium">
              {hexBold(c.reminderText, c.reminderTextBold)}
            </p>
          </div>
        </div>
        {/* Triángulo gris asomando hacia el PASO 3 (prod lo estira a 64×46) */}
        <img
          src={assets?.notchTriangle} alt="" aria-hidden="true"
          className="absolute -bottom-8 md:-bottom-11 left-1/2 -translate-x-1/2 w-16 h-[45px] md:h-[46px]"
        />
      </section>

      {/* ═══ PASO 3: entrevista (el thumb trae el play incrustado) ═══ */}
      <section className="px-[10px] md:px-6 pt-10 md:pt-[59px] pb-16 md:pb-[99px] text-center">
        <div className="max-w-[960px] mx-auto">
          <HexStepHeading text={c.paso3Badge} color={c.stepColor || '#1c48b0'} />
          <div className="mt-6 space-y-6 text-[16px] leading-6 font-medium">
            {c.paso3Subtitle && <p>{c.paso3Subtitle}</p>}
            {c.paso3Note && <p>{c.paso3Note}</p>}
          </div>
          <a href={c.paso3Video} target="_blank" rel="noopener noreferrer" className="block mt-[60px] md:mt-[35px]">
            <img src={c.paso3Thumbnail} alt="" className="w-full h-auto" />
          </a>
        </div>
      </section>
    </div>
  )
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

// Badge pill de cada paso. `big` = estilo grande (32px + icono); si no, pill
// pequeño de texto. `padClass`/`sizeClass`/`weightClass` permiten al tema fijar
// los valores exactos de producción (Blocks: 20px/500, padding 4px 16px).
// `texture` aplica el papel paperboard de fondo.
function StepBadge({ children, icon, big, texture, padClass, sizeClass, weightClass, wrap }) {
  const pad = padClass || (big ? 'px-4 py-1 rounded-2xl' : 'px-5 py-1.5 rounded-full')
  const size = sizeClass || (big ? 'text-2xl md:text-[32px]' : 'text-base md:text-lg')
  const weight = weightClass || 'font-semibold'
  // Por defecto el badge no parte línea; con `wrap` (p.ej. badges largos en móvil)
  // se permite que envuelva, centrado, como en producción.
  const wrapCls = wrap ? 'text-center' : 'whitespace-nowrap'
  return (
    <div
      className={`relative inline-flex items-center gap-3 ${pad} border border-[#BBB49B] ${cardShadow} overflow-hidden`}
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
        className={`relative font-['Funnel_Display',sans-serif] ${weight} ${size} leading-[1.25] text-black ${wrapCls}`}
      >
        {children}
      </p>
      {icon && <img src={icon} alt="" className={`relative ${big ? 'w-8 h-8' : 'w-5 h-5'}`} />}
    </div>
  )
}

// Resalta en negrita el fragmento `bold` dentro de `text` (p. ej. "47 segundos"
// en el texto del Paso 1, como en producción). Sin `bold`, devuelve el texto tal cual.
function withBold(text, bold) {
  if (!bold || typeof text !== 'string' || !text.includes(bold)) return text
  const i = text.indexOf(bold)
  return (
    <>
      {text.slice(0, i)}
      <strong className="font-bold">{bold}</strong>
      {text.slice(i + bold.length)}
    </>
  )
}

// Marco del vídeo: si el tema trae un SVG de marco se superpone; si no, borde
// redondeado de color `borderColor` (naranja en Blocks, azul en Legal) con un
// `glow` opcional. Producción de Blocks usa borde naranja 2px sin glow.
function VideoFrame({ frame, accent, borderColor, glow, children }) {
  if (frame) {
    return (
      <div className="aspect-video relative">
        {children}
        <img src={frame} alt="" className="absolute inset-0 w-full h-full pointer-events-none z-10" />
      </div>
    )
  }
  const ring = borderColor || accent?.ring || '#3E76FF'
  const shadow = glow !== undefined ? glow : '0 0 30px rgba(62,118,255,0.25)'
  return (
    <div
      className="aspect-video relative rounded-xl overflow-hidden"
      style={{ border: `2px solid ${ring}`, boxShadow: shadow === 'none' ? undefined : shadow }}
    >
      {children}
    </div>
  )
}

function PaperboardConfirmation({ theme, assets }) {
  const c = theme.confirmation
  // La confirmación puede traer su propia textura paperboard (Blocks usa una más
  // clara y fina que la del StepForm); si no, cae a la del tema.
  const texture = c.texture || assets?.paperboardTexture
  const px = assets?.pixels || {}

  // Fondo paperboard de las secciones crema. `paperboardTiled` replica producción
  // (textura tileada al 50% con velo blanco 0.4 sobre #FAFAFA); por defecto, la
  // textura a `cover` (comportamiento original de Legal).
  const paperboardBg = !texture
    ? undefined
    : c.paperboardTiled
      ? {
          backgroundColor: '#FAFAFA',
          backgroundImage: `linear-gradient(rgba(255,255,255,0.4), rgba(255,255,255,0.4)), url(${texture})`,
          backgroundSize: 'auto, 50%',
          backgroundRepeat: 'repeat',
          backgroundPosition: '0 0, 50% 0',
        }
      : { backgroundImage: `url(${texture})`, backgroundSize: 'cover', backgroundPosition: 'center' }
  const cardBg = texture
    ? {
        backgroundImage: `linear-gradient(rgba(255,255,255,0.5), rgba(255,255,255,0.5)), url(${texture})`,
        backgroundSize: 'cover',
        backgroundPosition: 'center',
      }
    : undefined
  // Fondo de las cajas naranjas (Importante / recordatorio): imagen
  // (card-background.png en Blocks) o degradado (Legal), según el tema.
  const boxBg = c.boxImage
    ? { backgroundImage: `url(${c.boxImage})`, backgroundSize: 'cover', backgroundPosition: 'center' }
    : { backgroundImage: c.boxGradient }
  const gridBg = {
    backgroundImage:
      'linear-gradient(rgba(255,255,255,0.07) 1px, transparent 1px), linear-gradient(90deg, rgba(255,255,255,0.07) 1px, transparent 1px)',
    backgroundSize: '48px 48px',
  }

  // Imagen del rasgado entre secciones: la confirmación puede traer la suya
  // (Blocks usa la de producción que combina con su paperboard); si no, la del tema.
  const torn = c.torn || assets?.tornTransition2000
  const heroWeight = c.heroWeight || 'font-semibold'
  const isInstr = c.paso2ImageMode === 'instructor'
  const maskRight = assets?.instructorMask ? `url(${assets.instructorMask})` : undefined
  const maskMobile = c.paso2MaskMobile ? `url(${c.paso2MaskMobile})` : undefined
  const paso2ImgStyle = {
    backgroundImage: `url(${c.paso2Image})`,
    backgroundSize: isInstr ? '120%' : 'cover',
    backgroundPosition: isInstr ? '40% 32%' : 'center',
    backgroundRepeat: 'no-repeat',
    WebkitMaskSize: '100% 100%',
    maskSize: '100% 100%',
    WebkitMaskRepeat: 'no-repeat',
    maskRepeat: 'no-repeat',
    transform: isInstr ? 'scaleX(-1)' : undefined,
    // Con máscara móvil (Blocks/Legal/Finance): borde ABAJO en móvil y borde
    // DERECHO en desktop. Las dos URLs viajan como CSS vars inline (dependen del
    // tema), pero `--p2mask` se decide por CLASE en el elemento
    // (`[--p2mask:var(--p2-bottom)] lg:[--p2mask:var(--p2-right)]`): si se
    // definiera inline, ninguna clase podría sobreescribirla y desktop quedaría
    // clavado en la máscara de abajo. Sin máscara móvil: siempre la derecha.
    ...(maskMobile
      ? {
          '--p2-right': maskRight,
          '--p2-bottom': maskMobile,
          WebkitMaskImage: 'var(--p2mask)',
          maskImage: 'var(--p2mask)',
        }
      : { WebkitMaskImage: maskRight, maskImage: maskRight }),
  }

  return (
    <div className="min-h-screen overflow-x-hidden relative flex flex-col font-['Funnel_Display',sans-serif] bg-black">

      {/* ═══ SECTION 1: Hero ═══ */}
      <section className={`relative bg-[#F5EDE3] px-4 lg:px-16 ${c.heroSectionPad || 'pt-12 pb-12'}`} style={paperboardBg}>
        {(c.heroDecoImg || px.deco2) &&
          (c.heroDecos || ['top-8 left-6 w-24 opacity-40', 'top-16 right-6 w-28 opacity-20']).map((cls, i) => (
            <img key={i} src={c.heroDecoImg || px.deco2} alt="" className={`absolute ${cls} pointer-events-none hidden lg:block`} />
          ))}

        {/* Navbar con logo. En Blocks (navbarLogoOnly) solo el logo centrado, sin
            tarjeta; en Legal se mantiene la tarjeta paperboard con borde. */}
        <header className={`relative z-10 ${c.navbarMb || 'mb-12'}`}>
          <div className="mx-auto" style={{ maxWidth: c.heroMaxWidth || '1280px' }}>
            {c.navbarLogoOnly ? (
              <div className="flex items-center justify-center py-4">
                <img src={assets?.logo} alt="" className={c.navLogoHeight || 'h-9'} />
              </div>
            ) : (
              <div
                className={`flex items-center justify-center py-5 rounded-lg border border-[#BBB49B] ${cardShadow} overflow-hidden`}
                style={cardBg}
              >
                <img src={assets?.logo} alt="" className="h-6" />
              </div>
            )}
          </div>
        </header>

        <div className="relative z-10 mx-auto text-center" style={{ maxWidth: c.heroMaxWidth || '1280px' }}>
          {c.heroIcon && (
            <div className={`mx-auto ${c.heroIconMb || 'mb-8'}`}>
              <img src={c.heroIcon} alt="" className={`${c.heroIconSize || 'w-24 h-24'} mx-auto`} />
            </div>
          )}

          <h1 className={`${c.heroTitleSize || 'text-3xl md:text-[40px]'} ${heroWeight} ${c.heroTitleLeading || 'leading-[1.2]'} text-black ${c.heroTitleMb || 'mb-8'}`}>
            <span className={`block ${c.felicidadesSize || 'text-4xl md:text-[40px]'}`} style={gradText(c.felicidadesGradient)}>
              {c.felicidades}
            </span>
            {c.heroTitle}
          </h1>

          {/* Caja Importante. La imagen redondeada se recorta (overflow-hidden)
              en la capa interna; el rayo se desborda por la esquina inferior
              derecha desde la capa externa (overflow visible). */}
          <div
            className={`relative w-full mx-auto`}
            style={{ maxWidth: c.boxMaxWidth || '640px' }}
          >
            <div className={`relative rounded-xl overflow-hidden ${c.boxShadowClass ?? cardShadow} ${c.boxPadX || 'px-8 md:px-12'} ${c.boxPadY || 'py-6'}`} style={boxBg}>
              <p className={`font-semibold text-white text-2xl md:text-[32px] leading-[1.15] text-center ${c.importanteTitleMb || 'mb-2'}`}>
                {c.importanteTitle}
              </p>
              <p className={`font-medium text-white ${c.importanteTextSize || 'text-lg md:text-xl'} leading-[1.25] text-center`}>
                {c.importanteText}
              </p>
            </div>
            {c.heroIconSmall && (
              <img
                src={c.heroIconSmall}
                alt=""
                className="absolute w-[80px] md:w-[111px] -bottom-[24px] -right-[20px] md:-bottom-[37px] md:-right-[37px] pointer-events-none"
              />
            )}
          </div>
        </div>
      </section>

      {/* ═══ TORN: cream → black ═══ */}
      {torn && (
        <div className="relative z-10 bg-black -mt-[2px]">
          <img src={torn} alt="" className="w-full block scale-y-[-1] -mt-[3px]" />
        </div>
      )}

      {/* ═══ SECTION 2: Paso 1 — vídeo ═══ */}
      <section className={`relative bg-black px-4 lg:px-16 ${c.paso1SectionPad || 'py-20 lg:py-28'}`} style={gridBg}>
        <div className="relative z-10 max-w-[1280px] mx-auto text-center">
          <div className={c.paso1BadgeMb || 'mb-8'}>
            <StepBadge big={c.badgeBig} icon={c.paso1BadgeIcon} texture={texture} padClass={c.badgePad} sizeClass={c.badgeText} weightClass={c.badgeWeight} wrap={c.badgeWrap}>
              {c.paso1Badge}
            </StepBadge>
          </div>
          <p className={`text-white ${c.paso1TextClass || 'font-medium text-lg md:text-xl leading-[1.3]'} ${c.paso1TextMb || 'mb-12'} max-w-[820px] mx-auto`}>
            {withBold(c.paso1Text, c.paso1TextBold)}
          </p>
          <div className="max-w-[1024px] mx-auto">
            <VideoFrame frame={c.videoFrame} accent={theme.accent} borderColor={c.videoBorderColor} glow={c.videoGlow}>
              <iframe
                src={c.paso1Video}
                className="w-full h-full relative z-0"
                allow="autoplay; fullscreen; picture-in-picture"
                allowFullScreen
                referrerPolicy="strict-origin-when-cross-origin"
                title="Paso 1"
                style={{ border: 'none' }}
              />
            </VideoFrame>
          </div>
        </div>
      </section>

      {/* ═══ TORN: black → cream (vídeo → Paso 2) ═══ */}
      {torn && (
        <div className="relative z-10 bg-black -mb-[2px]">
          <img src={torn} alt="" className="w-full block -mb-[3px]" />
        </div>
      )}

      {/* ═══ SECTION 3: Paso 2 — confirma tu cita ═══ */}
      <section className={`relative px-4 lg:px-16 ${c.paso2SectionPad || 'py-20'} bg-[#F5EDE3]`} style={paperboardBg}>
        {px.deco && (
          <img src={px.deco} alt="" className="absolute top-8 left-8 w-28 opacity-20 pointer-events-none hidden lg:block" />
        )}
        <div className="relative z-10 max-w-[1280px] mx-auto">
          <div className={`text-center ${c.paso2BadgeMb || 'mb-16'}`}>
            <StepBadge big={c.badgeBig} icon={c.paso2BadgeIcon} texture={texture} padClass={c.badgePad} sizeClass={c.badgeText} weightClass={c.badgeWeight} wrap={c.badgeWrap}>
              {c.paso2Badge}
            </StepBadge>
          </div>

          {/* Tarjeta: foto + texto */}
          <div
            className={`rounded-2xl overflow-hidden ${cardShadow} flex flex-col lg:flex-row border border-[#BBB49B] ${c.paso2CardMax || ''}`}
            style={{ ...cardBg, minHeight: c.paso2MinHeight || undefined }}
          >
            <div
              className={`${c.paso2ImgWidth || 'lg:w-[540px]'} flex-shrink-0 self-stretch ${c.paso2MobileBox || 'h-64'} lg:h-auto ${c.paso2MaskMobile ? '[--p2mask:var(--p2-bottom)] lg:[--p2mask:var(--p2-right)]' : ''}`}
              style={paso2ImgStyle}
            />

            <div className={`flex-1 ${c.paso2ContentPad || 'p-8 lg:p-12'} flex flex-col justify-center`}>
              {c.paso2Heading && (
                <div className={`relative flex items-center gap-4 ${c.paso2HeadingMb || 'mb-6'}`}>
                  {c.paso2HeadingIcon && <img src={c.paso2HeadingIcon} alt="" className={`${c.paso2IconClass || 'w-12 h-12'} flex-shrink-0`} />}
                  <h3 className={`text-black ${c.paso2HeadingClass || 'text-2xl md:text-[32px] font-semibold leading-[1.1]'}`}>
                    {c.paso2Heading}
                  </h3>
                  {/* En móvil (Blocks) el icono va pequeño, pegado al borde derecho de la
                      tarjeta y solapando la esquina inferior del título — como producción. */}
                  {c.paso2IconMobileFloat && c.paso2HeadingIcon && (
                    <img src={c.paso2HeadingIcon} alt="" className="lg:hidden absolute -right-7 -bottom-[34px] w-[50px] h-auto rotate-[10deg] pointer-events-none" />
                  )}
                </div>
              )}
              <div className={c.paso2ParagraphClass || 'text-base md:text-lg text-[#333] leading-[1.5] font-normal space-y-5'}>
                {(c.paso2Paragraphs || []).map((p, i) => (
                  <p key={i}>{p}</p>
                ))}
              </div>
              {c.paso2Divider && <div className="border-t border-[#BBB49B]/60 mt-8" />}
            </div>
          </div>

          {/* Caja recordatorio */}
          <div
            className={`${c.paso2ReminderMt || 'mt-12'} relative ${cardShadow} rounded-xl overflow-hidden w-full ${c.paso2CardMax || ''}`}
            style={boxBg}
          >
            <div className={`relative ${c.reminderPad || 'px-8 md:px-12 py-6'}`}>
              <p className={`text-white ${c.reminderTextClass || 'text-center font-semibold text-xl md:text-[28px] leading-[1.3]'}`}>
                {c.reminderText}
              </p>
            </div>
          </div>
        </div>
      </section>

      {/* ═══ TORN: cream → black ═══ */}
      {torn && (
        <div className="relative z-10 bg-black -mt-[2px]">
          <img src={torn} alt="" className="w-full block scale-y-[-1] -mt-[3px]" />
        </div>
      )}

      {/* ═══ SECTION 4: Paso 3 — perspectivas ═══ */}
      <section className={`relative bg-black px-4 lg:px-16 overflow-hidden ${c.paso3SectionPad || 'py-20 lg:py-28'}`} style={gridBg}>
        {px.deco && (
          <img src={px.deco} alt="" className="absolute top-20 left-6 w-20 opacity-60 pointer-events-none hidden lg:block" />
        )}
        <div className="relative z-10 max-w-[1280px] mx-auto text-center">
          <div className={c.paso3BadgeMb || 'mb-8'}>
            <StepBadge big={c.badgeBig} icon={c.paso3BadgeIcon} texture={texture} padClass={c.badgePad} sizeClass={c.badgeText} weightClass={c.badgeWeight} wrap={c.badgeWrap}>
              {c.paso3Badge}
            </StepBadge>
          </div>

          <h2 className={`font-semibold text-white ${c.paso3TitleSize || 'text-3xl md:text-[40px]'} ${c.paso3TitleLeading || 'leading-[1.2]'} ${c.paso3TitleMb || 'mb-6'} ${c.paso3TitleMaxW || 'max-w-[820px]'} mx-auto`}>
            {c.paso3TitlePre}
            <span style={gradText(c.accentGradient)}>{c.paso3TitleAccent}</span>
          </h2>

          <div className={`${c.paso3SubtitleMaxW || 'max-w-[760px]'} mx-auto ${c.paso3SubtitleBlockMb || 'mb-12'}`}>
            <p className={`${c.paso3SubtitleClass || 'text-white text-lg md:text-xl leading-[1.3]'} ${c.paso3SubtitleMb || 'mb-1'}`}>{c.paso3Subtitle}</p>
            {c.paso3SubtitleAccent && (
              <p className={c.paso3SubtitleAccentClass || 'text-lg md:text-xl leading-[1.3] font-semibold'} style={gradText(c.accentGradient)}>
                {c.paso3SubtitleAccent}
              </p>
            )}
          </div>

          <div className="max-w-[1024px] mx-auto">
            <a href={c.paso3Video} target="_blank" rel="noopener noreferrer" className="block group">
              <VideoFrame frame={c.videoFrame} accent={theme.accent} borderColor={c.videoBorderColor} glow={c.videoGlow}>
                <img
                  src={c.paso3Thumbnail}
                  alt=""
                  className="w-full h-full object-cover"
                  style={c.paso3ThumbFilter ? { filter: c.paso3ThumbFilter, transform: 'scale(1.03)' } : undefined}
                />
                <div className="absolute inset-0 flex items-center justify-center z-[5]">
                  {c.paso3PlayIcon ? (
                    <img src={c.paso3PlayIcon} alt="" className={`${c.paso3PlayClass || 'w-16 h-16 md:w-20 md:h-20'} group-hover:scale-110 transition-transform`} />
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
      {torn && (
        <div className="relative z-10 bg-black -mb-[2px]">
          <img src={torn} alt="" className="w-full block -mt-[3px]" />
        </div>
      )}

      {/* ═══ FOOTER ═══ */}
      <footer className="relative flex-shrink-0 z-10 overflow-hidden bg-[#F5EDE3]" style={paperboardBg}>
        {c.footerMode === 'minimal' ? (
          <>
            {/* Blocks: píxeles decorativos relativos al footer completo (uno a
                cada lado, como producción). Legal: el deco original centrado. */}
            {(c.footerDecos || []).map((d, i) => (
              <img key={i} src={(assets?.pixels || {})[d.img]} alt="" className={`absolute ${d.cls} pointer-events-none`} />
            ))}
            <div className={`relative w-full max-w-[1280px] mx-auto px-6 ${c.footerPadY || 'py-16'} flex justify-center`}>
              {!c.footerDecos && px.deco2 && (
                <img src={px.deco2} alt="" className="absolute top-8 right-10 w-24 opacity-40 pointer-events-none hidden lg:block" />
              )}
              <img src={assets?.logo} alt="" className={c.footerLogoHeight || 'h-16'} />
            </div>
          </>
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
              // Bunny valida el dominio que embebe por Referer; Django manda
              // Referrer-Policy: same-origin (el iframe cross-origin iría SIN
              // referer y la CDN responde 403 → player en negro en iOS/WebKit).
              referrerPolicy="strict-origin-when-cross-origin"
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
