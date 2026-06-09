export default function BottomNavBar({ progress, onUp, onDown, canGoUp, canGoDown }) {
  return (
    <div className="bottom-nav">
      <div className="bottom-progress">
        <span className="progress-label">{progress}% completado</span>
        <div className="progress-track">
          <div
            className="progress-fill"
            style={{
              width: `${progress}%`,
              background: 'linear-gradient(90deg, #ffbf00, #ff4000)',
            }}
          />
        </div>
      </div>

      <div className="nav-arrows">
        <button
          className="nav-arrow-btn"
          onClick={onUp}
          disabled={!canGoUp}
          style={{ opacity: canGoUp ? 1 : 0.3, cursor: canGoUp ? 'pointer' : 'default' }}
          aria-label="Pregunta anterior"
        >
          <svg viewBox="0 0 24 24" fill="none" stroke="#fff" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
            <polyline points="18 15 12 9 6 15" />
          </svg>
        </button>
        <button
          className="nav-arrow-btn"
          onClick={onDown}
          disabled={!canGoDown}
          style={{ opacity: canGoDown ? 1 : 0.3, cursor: canGoDown ? 'pointer' : 'default' }}
          aria-label="Pregunta siguiente"
        >
          <svg viewBox="0 0 24 24" fill="none" stroke="#fff" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
            <polyline points="6 9 12 15 18 9" />
          </svg>
        </button>
      </div>
    </div>
  )
}
