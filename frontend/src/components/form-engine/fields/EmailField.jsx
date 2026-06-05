import { useRef, useEffect } from 'react'

export default function EmailField({ field, value, onChange, onKeyDown }) {
  const inputRef = useRef(null)

  useEffect(() => {
    inputRef.current?.focus()
  }, [field.id])

  return (
    <input
      ref={inputRef}
      type="email"
      value={value}
      onChange={(e) => onChange(e.target.value)}
      onKeyDown={onKeyDown}
      placeholder={field.placeholder || 'nombre@ejemplo.com'}
      className="w-full bg-transparent border-b-2 border-black focus:border-black text-black text-2xl md:text-3xl py-4 px-1 outline-none transition-colors placeholder:text-[#aaa]"
      autoComplete="email"
    />
  )
}
