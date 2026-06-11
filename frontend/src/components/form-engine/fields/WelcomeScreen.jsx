export default function WelcomeScreen({ field, onNext }) {
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
      <button
        onClick={() => onNext(null)}
        style={{
          display: 'inline-block',
          background: 'var(--theme-btn-gradient, linear-gradient(90deg, #ffbf00, #ff4000))',
          borderRadius: 0,
          border: 0,
          boxShadow: 'none',
          fontFamily: '"Funnel Display", Arial, sans-serif',
          fontWeight: 300,
          color: '#fafafa',
          lineHeight: 1,
          textDecoration: 'none',
          cursor: 'pointer',
          paddingLeft: '4rem',
          paddingRight: '4rem',
          paddingTop: '0.9rem',
          paddingBottom: '0.9rem',
          fontSize: '1.25rem',
          transition: 'opacity 0.2s ease',
          clipPath: 'polygon(97.74% 73.83%, 97.74% 82.56%, 100% 82.56%, 100% 100%, 95.47% 100%, 95.47% 91.28%, 81.5% 91.28%, 81.5% 100%, 19.87% 100%, 19.87% 91.28%, 9.06% 91.28%, 9.06% 100%, 2.26% 100%, 2.26% 80.24%, 0% 80.24%, 0% 26.16%, 2.26% 26.16%, 2.26% 17.44%, 0% 17.44%, 0% 0%, 4.53% 0%, 4.53% 8.72%, 12.82% 8.72%, 12.82% 0%, 72.03% 0%, 72.03% 8.72%, 88.67% 8.72%, 88.67% 0%, 97.74% 0%, 97.74% 8.72%, 100% 8.72%, 100% 73.83%)',
        }}
        onMouseEnter={e => e.currentTarget.style.opacity = '0.9'}
        onMouseLeave={e => e.currentTarget.style.opacity = '1'}
      >
        {field.buttonText || 'Comenzar'}
      </button>
      <span className="hidden md:inline text-gray-400 text-xs mt-3">
        presiona <strong>Enter ↵</strong>
      </span>
    </div>
  )
}
