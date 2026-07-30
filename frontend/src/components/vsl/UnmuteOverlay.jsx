import { CtaButton } from './AgendarButton'

/* Overlay de activación de audio — réplica de producción: icono de altavoz
   tachado, dos líneas de texto y botón "VER VÍDEO" (mismo estilo que el CTA
   "Agendar"). */
export default function UnmuteOverlay({ onUnmute, theme }) {
  // Finance (hexboard): réplica del modal de videolitics de producción
  // (cf-video.css): fondo negro 80%, Inter con text-shadow, icono 40/120px y
  // botón plano #5996e1 (radio 5, uppercase, 500; 20px de fuente en ≥640).
  if (theme?.hexboard) {
    return (
      <div
        className="absolute inset-0 z-10 grid place-items-center bg-black/80 p-4 cursor-pointer"
        style={{ fontFamily: 'Inter, sans-serif' }}
        onClick={onUnmute}
      >
        <div className="text-center text-white">
          <svg
            xmlns="http://www.w3.org/2000/svg"
            className="w-10 h-10 sm:w-[120px] sm:h-[120px] mx-auto mb-[5px] sm:mb-[10px] text-white"
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
            strokeWidth={1.2}
          >
            <path strokeLinecap="round" strokeLinejoin="round" d="M6.75 8.25l4.72-4.72a.75.75 0 011.28.53v15.88a.75.75 0 01-1.28.53l-4.72-4.72H4.51c-.88 0-1.704-.507-1.938-1.354A9.009 9.009 0 012.25 12c0-.83.112-1.633.322-2.396C2.806 8.756 3.63 8.25 4.51 8.25H6.75z" />
            <path strokeLinecap="round" strokeLinejoin="round" d="M19.114 5.636a9 9 0 010 12.728M16.463 8.288a5.25 5.25 0 010 7.424" />
            <line x1="2.5" y1="21.5" x2="21.5" y2="2.5" strokeLinecap="round" strokeWidth={1.4} />
          </svg>
          <p className="text-[14px] leading-[20px] [text-shadow:0_0_3px_rgba(0,0,0,1)]">El vídeo se está reproduciendo</p>
          <p className="text-[14px] leading-[20px] mb-3 [text-shadow:0_0_3px_rgba(0,0,0,1)]">Click para activar el audio</p>
          <button
            onClick={onUnmute}
            className="bg-[#5996e1] text-white font-medium uppercase rounded-[5px] px-[0.8rem] py-[0.5rem] sm:px-[1.2rem] sm:py-[0.8rem] sm:text-[20px] cursor-pointer border-0"
          >
            Ver vídeo
          </button>
        </div>
      </div>
    )
  }

  return (
    <div
      className="absolute inset-0 z-10 flex items-center justify-center bg-black/70 cursor-pointer"
      onClick={onUnmute}
    >
      <div className="text-center text-white px-4 md:px-6">
        <svg
          xmlns="http://www.w3.org/2000/svg"
          className="w-14 h-14 md:w-28 md:h-28 mx-auto mb-1 md:mb-2 text-white"
          fill="none"
          viewBox="0 0 24 24"
          stroke="currentColor"
          strokeWidth={1.2}
        >
          <path strokeLinecap="round" strokeLinejoin="round" d="M6.75 8.25l4.72-4.72a.75.75 0 011.28.53v15.88a.75.75 0 01-1.28.53l-4.72-4.72H4.51c-.88 0-1.704-.507-1.938-1.354A9.009 9.009 0 012.25 12c0-.83.112-1.633.322-2.396C2.806 8.756 3.63 8.25 4.51 8.25H6.75z" />
          <path strokeLinecap="round" strokeLinejoin="round" d="M19.114 5.636a9 9 0 010 12.728M16.463 8.288a5.25 5.25 0 010 7.424" />
          <line x1="2.5" y1="21.5" x2="21.5" y2="2.5" strokeLinecap="round" strokeWidth={1.4} />
        </svg>
        <p className="text-sm md:text-xl leading-snug md:leading-relaxed">El vídeo se está reproduciendo</p>
        <p className="text-sm md:text-xl leading-snug md:leading-relaxed mb-3 md:mb-5">Click para activar el audio</p>
        <div className="flex justify-center">
          <CtaButton theme={theme} text="Ver vídeo" size="sm" />
        </div>
      </div>
    </div>
  )
}
