import { useRef, useEffect } from 'react'

export default function LongTextField({ field, value, onChange, onKeyDown }) {
  const textareaRef = useRef(null)

  useEffect(() => {
    textareaRef.current?.focus()
  }, [field.id])

  return (
    <div>
      <textarea
        ref={textareaRef}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        onKeyDown={onKeyDown}
        placeholder={field.placeholder || 'Escribe aquí tu respuesta...'}
        rows={4}
        className="w-full bg-transparent border-2 border-black focus:border-black text-black text-xl md:text-2xl py-4 px-4 rounded-lg outline-none transition-colors placeholder:text-[#aaa] resize-none"
      />
      <p className="text-gray-400 text-xs mt-1">
        <strong>Shift + Enter</strong> para salto de línea
      </p>
    </div>
  )
}
