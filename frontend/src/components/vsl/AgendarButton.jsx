export default function AgendarButton({ theme, onClick, text = 'Agendar Sesion de Consultoria Gratuita' }) {
  const isCB = theme?.id === 'conquerblocks'

  return (
    <div className="flex justify-center mt-6 animate-fade-in">
      {isCB ? (
        <button
          onClick={onClick}
          className="relative px-10 py-4 text-white text-lg font-semibold whitespace-nowrap flex items-center justify-center gap-3 hover:brightness-110 active:scale-[0.98] transition-all overflow-visible"
        >
          <img
            src={theme.assets?.ctaButtonBg}
            alt=""
            className="absolute pointer-events-none"
            style={{
              top: '-8px',
              left: '-10px',
              width: 'calc(100% + 20px)',
              height: 'calc(100% + 16px)',
            }}
          />
          <span className="relative z-10">{text}</span>
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
