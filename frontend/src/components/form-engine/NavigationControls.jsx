export default function NavigationControls({ isFirst, isLast, isSubmitting, onOk, onBack, messages, hideEnterHint }) {
  const m = messages || {}
  return (
    <div className="flex items-center gap-4 mt-6">
      <button
        type="button"
        onClick={onOk}
        disabled={isSubmitting}
        style={{
          display: 'inline-flex',
          alignItems: 'center',
          gap: '0.5rem',
          background: isSubmitting ? '#e5e5e5' : 'var(--theme-btn-gradient, linear-gradient(90deg, #ffbf00, #ff4000))',
          borderRadius: 0,
          border: 0,
          boxShadow: 'none',
          fontFamily: '"Funnel Display", Arial, sans-serif',
          fontWeight: 300,
          color: isSubmitting ? '#8d8d8d' : '#fafafa',
          lineHeight: 1,
          cursor: isSubmitting ? 'not-allowed' : 'pointer',
          paddingLeft: '1.75rem',
          paddingRight: '1.75rem',
          paddingTop: '0.75rem',
          paddingBottom: '0.75rem',
          fontSize: '1.25rem',
          transition: 'opacity 0.2s ease',
          opacity: isSubmitting ? 0.6 : 1,
          clipPath: 'polygon(97.74% 73.83%, 97.74% 82.56%, 100% 82.56%, 100% 100%, 95.47% 100%, 95.47% 91.28%, 81.5% 91.28%, 81.5% 100%, 19.87% 100%, 19.87% 91.28%, 9.06% 91.28%, 9.06% 100%, 2.26% 100%, 2.26% 80.24%, 0% 80.24%, 0% 26.16%, 2.26% 26.16%, 2.26% 17.44%, 0% 17.44%, 0% 0%, 4.53% 0%, 4.53% 8.72%, 12.82% 8.72%, 12.82% 0%, 72.03% 0%, 72.03% 8.72%, 88.67% 8.72%, 88.67% 0%, 97.74% 0%, 97.74% 8.72%, 100% 8.72%, 100% 73.83%)',
        }}
        className="group"
        onMouseEnter={e => { if (!isSubmitting) e.currentTarget.style.opacity = '0.9' }}
        onMouseLeave={e => { if (!isSubmitting) e.currentTarget.style.opacity = '1' }}
      >
        {isSubmitting ? (
          <>
            <svg className="animate-spin h-4 w-4" viewBox="0 0 24 24">
              <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" />
              <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
            </svg>
            {m['label.button.submitting'] || 'Enviando...'}
          </>
        ) : isLast ? (
          m['label.button.submit'] || 'Enviar'
        ) : (
          <>
            {m['label.button.next'] || 'Siguiente'}
            <svg
              className="w-4 h-4 transition-transform duration-200 group-hover:translate-x-1"
              fill="none" stroke="currentColor" viewBox="0 0 24 24"
            >
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={3} d="M9 5l7 7-7 7" />
            </svg>
          </>
        )}
      </button>
      {!isLast && !hideEnterHint && (
        <span className="hidden md:inline text-gray-500 text-sm font-medium">
          {m['label.button.enterHint'] || 'presiona'} <strong className="font-bold">Enter ↵</strong>
        </span>
      )}
    </div>
  )
}
