import VideoPlayer from '../vsl/VideoPlayer'
import { safeHtml } from '../../lib/sanitize'
import { LAB_H1, LAB_BUTTON, LAB_BUTTON_STYLE, LabPage, LabLogoBar, LabTag, LabTorn, LabFooter } from './LabParts'

/* ═══ Página de vídeo "Conquer Lab" ═══
   Réplica de Figma (Languages · Embudo 2 · Video clase). Estructura (1440):
     01 Cabecera — barra con logo, tag y H1 (sobre papel)
     02 Vídeo    — banda blanca con rasgado arriba y abajo, sello de marca de
                   agua, reproductor r28 con el glow de marca y el CTA
     99 Footer   — el mismo de la landing
   El reproductor es el de siempre (overlays, seguimiento de progreso, CTA al
   llegar al %); aquí solo cambia el envoltorio. */

// Glow de marca (efecto Languages/Glow: cuatro sombras al 20 % con las tres
// paradas del degradado). Va por CSS vars para valer en cualquier marca.
const GLOW = '0 56px 60px 0 color-mix(in srgb, var(--lab-middle) 20%, transparent), -36px 0 50px 0 color-mix(in srgb, var(--lab-start) 20%, transparent), 0 -20px 30px 0 color-mix(in srgb, var(--lab-start) 20%, transparent), 36px 0 36px 0 color-mix(in srgb, var(--lab-end) 20%, transparent)'

export default function LabVideoPage({ theme, video, urls, pct, showButton, onShowButton, onProgress, goToStepForm, school, hideFooter = false }) {
  const lab = theme.lab
  const v = theme.video || {}
  const footer = theme.footer || {}
  const brand = footer.copyrightBrand || 'Conquer'
  const subtitle = video.subtitle || v.subtitle || ''
  const title = video.title || v.title || ''
  const buttonText = video.buttonText || 'Agendar sesión de consultoría gratuita'

  return (
    <LabPage lab={lab}>
      {/* ── 01 · Cabecera ── */}
      <header className="w-full px-4 md:px-16 pt-4 md:pt-[28px] pb-14 md:pb-24 flex flex-col items-center gap-8 md:gap-10">
        <LabLogoBar lab={lab} brand={brand} />
        <div className="w-full max-w-[1000px] md:pt-8 flex flex-col items-center gap-5 text-center">
          {subtitle && <LabTag html={subtitle} />}
          {title && <h1 className={LAB_H1} dangerouslySetInnerHTML={safeHtml(title)} />}
        </div>
      </header>

      {/* ── 02 · Vídeo ── */}
      <section className="relative w-full overflow-hidden bg-white px-4 md:px-16 py-16 md:py-28 flex flex-col items-center gap-8 md:gap-12">
        {/* Sello plano de marca de agua (8 % de opacidad), asomando por la
            esquina superior derecha como en Figma. */}
        {lab.seal && (
          <img
            src={lab.seal}
            alt=""
            aria-hidden="true"
            className="hidden md:block absolute top-[-92px] left-[calc(50%+218px)] w-[780px] max-w-none opacity-[0.08] pointer-events-none select-none"
          />
        )}
        <LabTorn src={lab.torn} />

        <div className="relative w-full max-w-[1140px] rounded-2xl md:rounded-[28px] overflow-hidden animate-fade-in" style={{ boxShadow: GLOW }}>
          <VideoPlayer
            videoUrls={urls}
            buttonPercent={pct}
            showControls={!!video.showControls}
            onAgendarClick={goToStepForm}
            onShowButton={onShowButton}
            onProgress={onProgress}
            theme={theme}
          />
        </div>

        {/* CTA — aparece al alcanzar el buttonPercent. Reserva su alto para
            que la página no salte cuando sale. */}
        <div className="relative min-h-[56px] w-full flex justify-center">
          {showButton && (
            <button
              onClick={goToStepForm}
              className={`${LAB_BUTTON} animate-fade-in w-full md:w-auto min-h-14 px-6 md:px-10 py-3 text-base md:text-[22px] leading-[22px] text-center`}
              style={LAB_BUTTON_STYLE}
            >
              {buttonText}
            </button>
          )}
        </div>
      </section>

      {!hideFooter && <LabFooter lab={lab} footer={footer} />}
    </LabPage>
  )
}
