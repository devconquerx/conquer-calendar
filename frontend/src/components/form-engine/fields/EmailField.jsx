import { useRef, useEffect } from 'react'
import { LAB_INPUT, useIsLab } from '../../lab/labFields'

export default function EmailField({ field, value, onChange, onKeyDown }) {
  const inputRef = useRef(null)
  const isLab = useIsLab()

  useEffect(() => {
    inputRef.current?.focus({ preventScroll: true })
  }, [field.id])

  return (
    <div className={isLab ? "" : "-mt-3"}>
    <input
      ref={inputRef}
      type="email"
      value={value}
      onChange={(e) => onChange(e.target.value)}
      onKeyDown={onKeyDown}
      placeholder={field.placeholder || 'nombre@ejemplo.com'}
      className={isLab ? LAB_INPUT : "w-full bg-transparent border-b-2 border-black focus:border-black text-black text-lg md:text-3xl py-4 px-1 outline-none transition-colors placeholder:text-[#aaa]"}
      autoComplete="email"
    />
    </div>
  )
}
