import { useTheme } from '../../../themes'

export default function WelcomeScreen({ field, onNext }) {
  const theme = useTheme()
  const ctaButtonBg = theme.assets?.ctaButtonBg

  return (
    <div className="flex flex-col items-center justify-center min-h-[50vh] text-center">
      <h1 className="text-gray-900 text-2xl md:text-3xl font-bold mb-4 leading-tight">
        {field.label || 'Formulario'}
      </h1>
      {field.description && (
        <p className="text-gray-500 text-base md:text-lg max-w-lg mb-8 leading-relaxed">
          {field.description}
        </p>
      )}
      {ctaButtonBg ? (
        <button
          onClick={() => onNext(null)}
          className="relative px-10 py-3 text-white text-base font-semibold whitespace-nowrap flex items-center justify-center hover:brightness-110 active:scale-[0.98] transition-all overflow-visible"
        >
          <img
            src={ctaButtonBg}
            alt=""
            className="absolute pointer-events-none"
            style={{
              top: '-8px',
              left: '-10px',
              width: 'calc(100% + 20px)',
              height: 'calc(100% + 16px)',
            }}
          />
          <span className="relative z-10" style={{ marginLeft: '-17px' }}>
            {field.buttonText || 'Comenzar'}
          </span>
        </button>
      ) : (
        <button
          onClick={() => onNext(null)}
          className="text-[var(--theme-accent-text,#fff)] px-8 py-3 rounded-lg font-semibold hover:brightness-110 transition-all text-lg"
          style={{ background: 'var(--theme-btn-gradient, var(--theme-accent, #111827))' }}
        >
          {field.buttonText || 'Comenzar'}
        </button>
      )}
      <span className="text-gray-400 text-xs mt-3">
        presiona <strong>Enter ↵</strong>
      </span>
    </div>
  )
}
