export default function ReturningOverlay({ onContinue, onRestart }) {
  return (
    <div className="absolute inset-0 z-10 flex items-center justify-center bg-black/80">
      <div className="text-center text-white p-8 max-w-md">
        <p className="text-xl font-semibold mb-6">
          Ya habias comenzado a ver este video
        </p>
        <div className="flex flex-col gap-3">
          <button
            onClick={onContinue}
            className="bg-white text-black px-6 py-3 rounded-lg font-semibold hover:bg-gray-200 transition-colors"
          >
            Continuar donde lo dejaste
          </button>
          <button
            onClick={onRestart}
            className="border border-white/50 text-white px-6 py-3 rounded-lg font-semibold hover:bg-white/10 transition-colors"
          >
            Empezar desde el principio
          </button>
        </div>
      </div>
    </div>
  )
}
