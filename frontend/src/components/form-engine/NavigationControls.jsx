export default function NavigationControls({ isFirst, isLast, isSubmitting, onOk, onBack }) {
  return (
    <div className="flex items-center justify-between mt-6">
      <div>
        {!isFirst && (
          <button
            type="button"
            onClick={onBack}
            className="text-gray-400 hover:text-gray-900 transition-colors text-sm flex items-center gap-1"
          >
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
            </svg>
            Anterior
          </button>
        )}
      </div>
      <div>
        <button
          type="button"
          onClick={onOk}
          disabled={isSubmitting}
          className="text-[var(--theme-accent-text,#fff)] px-8 py-3 rounded-lg font-semibold hover:brightness-110 transition-all text-sm disabled:opacity-50 flex items-center gap-2"
          style={{ background: 'var(--theme-btn-gradient, var(--theme-accent, #111827))' }}
        >
          {isSubmitting ? (
            <>
              <svg className="animate-spin h-4 w-4" viewBox="0 0 24 24">
                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" />
                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
              </svg>
              Enviando...
            </>
          ) : isLast ? (
            'Enviar'
          ) : (
            <>
              OK
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
              </svg>
            </>
          )}
        </button>
        {!isLast && (
          <span className="text-gray-400 text-xs mt-1 block text-right">
            presiona <strong>Enter ↵</strong>
          </span>
        )}
      </div>
    </div>
  )
}
