/* Overlay de "ya habías comenzado a ver este video" — réplica del modal de
   producción (videolitics): fondo negro 80%, título grande y dos botones
   circulares con aro azul (#3974FF) y etiqueta al lado. */

function CircleButton({ onClick, label, icon }) {
  return (
    <button onClick={onClick} className="flex items-center gap-5 group text-left">
      <svg
        width="80"
        height="80"
        viewBox="0 0 64 64"
        className="shrink-0 transition-transform group-hover:scale-105"
      >
        <circle cx="32" cy="32" r="29.18" fill="#000" stroke="#3974FF" strokeWidth="3.07" />
        {icon}
      </svg>
      <span className="text-white text-[17px] font-normal">{label}</span>
    </button>
  )
}

const playIcon = <path d="M26 20.5v23l19-11.5z" fill="#fff" />
const restartIcon = (
  <g transform="rotate(-30 32 32)">
    <path
      d="M32 17a15 15 0 1 1-12.99 7.5"
      fill="none"
      stroke="#fff"
      strokeWidth="4"
      strokeLinecap="round"
    />
    <path d="M19 16l1.2 9.6 8-5.4z" fill="#fff" />
  </g>
)

export default function ReturningOverlay({ onContinue, onRestart }) {
  return (
    <div className="absolute inset-0 z-10 grid place-items-center bg-black/80 px-4">
      <div className="text-center text-white max-w-[760px] w-full">
        <h2 className="font-funnel text-2xl md:text-4xl font-semibold mb-8">
          Ya habías comenzado a ver este video
        </h2>
        <div className="flex flex-col md:flex-row gap-5 justify-center md:justify-between items-center md:items-stretch md:px-7">
          <CircleButton onClick={onContinue} label="¿Continuar donde lo dejaste?" icon={playIcon} />
          <CircleButton onClick={onRestart} label="¿Empezar desde el principio?" icon={restartIcon} />
        </div>
      </div>
    </div>
  )
}
