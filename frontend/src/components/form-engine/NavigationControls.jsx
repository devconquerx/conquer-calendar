export default function NavigationControls({ isFirst, isLast, isSubmitting, onOk, onBack, messages }) {
  const m = messages || {}
  return (
    <div className="flex items-center gap-4 mt-6">
      <button
        type="button"
        onClick={onOk}
        disabled={isSubmitting}
        className="group text-[var(--theme-accent-text,#fff)] px-5 py-2 rounded-lg font-semibold hover:brightness-110 transition-all text-base disabled:opacity-50 flex items-center gap-2"
        style={{ background: 'var(--theme-btn-gradient, var(--theme-accent, #111827))' }}
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
      {!isLast && (
        <span className="hidden md:inline text-gray-500 text-sm font-medium">
          {m['label.button.enterHint'] || 'presiona'} <strong className="font-bold">Enter ↵</strong>
        </span>
      )}
    </div>
  )
}
