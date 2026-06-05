export default function ProgressBar({ progress }) {
  return (
    <div className="w-full bg-gray-200 h-2 rounded-full overflow-hidden">
      <div
        className="h-full transition-all duration-500 ease-out rounded-full"
        style={{
          width: `${progress}%`,
          background: 'var(--theme-btn-gradient, var(--theme-accent, #111827))',
        }}
      />
    </div>
  )
}
