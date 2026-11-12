import { useRef, useEffect } from 'react'
import { LAB_INPUT, useIsLab } from '../../lab/labFields'

export default function LongTextField({ field, value, onChange, onKeyDown }) {
  const textareaRef = useRef(null)
  const isLab = useIsLab()

  useEffect(() => {
    textareaRef.current?.focus({ preventScroll: true })
  }, [field.id])

  return (
    <div>
      <textarea
        ref={textareaRef}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        onKeyDown={onKeyDown}
        placeholder={field.placeholder || 'Escribe aquí tu respuesta...'}
        rows={isLab ? 2 : 4}
        className={isLab
          ? `${LAB_INPUT} resize-none`
          : "w-full bg-transparent border-2 border-black focus:border-black text-black text-base md:text-2xl py-4 px-4 rounded-lg outline-none transition-colors placeholder:text-[#aaa] resize-none"}
      />
      {isLab && (
        <p className="hidden md:block mt-7 text-sm leading-[21px] text-[color:var(--lab-n500)]">
          Shift ⇧ + Enter ↵ para hacer un salto de línea
        </p>
      )}
    </div>
  )
}
