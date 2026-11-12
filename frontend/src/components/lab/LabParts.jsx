import { safeHtml } from '../../lib/sanitize'
import { labCssVars } from '../../themes/lab'

/* Piezas comunes de las páginas del sistema Conquer Lab (landing, vídeo…).
   Todas leen el color de las CSS vars --lab-* que pone <LabPage>, así que no
   saben de qué marca son. */

// Tarjeta (Tarjeta · papel blanco): fondo blanco, borde 12 % y r16. El borde va
// como outline hacia dentro: en Figma es una capa de fondo y no suma alto, y
// con `border` cada tarjeta crecía 2px.
export const LAB_CARD = 'bg-white outline outline-1 -outline-offset-1 outline-[color:var(--lab-line)] rounded-2xl'

// Titular con la convención de la BD: <strong> = acento caligráfico de marca.
export const LAB_H1 = 'max-w-[970px] font-semibold text-[24px] leading-[32px] md:text-[32px] md:leading-[42px] tracking-[-0.32px] [&_strong]:font-normal [&_strong]:[font-family:var(--lab-script)] [&_strong]:text-[27px] md:[&_strong]:text-[36px] [&_strong]:[background-image:var(--lab-text-gradient)] [&_strong]:bg-clip-text [&_strong]:text-transparent [&_strong]:[-webkit-box-decoration-break:clone] [&_strong]:[box-decoration-break:clone] [&_strong]:px-[0.04em]'

// Raíz de página: tokens de marca + papel blanco en mosaico (Superficie ·
// Papel blanco). En Figma cada sección lleva su Superficie, pero es la misma
// imagen sin costuras, así que va una sola vez aquí.
export function LabPage({ lab, children }) {
  const style = {
    ...labCssVars(lab),
    backgroundColor: '#EFEFEF',
    backgroundImage: lab.paper ? `url(${lab.paper})` : undefined,
    backgroundSize: lab.paperTile,
    backgroundRepeat: 'repeat',
    backgroundPosition: 'left top',
  }
  return (
    <div className="min-h-screen overflow-x-hidden flex flex-col font-['Inter',sans-serif] text-[color:var(--lab-ink)]" style={style}>
      {children}
    </div>
  )
}

// Barra · logo: tarjeta blanca a todo el ancho con el logo centrado.
export function LabLogoBar({ lab, brand }) {
  return (
    <div className={`${LAB_CARD} w-full h-[60px] md:h-[76px] flex items-center justify-center`}>
      <img src={lab.logo} alt={brand} width="220" height="24" className="w-[180px] md:w-[220px] h-auto" />
    </div>
  )
}

// Tag: etiqueta tintada con esquinas redondeadas y sombra. Sobre una banda de
// color va en papel (`style` con el fondo gris + textura).
export function LabTag({ html, style }) {
  return (
    <span
      style={style}
      className="inline-flex items-center justify-center px-[13.5px] py-[4.5px] rounded-[4.5px] bg-[color:var(--lab-tint)] border-[0.75px] border-[rgba(96,96,96,0.6)] drop-shadow-[3px_4px_3px_rgba(0,0,0,0.25)] font-semibold text-base leading-5 md:text-[18px] md:leading-[22px] text-[#666]"
      dangerouslySetInnerHTML={safeHtml(html)}
    />
  )
}

// Rasgado de papel arriba y abajo de una banda (Transición papel blanco).
export function LabTorn({ src }) {
  if (!src) return null
  return (
    <>
      <img src={src} alt="" aria-hidden="true" className="absolute left-0 top-0 w-full h-[24px] md:h-[35px] object-cover pointer-events-none select-none" />
      <img src={src} alt="" aria-hidden="true" className="absolute left-0 bottom-0 w-full h-[24px] md:h-[35px] object-cover rotate-180 pointer-events-none select-none" />
    </>
  )
}

// Botón (Button · Fill=Gradient): degradado de marca y la esquina inferior
// derecha en recto, que es la silueta de la línea.
export const LAB_BUTTON = 'rounded-[28px] rounded-br-none text-white uppercase font-semibold flex items-center justify-center gap-2 hover:brightness-105 active:scale-[0.99] transition-all disabled:opacity-50'
export const LAB_BUTTON_STYLE = { backgroundImage: 'var(--lab-gradient)' }

// 99 · Footer: logo, (disclaimer), divisor y legales.
export function LabFooter({ lab, footer = {}, disclaimer }) {
  const brand = footer.copyrightBrand || 'Conquer'
  return (
    <footer className="w-full px-4 md:px-16 pt-10 md:pt-[72px] pb-10 flex flex-col items-center gap-8 mt-auto">
      <img src={lab.logo} alt={brand} width="220" height="24" loading="lazy" className="w-[180px] md:w-[220px] h-auto" />
      {disclaimer && (
        <div className="max-w-[1000px] text-center text-xs leading-[18px] opacity-70 space-y-1.5">
          {(Array.isArray(disclaimer) ? disclaimer : [disclaimer]).map((line, i) => <p key={i}>{line}</p>)}
        </div>
      )}
      <div className="w-full h-px bg-[color:var(--lab-n300)]" />
      <div className="w-full flex flex-col xl:flex-row items-center xl:items-start justify-between gap-4 text-sm leading-[21px] text-center xl:text-left">
        <p>{brand} {new Date().getFullYear()} &reg; | ConquerX LLC | 16192 Coastal Highway, Lewes 19958, Delaware, USA</p>
        <nav className="flex flex-wrap justify-center gap-x-6 gap-y-2 flex-shrink-0">
          <a href={footer.legal?.cookies} target="_blank" rel="noopener noreferrer" className="underline">Política de Cookies</a>
          <a href={footer.legal?.privacy} target="_blank" rel="noopener noreferrer" className="underline">Política de Privacidad</a>
          <a href={footer.legal?.terms} target="_blank" rel="noopener noreferrer" className="underline">Términos y Condiciones</a>
        </nav>
      </div>
    </footer>
  )
}
