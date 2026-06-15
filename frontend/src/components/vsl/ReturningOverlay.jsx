/* Overlay de "ya habías comenzado a ver este video" — réplica del modal de
   producción (videolitics): fondo negro 80%, título grande y dos botones
   circulares con aro azul (#3974FF) y etiqueta al lado. */

function CircleButton({ onClick, label, icon, colorStops, gradientId }) {
  const isGradient = colorStops.length > 1
  const stroke = isGradient ? `url(#${gradientId})` : colorStops[0]
  return (
    <button onClick={onClick} className="flex items-center gap-3 md:gap-5 group text-left">
      <svg
        viewBox="0 0 64 64"
        className="shrink-0 w-10 h-10 md:w-20 md:h-20 transition-transform group-hover:scale-105"
      >
        {isGradient && (
          <defs>
            <linearGradient id={gradientId} x1="0" y1="0" x2="1" y2="1">
              {colorStops.map((c, i) => (
                <stop key={i} offset={`${(i / (colorStops.length - 1)) * 100}%`} stopColor={c} />
              ))}
            </linearGradient>
          </defs>
        )}
        <circle cx="32" cy="32" r="29.18" fill="#000" stroke={stroke} strokeWidth="3.07" />
        {icon}
      </svg>
      <span className="text-white text-sm md:text-[17px] font-normal leading-tight">{label}</span>
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

export default function ReturningOverlay({ onContinue, onRestart, theme }) {
  // Color del aro de los botones: degradado del acento del tema (naranja en
  // Conquer Blocks, azul en Legal). Fallback al azul de producción si el tema
  // no define un degradado de botón.
  const colorStops = theme?.accent?.buttonGradient?.match(/#[0-9a-fA-F]{3,8}/g) || ['#3974FF']

  return (
    <div className="absolute inset-0 z-10 grid place-items-center bg-black/80 px-2 md:px-4">
      <div className="text-center text-white max-w-[760px] w-full">
        <h2 className="font-funnel text-sm md:text-4xl font-semibold leading-tight mb-3 md:mb-8">
          Ya habías comenzado a ver este video
        </h2>
        <div className="flex flex-col md:flex-row gap-3 md:gap-5 justify-center md:justify-between items-center md:items-stretch md:px-7">
          <CircleButton onClick={onContinue} label="¿Continuar donde lo dejaste?" icon={playIcon} colorStops={colorStops} gradientId="ro-grad-continue" />
          <CircleButton onClick={onRestart} label="¿Empezar desde el principio?" icon={restartIcon} colorStops={colorStops} gradientId="ro-grad-restart" />
        </div>
      </div>
    </div>
  )
}
