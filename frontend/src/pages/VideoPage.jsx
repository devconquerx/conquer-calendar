import { useState, useCallback, useMemo } from 'react'
import VideoPlayer from '../components/vsl/VideoPlayer'
import AgendarButton from '../components/vsl/AgendarButton'
import { getTheme } from '../themes'
import { CB_CARD_SHADOW } from '../themes/conquerblocks'
import { sendVideoProgressToBackend } from '../api'
import { safeHtml } from '../lib/sanitize'
import { useRouter } from '../lib/router'

/* Página de video (VSL) standalone — entre la landing de lead y el StepForm.
   Muestra el video (autoplay muted + overlays), revela el botón al alcanzar el
   buttonPercent y, al pulsarlo, redirige al StepForm conservando el query string
   (name/email/phone/event_id/journey_id que vienen de la landing). */
export default function VideoPage({ school, region, formConfig, videoUrls, buttonPercent, nextUrl }) {
  const router = useRouter()
  const [showButton, setShowButton] = useState(false)

  const theme = getTheme(school?.slug)
  const isPaper = !!theme.paperboard
  const assets = theme.assets

  const video = formConfig?.video || {}
  const urls = videoUrls && videoUrls.length ? videoUrls : (video.videoUrls || [])
  const pct = buttonPercent || video.buttonPercent || 75
  const landing = formConfig?.landing || formConfig?.welcome || {}

  // Email para el tracking de progreso (viene como query param desde la landing).
  const email = useMemo(
    () => new URLSearchParams(window.location.search).get('email') || '',
    []
  )

  const handleShowButton = useCallback(() => setShowButton(true), [])

  const handleProgress = useCallback(
    (percent) => {
      sendVideoProgressToBackend({ email, percent, school: school?.slug, region })
    },
    [email, school, region]
  )

  // Siguiente etapa: el StepForm. Conserva el query string actual (prefill +
  // tracking). En la SPA navega con pushState; fuera de ella, recarga completa.
  const goToStepForm = useCallback(() => {
    const search = window.location.search || ''
    if (router) {
      router.navigate('stepform', { search })
      return
    }
    window.location.href = `${nextUrl}${search}`
  }, [router, nextUrl])

  if (isPaper) {
    return (
      <PaperboardVideoPage
        assets={assets}
        video={video}
        urls={urls}
        pct={pct}
        showButton={showButton}
        onShowButton={handleShowButton}
        onProgress={handleProgress}
        goToStepForm={goToStepForm}
        theme={theme}
        school={school}
      />
    )
  }

  return (
    <div className="min-h-screen overflow-x-hidden relative flex flex-col bg-[#0A0A0A] text-white">
      <main className="relative z-10 flex-1 w-full max-w-[920px] mx-auto px-5 flex flex-col">
        {/* Logo */}
        {assets?.logo && (
          <div className="py-4 flex justify-center">
            <img src={assets.logo} alt={school?.slug || ''} className="h-9 w-auto" />
          </div>
        )}

        {/* Titular (de la landing, si existe) */}
        {(landing.subtitle || landing.title) && (
          <div className="text-center mb-5 animate-fade-in">
            {landing.subtitle && (
              <p className="text-sm font-medium uppercase tracking-wide mb-2 text-orange-400">
                {landing.subtitle}
              </p>
            )}
            {landing.title && (
              <h1
                className="max-w-[760px] mx-auto text-xl md:text-2xl font-medium leading-[1.15] text-white"
                dangerouslySetInnerHTML={safeHtml(landing.title)}
              />
            )}
          </div>
        )}

        {/* Reproductor */}
        <div className="animate-fade-in">
          <VideoPlayer
            videoUrls={urls}
            buttonPercent={pct}
            onAgendarClick={goToStepForm}
            onShowButton={handleShowButton}
            onProgress={handleProgress}
          />
        </div>

        {/* Botón CTA — aparece al alcanzar el buttonPercent */}
        {showButton && <AgendarButton theme={theme} onClick={goToStepForm} />}
      </main>

      <div className="py-10" />
    </div>
  )
}

/* ═══ VSL paperboard (Blocks / Legal) — réplica de producción ═══
   Renderer compartido dirigido por tokens del tema (`theme.video` + `accent`):
   cabecera clara (paperboard #FAFAFA) con logo, badge pill y H1; transición de
   papel rasgado hacia una zona negra con retícula (grid) donde vive el video
   con glow de marca y el CTA pixelado; cierre con otra transición rasgada y
   footer claro con logo y píxeles decorativos. El acento (naranja Blocks / azul
   Legal) y los textos salen del tema; `config['video']` puede sobreescribirlos. */
function PaperboardVideoPage({ assets, video, urls, pct, showButton, onShowButton, onProgress, goToStepForm, theme, school }) {
  const v = theme.video || {}
  // Textos del hero: prioridad a config['video'], luego tokens del tema.
  const subtitle = video.subtitle || v.subtitle || 'Vídeo'
  const title = video.title || v.title || ''
  const badgeColor = v.badgeColor || '#0f172a'
  const titleColor = v.titleColor || '#0f172a'
  const titleSize = v.titleSize || 'text-2xl md:text-[32px]'
  const glow = v.glow || '0 2px 20px 6px rgba(127,193,255,0.28)'
  const headerLogoWidth = v.headerLogoWidth || '125px'
  const headerLogoWidthMobile = v.headerLogoWidthMobile || headerLogoWidth
  const footerLogoWidth = v.footerLogoWidth || '280px'
  const footerLogo = assets.footerLogo || assets.logo

  // Fondo claro de cabecera/footer: #FAFAFA + velo blanco 40% sobre paperboard.
  const paperStyle = {
    backgroundColor: '#FAFAFA',
    backgroundImage: `linear-gradient(rgba(255,255,255,0.4), rgba(255,255,255,0.4)), url(${assets.paperboardTexture})`,
    backgroundSize: 'auto, 50%',
  }
  // Badge pill: textura paperboard con velo blanco 60% + sombra en capas.
  const tagStyle = {
    backgroundImage: `linear-gradient(rgba(255,255,255,0.6), rgba(255,255,255,0.6)), url(${assets.paperboardTexture})`,
    backgroundSize: 'cover',
    boxShadow: CB_CARD_SHADOW,
  }
  // Zona oscura: negro + velo negro 15% sobre la retícula. `fixed` hace que la
  // retícula sea UN único fondo anclado al viewport, así las transiciones rasgadas
  // (transparentes) muestran exactamente la misma retícula que el resto de la zona
  // oscura, sin banda negra ni costuras (igual que producción, que pone la retícula
  // en el body y deja transparentes las secciones).
  const darkStyle = {
    backgroundColor: '#000',
    backgroundImage: `linear-gradient(rgba(0,0,0,0.15), rgba(0,0,0,0.15)), url(${assets.gridBackground})`,
    backgroundAttachment: 'fixed',
  }

  return (
    <div className="min-h-screen overflow-x-hidden relative flex flex-col font-funnel">
      {/* ── Cabecera clara ── */}
      <header className="relative" style={paperStyle}>
        {/* Píxeles decorativos laterales */}
        {assets.pixels?.deco2 && (
          <>
            <img src={assets.pixels.deco2} alt="" aria-hidden="true" className="hidden md:block absolute left-0 top-[25px] w-[150px] pointer-events-none select-none" />
            <img src={assets.pixels.deco2} alt="" aria-hidden="true" className="hidden md:block absolute right-0 top-[101px] w-[150px] pointer-events-none select-none" />
          </>
        )}
        <div className="relative max-w-[1024px] mx-auto px-5 lg:px-0 pt-4">
          {/* Logo vertical */}
          <div className="py-2 md:py-4 flex justify-center">
            <img
              src={assets.logo}
              alt={school?.slug || ''}
              className="h-auto w-[var(--logo-w-m)] md:w-[var(--logo-w)]"
              style={{ '--logo-w-m': headerLogoWidthMobile, '--logo-w': headerLogoWidth }}
            />
          </div>
          <div className="flex flex-col items-center gap-5 mb-4 mt-1.5 md:mt-0">
            {/* Badge pill — producción usa la fuente geométrica "Termina" y un
                triángulo ▶ sólido inline. Replicamos con Montserrat (la más cercana
                disponible) y el carácter ▶ a tamaño ligeramente menor que el texto. */}
            <div
              className="inline-flex items-center gap-2 rounded-full border px-4 py-1 text-sm font-medium"
              style={{ ...tagStyle, fontFamily: 'Montserrat, sans-serif', borderColor: badgeColor, color: badgeColor }}
            >
              <span className="text-[11px] leading-none">▶</span>
              {subtitle}
            </div>
            {/* Titular */}
            <h1
              className={`max-w-[1024px] mx-auto text-center ${titleSize} font-semibold leading-[1.1] [&_strong]:font-semibold`}
              style={{ color: titleColor }}
              dangerouslySetInnerHTML={safeHtml(title)}
            />
          </div>
        </div>
      </header>

      {/* ── Zona oscura: retícula continua que cubre las dos transiciones rasgadas
            y el contenido. Los wrappers de rasgado son TRANSPARENTES, así muestran
            esta misma retícula y no aparece ninguna banda/línea negra. ── */}
      <div className="flex-1 relative flex flex-col" style={darkStyle}>
        {/* Transición cabecera → zona oscura. El PNG es papel crema con borde
            rasgado; rotado 180° queda crema arriba (sigue a la cabecera) y el
            rasgado abajo. Lo transparente bajo el rasgado deja ver la retícula. */}
        {assets.tornTransition && (
          <div className="relative z-10 -mt-[5px] overflow-hidden pointer-events-none select-none">
            <img
              src={assets.tornTransition}
              alt=""
              aria-hidden="true"
              className="block w-full rotate-180"
            />
          </div>
        )}

        <main className="relative flex-1">
          <div className="max-w-[1064px] mx-auto px-2 md:px-5 pt-6 pb-4">
            <div
              className="animate-fade-in"
              style={{ boxShadow: glow }}
            >
              <VideoPlayer
                videoUrls={urls}
                buttonPercent={pct}
                onAgendarClick={goToStepForm}
                onShowButton={onShowButton}
                onProgress={onProgress}
              />
            </div>

            {/* Botón CTA — aparece al alcanzar el buttonPercent */}
            {showButton && <AgendarButton theme={theme} onClick={goToStepForm} />}

            <div className="h-[100px]" />
          </div>
        </main>

        {/* Transición zona oscura → footer. Sin rotar: rasgado arriba (lo
            transparente deja ver la retícula) y papel crema abajo. */}
        <div className="relative">
          {/* Píxel que asoma sobre el borde rasgado (solo el cuadrado superior). */}
          {assets.pixels?.sm7 && (
            <img src={assets.pixels.sm7} alt="" aria-hidden="true" className="hidden md:block absolute -top-[14px] left-[150px] w-[150px] z-0 pointer-events-none select-none" />
          )}
          {assets.tornTransition && (
            <div className="relative z-10 -mb-[1px] overflow-hidden pointer-events-none select-none">
              <img
                src={assets.tornTransition}
                alt=""
                aria-hidden="true"
                className="block w-full"
              />
            </div>
          )}
        </div>
      </div>

      {/* ── Footer claro ── */}
      {/* `isolate` acota los z-index de las capas al footer. Réplica del orden de
          producción: fondo crema → píxel izq (oculto, solo asoma arriba) → velo
          crema → píxel der (visible) → logo (encima, limpio). */}
      <footer className="relative isolate" style={paperStyle}>
        {/* Píxel izquierdo (móvil): queda DETRÁS del velo crema, así solo asoma por
            encima del footer sobre la transición — igual que producción (z-index bajo). */}
        {assets.pixels?.sm7 && (
          <img src={assets.pixels.sm7} alt="" aria-hidden="true" className="md:hidden absolute -top-[20px] left-6 w-[100px] z-0 pointer-events-none select-none" />
        )}
        {/* Velo crema (solo móvil): cubre el píxel izquierdo dentro del footer; la
            parte que sobresale por arriba queda visible. */}
        <div className="md:hidden absolute inset-0 z-[1]" style={paperStyle} />
        {/* Píxel derecho: por ENCIMA del velo, visible a la derecha del logo
            (producción). En desktop conserva su posición original arriba a la dcha. */}
        {assets.pixels?.lg8 && (
          <img src={assets.pixels.lg8} alt="" aria-hidden="true" className="absolute -top-[12px] right-4 w-[75px] z-[2] md:top-[13px] md:right-[15px] md:w-[100px] pointer-events-none select-none" />
        )}
        {/* z-10: el logo va SIEMPRE por encima de los píxeles decorativos. */}
        <div className="relative z-10 py-8 flex justify-center">
          {/* Móvil: logo vertical compacto (125px), igual que producción. */}
          <img src={assets.logo} alt={school?.slug || ''} className="md:hidden h-auto w-[125px]" />
          {/* Desktop: logo de footer a tamaño completo (sin cambios). */}
          <img src={footerLogo} alt={school?.slug || ''} className="hidden md:block h-auto" style={{ width: footerLogoWidth }} />
        </div>
      </footer>
    </div>
  )
}
