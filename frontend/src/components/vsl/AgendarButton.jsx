// Borde pixelado del CTA de producción (clip-path copiado del botón real).
export const CB_PIXEL_CLIP =
  'polygon(97.74% 73.83%, 97.74% 82.56%, 100% 82.56%, 100% 100%, 95.47% 100%, 95.47% 91.28%, 81.5% 91.28%, 81.5% 100%, 19.87% 100%, 19.87% 91.28%, 9.06% 91.28%, 9.06% 100%, 2.26% 100%, 2.26% 80.24%, 0% 80.24%, 0% 26.16%, 2.26% 26.16%, 2.26% 17.44%, 0% 17.44%, 0% 0%, 4.53% 0%, 4.53% 8.72%, 12.82% 8.72%, 12.82% 0%, 72.03% 0%, 72.03% 8.72%, 88.67% 8.72%, 88.67% 0%, 97.74% 0%, 97.74% 8.72%, 100% 8.72%, 100% 73.83%)'

// Tamaños del CTA: `lg` para el botón principal bajo el vídeo, `sm` (más
// compacto y responsive) para reutilizarlo dentro del overlay del reproductor.
const CTA_SIZES = {
  lg: { paper: 'text-base md:text-lg px-[30px] md:px-10 py-5', plain: 'py-4 px-8 text-lg', hex: 'text-base md:text-lg px-8 md:px-10 py-4 md:py-5' },
  sm: { paper: 'text-sm md:text-base px-5 md:px-9 py-2 md:py-4', plain: 'py-2 px-5 md:px-7 text-base', hex: 'text-sm md:text-base px-5 md:px-8 py-2 md:py-3' },
}

/* Botón CTA reutilizable con el estilo de producción: pixelado + degradado
   naranja (tema paperboard/Blocks) o naranja redondeado (resto de temas). */
export function CtaButton({ theme, onClick, text, size = 'lg' }) {
  const isPaper = !!theme?.paperboard
  const accent = theme?.accent || {}
  const s = CTA_SIZES[size] || CTA_SIZES.lg

  if (isPaper) {
    return (
      <button
        onClick={onClick}
        className={`text-white ${s.paper} uppercase text-center leading-[1.25] hover:brightness-110 active:scale-[0.98] transition-all`}
        style={{
          fontFamily: 'Montserrat, sans-serif',
          backgroundImage: accent.buttonGradient || 'linear-gradient(90deg, #FFBF00, #FF4000)',
          fontWeight: accent.ctaWeight || accent.buttonWeight || '800',
          // `accent.buttonClip: 'none'` deja el CTA plano (Languages).
          clipPath: accent.buttonClip || CB_PIXEL_CLIP,
        }}
      >
        {text}
      </button>
    )
  }

  // Hexboard (Finance): pill con el gradiente azul de producción (cf-video.css
  // #js-videolitics-calendly-container a): radio 85px, outline 4px
  // rgba(118,157,255,.28), Montserrat 800 18px y padding 20/40 en desktop;
  // 16px/600 con padding 10/30 y ancho 90% en móvil (≤640px).
  if (theme?.hexboard) {
    const hexSize = size === 'sm'
      ? 'text-[14px] sm:text-[16px] px-5 py-2 sm:px-7 sm:py-3'
      : 'w-[90%] sm:w-auto text-[16px] font-semibold px-[30px] py-[10px] sm:text-[18px] sm:font-extrabold sm:px-[40px] sm:py-[20px]'
    return (
      <button
        onClick={onClick}
        className={`text-white ${hexSize} uppercase text-center leading-[1.25] rounded-[85px] hover:brightness-110 active:scale-[0.98] transition-all`}
        style={{
          fontFamily: 'Montserrat, sans-serif',
          backgroundImage: accent.buttonGradient || 'linear-gradient(95deg, #1c48b0 36%, #5e94ff)',
          boxShadow: '0 0 0 4px rgba(118,157,255,0.28)',
        }}
      >
        {text}
      </button>
    )
  }

  return (
    <button
      onClick={onClick}
      className={`${s.plain} text-white font-bold rounded-xl active:scale-[0.98] transition-all flex items-center justify-center gap-2 ${theme?.landing?.form?.button || 'bg-orange-500 hover:bg-orange-600'}`}
    >
      {text}
    </button>
  )
}

export default function AgendarButton({ theme, onClick, text = 'Agendar Sesión de Consultoría Gratuita' }) {
  // Finance (hexboard): márgenes del contenedor del CTA de producción
  // (#js-videolitics-calendly-container: margin 2rem arriba / 3rem abajo).
  const spacing = theme?.hexboard ? 'mt-8 mb-12' : 'mt-8 animate-fade-in'
  return (
    <div className={`flex justify-center ${spacing}`}>
      <CtaButton theme={theme} onClick={onClick} text={text} size="lg" />
    </div>
  )
}
