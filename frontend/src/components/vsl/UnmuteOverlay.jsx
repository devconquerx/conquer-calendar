/* Overlay de activación de audio — réplica de producción: icono de altavoz
   tachado, dos líneas de texto y botón azul "VER VÍDEO". */
export default function UnmuteOverlay({ onUnmute }) {
  return (
    <div
      className="absolute inset-0 z-10 flex items-center justify-center bg-black/70 cursor-pointer"
      onClick={onUnmute}
    >
      <div className="text-center text-white px-6">
        <svg
          xmlns="http://www.w3.org/2000/svg"
          className="w-28 h-28 mx-auto mb-2 text-white"
          fill="none"
          viewBox="0 0 24 24"
          stroke="currentColor"
          strokeWidth={1.2}
        >
          <path strokeLinecap="round" strokeLinejoin="round" d="M6.75 8.25l4.72-4.72a.75.75 0 011.28.53v15.88a.75.75 0 01-1.28.53l-4.72-4.72H4.51c-.88 0-1.704-.507-1.938-1.354A9.009 9.009 0 012.25 12c0-.83.112-1.633.322-2.396C2.806 8.756 3.63 8.25 4.51 8.25H6.75z" />
          <path strokeLinecap="round" strokeLinejoin="round" d="M19.114 5.636a9 9 0 010 12.728M16.463 8.288a5.25 5.25 0 010 7.424" />
          <line x1="2.5" y1="21.5" x2="21.5" y2="2.5" strokeLinecap="round" strokeWidth={1.4} />
        </svg>
        <p className="text-xl leading-relaxed">El vídeo se está reproduciendo</p>
        <p className="text-xl leading-relaxed mb-5">Click para activar el audio</p>
        <button className="bg-[#3974FF] text-white text-xl font-medium uppercase px-8 py-3.5 rounded-md hover:brightness-110 transition-all">
          Ver vídeo
        </button>
      </div>
    </div>
  )
}
