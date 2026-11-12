import { safeHtml } from '../../lib/sanitize'
import { LAB_CARD, LabPage, LabLogoBar, LabTag, LabTorn, LabFooter } from './LabParts'
import { LAB_TEXTURE_MASK } from '../../themes/lab'

/* ═══ Confirmación de llamada "Conquer Lab" ═══
   Réplica de Figma (Languages · Embudo 1 · Confirmación llamada). Estructura:
     01 Cabecera — logo, medalla, "¡Felicidades!" + H2 y la caja "Importante"
     02 Paso 1   — banda de color: tag, texto y el vídeo de Bunny
     03 Paso 2   — papel: tarjeta foto + texto y el recordatorio
     04 Paso 3   — banda de color: título, subtítulo y la portada del vídeo
     99 Footer
   Los vídeos, enlaces y el copy de los pasos 1 y 3 salen de
   `theme.confirmation` (los mismos de la confirmación actual); lo que Figma
   reescribe (Paso 2) viene de `theme.lab.confirmation`. El evento Schedule lo
   sigue disparando <Confirmation> al montar: esto solo pinta. */

// Glow de marca alrededor de los vídeos (efecto Languages/Glow).
const GLOW = '0 56px 60px 0 color-mix(in srgb, var(--lab-middle) 20%, transparent), -36px 0 50px 0 color-mix(in srgb, var(--lab-start) 20%, transparent), 0 -20px 30px 0 color-mix(in srgb, var(--lab-start) 20%, transparent), 36px 0 36px 0 color-mix(in srgb, var(--lab-end) 20%, transparent)'

// "Conquer shadow" del recordatorio.
const SOFT_SHADOW = '0 2px 5px rgba(0,0,0,0.1), 0 9px 9px rgba(0,0,0,0.09), 0 20px 12px rgba(0,0,0,0.05), 0 36px 14px rgba(0,0,0,0.01)'

// Acento caligráfico con el degradado de marca (o blanco sobre la banda).
const SCRIPT = '[font-family:var(--lab-script)] font-normal'
const SCRIPT_GRADIENT = `${SCRIPT} [background-image:var(--lab-text-gradient)] bg-clip-text text-transparent px-[0.04em]`

function withBold(text, bold) {
  if (!bold || typeof text !== 'string' || !text.includes(bold)) return text
  const i = text.indexOf(bold)
  return (
    <>
      {text.slice(0, i)}
      <strong className="font-semibold">{bold}</strong>
      {text.slice(i + bold.length)}
    </>
  )
}

// Banda de color (Superficie · Gradiente) con rasgado de papel arriba y abajo.
function Band({ lab, texture = true, className = '', children }) {
  return (
    <section className={`relative w-full overflow-hidden px-4 md:px-16 ${className}`} style={{ backgroundImage: lab.bandBackground }}>
      {texture && lab.bandTexture && (
        <div
          aria-hidden="true"
          className="absolute inset-0 pointer-events-none bg-cover bg-center"
          style={{ backgroundImage: `url(${lab.bandTexture})`, WebkitMaskImage: LAB_TEXTURE_MASK, maskImage: LAB_TEXTURE_MASK }}
        />
      )}
      <LabTorn src={lab.torn} />
      <div className="relative flex flex-col items-center">{children}</div>
    </section>
  )
}

export default function LabConfirmation({ theme }) {
  const lab = theme.lab
  const c = theme.confirmation || {}
  const lc = lab.confirmation || {}
  const footer = c.footer ? { ...theme.footer, ...c.footer } : theme.footer
  const brand = footer?.copyrightBrand || 'Conquer'
  // Sobre la banda el tag va en papel (gris con la textura), no tintado.
  const paperTag = { backgroundColor: '#EDEDED', backgroundImage: lab.paper ? `url(${lab.paper})` : undefined, backgroundSize: lab.paperTile }

  return (
    <LabPage lab={lab}>
      {/* ── 01 · Cabecera ── */}
      <header className="w-full px-4 md:px-16 pt-4 md:pt-[28px] pb-16 md:pb-24 flex flex-col items-center gap-8">
        <LabLogoBar lab={lab} brand={brand} />
        <div className="w-full max-w-[900px] pt-2 md:pt-6 flex flex-col items-center gap-6 text-center">
          {lc.heroIcon && (
            <span className="relative w-24 h-24 md:w-[120px] md:h-[120px]" aria-hidden="true">
              <span className="absolute inset-x-0 top-[-4.17%] bottom-[-12.5%]">
                <img src={lc.heroIcon} alt="" className="block w-full h-full" />
              </span>
            </span>
          )}
          <h1 className="font-semibold tracking-[-0.72px]">
            <span className={`block text-[44px] leading-[48px] md:text-[54px] md:leading-[58px] ${SCRIPT_GRADIENT}`}>
              {c.felicidades || '¡Felicidades!'}
            </span>
            <span className="block text-[32px] leading-[40px] md:text-[48px] md:leading-[58px]">{c.heroTitle || 'Tu llamada ha sido reservada'}</span>
          </h1>
        </div>
        <div
          className="relative w-full max-w-[760px] rounded-2xl overflow-hidden outline outline-1 -outline-offset-1 outline-[color:var(--lab-line)] px-6 py-7 md:px-12 md:py-9 flex flex-col items-center gap-2 text-center text-white"
          style={{ backgroundImage: lab.bandBackground }}
        >
          <p className="font-semibold text-2xl leading-8 md:text-[32px] md:leading-[42px] tracking-[-0.32px]">{c.importanteTitle || 'Importante'}</p>
          <p className="text-lg leading-7 md:text-xl md:leading-[30px]">{c.importanteText}</p>
        </div>
      </header>

      {/* ── 02 · Paso 1 · Mira este vídeo ── */}
      <Band lab={lab} className="py-20 md:py-[120px]">
        {c.paso1Badge && <LabTag html={c.paso1Badge} style={paperTag} />}
        {c.paso1Text && (
          <p className="mt-7 max-w-[820px] text-center text-white text-lg leading-7 md:text-xl md:leading-[30px]">
            {withBold(c.paso1Text, c.paso1TextBold)}
          </p>
        )}
        {c.paso1Video && (
          <div className="mt-7 w-full max-w-[1040px] aspect-video rounded-2xl md:rounded-[28px] overflow-hidden bg-black" style={{ boxShadow: GLOW }}>
            <iframe
              src={c.paso1Video}
              className="w-full h-full"
              allow="autoplay; fullscreen; picture-in-picture"
              allowFullScreen
              referrerPolicy="strict-origin-when-cross-origin"
              title="Paso 1"
              style={{ border: 'none' }}
            />
          </div>
        )}
      </Band>

      {/* ── 03 · Paso 2 · Confirma tu cita ── */}
      <section className="w-full px-4 md:px-16 py-16 md:py-28 flex flex-col items-center gap-8">
        {c.paso2Badge && <LabTag html={c.paso2Badge} />}
        <div className={`${LAB_CARD} w-full max-w-[1140px] overflow-hidden flex flex-col lg:flex-row`}>
          {(lc.paso2Image || c.paso2Image) && (
            <img
              src={lc.paso2Image || c.paso2Image}
              alt=""
              width="520"
              height="440"
              loading="lazy"
              className="w-full lg:w-[45.6%] aspect-[520/440] object-cover flex-shrink-0"
            />
          )}
          <div className="flex-1 min-w-0 px-5 py-8 md:px-12 md:py-10 lg:px-14 lg:py-12 flex flex-col justify-center gap-4">
            <h2 className="font-semibold text-2xl leading-8 md:text-[32px] md:leading-[42px] tracking-[-0.32px]">
              {lc.paso2HeadingPre || c.paso2Heading}
              {lc.paso2HeadingAccent && <span className={`text-[27px] md:text-[36px] ${SCRIPT_GRADIENT}`}>{lc.paso2HeadingAccent}</span>}
            </h2>
            {(lc.paso2Paragraphs || c.paso2Paragraphs || []).map((p, i) => (
              <p key={i} className="text-base leading-6 md:text-lg md:leading-[27px] [&_strong]:font-semibold" dangerouslySetInnerHTML={safeHtml(p)} />
            ))}
          </div>
        </div>
        {c.reminderText && (
          <div
            className="w-full max-w-[1140px] rounded-2xl bg-[color:var(--lab-tint)] outline outline-1 -outline-offset-1 outline-[color:var(--lab-line)] px-6 py-6 md:px-10 md:py-7 text-center"
            style={{ boxShadow: SOFT_SHADOW }}
          >
            <p className="font-semibold text-lg leading-7 md:text-xl md:leading-[30px] text-[color:var(--lab-middle)]">{c.reminderText}</p>
          </div>
        )}
      </section>

      {/* ── 04 · Paso 3 · Descubre ── (en Figma esta banda va sin textura) */}
      <Band lab={lab} texture={false} className="py-20 md:py-[120px]">
        {c.paso3Badge && <LabTag html={c.paso3Badge} style={paperTag} />}
        <div className="mt-7 w-full max-w-[860px] flex flex-col items-center gap-4 text-center text-white">
          <h2 className="font-semibold text-[32px] leading-[40px] md:text-[48px] md:leading-[58px] tracking-[-0.72px]">
            {c.paso3TitlePre}
            {c.paso3TitleAccent && <span className={`text-[36px] md:text-[54px] ${SCRIPT}`}>{c.paso3TitleAccent}</span>}
          </h2>
          {c.paso3Subtitle && <p className="text-base leading-6 md:text-lg md:leading-[27px]">{c.paso3Subtitle}</p>}
          {c.paso3SubtitleAccent && <p className="font-semibold text-base leading-6 md:text-lg md:leading-[27px]">{c.paso3SubtitleAccent}</p>}
        </div>
        {c.paso3Thumbnail && (
          <a
            href={c.paso3Video}
            target="_blank"
            rel="noopener noreferrer"
            className="group mt-7 relative block w-full max-w-[1040px] aspect-video rounded-2xl md:rounded-[28px] overflow-hidden bg-black"
            style={{ boxShadow: GLOW }}
          >
            <img src={c.paso3Thumbnail} alt="" loading="lazy" className="absolute inset-0 w-full h-full object-cover" />
            <span className="absolute inset-0 bg-[linear-gradient(146deg,rgba(42,58,66,0.4)_0%,rgba(13,20,24,0.4)_89%)]" aria-hidden="true" />
            {/* Play: círculo blanco de 84px con sombra. */}
            <span className="absolute inset-0 flex items-center justify-center" aria-hidden="true">
              <span className="w-14 h-14 md:w-[84px] md:h-[84px] rounded-full bg-white flex items-center justify-center drop-shadow-[0_8px_12px_rgba(0,0,0,0.2)] group-hover:scale-110 transition-transform">
                <svg viewBox="0 0 24 24" className="w-5 h-5 md:w-7 md:h-7 ml-1 text-[color:var(--lab-ink)]" fill="currentColor"><path d="M8 5v14l11-7z" /></svg>
              </span>
            </span>
          </a>
        )}
      </Band>

      <LabFooter lab={lab} footer={footer} />
    </LabPage>
  )
}
