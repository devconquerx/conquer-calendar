import { useRef, useEffect } from 'react'

export default function TextField({ field, value, onChange, onKeyDown }) {
  const inputRef = useRef(null)

  useEffect(() => {
    inputRef.current?.focus({ preventScroll: true })
  }, [field.id])

  return (
    <input
      ref={inputRef}
      type="text"
      value={value}
      onChange={(e) => onChange(e.target.value)}
      onKeyDown={onKeyDown}
      placeholder={field.placeholder || 'Escribe aquí tu respuesta...'}
      className="w-full bg-transparent border-b-2 border-black focus:border-black text-black text-lg md:text-3xl py-4 px-1 outline-none transition-colors placeholder:text-[#aaa]"
    />
  )
}
