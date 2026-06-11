// Borde pixelado del CTA de producción (clip-path copiado del botón real).
const CB_PIXEL_CLIP =
  'polygon(97.74% 73.83%, 97.74% 82.56%, 100% 82.56%, 100% 100%, 95.47% 100%, 95.47% 91.28%, 81.5% 91.28%, 81.5% 100%, 19.87% 100%, 19.87% 91.28%, 9.06% 91.28%, 9.06% 100%, 2.26% 100%, 2.26% 80.24%, 0% 80.24%, 0% 26.16%, 2.26% 26.16%, 2.26% 17.44%, 0% 17.44%, 0% 0%, 4.53% 0%, 4.53% 8.72%, 12.82% 8.72%, 12.82% 0%, 72.03% 0%, 72.03% 8.72%, 88.67% 8.72%, 88.67% 0%, 97.74% 0%, 97.74% 8.72%, 100% 8.72%, 100% 73.83%)'

export default function AgendarButton({ theme, onClick, text = 'Agendar Sesión de Consultoría Gratuita' }) {
  const isPaper = !!theme?.paperboard
  const accent = theme?.accent || {}

  return (
    <div className="flex justify-center mt-8 animate-fade-in">
      {isPaper ? (
        <button
          onClick={onClick}
          className="text-white text-base md:text-lg uppercase text-center px-6 md:px-10 py-5 hover:brightness-110 active:scale-[0.98] transition-all"
          style={{
            fontFamily: 'Montserrat, sans-serif',
            backgroundImage: accent.buttonGradient || 'linear-gradient(90deg, #FFBF00, #FF4000)',
            fontWeight: accent.buttonWeight || '800',
            clipPath: CB_PIXEL_CLIP,
          }}
        >
          {text}
        </button>
      ) : (
        <button
          onClick={onClick}
          className={`py-4 px-8 text-white font-bold text-lg rounded-xl active:scale-[0.98] transition-all flex items-center justify-center gap-2 ${theme?.landing?.form?.button || 'bg-orange-500 hover:bg-orange-600'}`}
        >
          {text}
        </button>
      )}
    </div>
  )
}
