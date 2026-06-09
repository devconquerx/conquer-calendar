import { useEffect, useCallback } from 'react'

import paperboardTexture from '../../../assets/img/cb/paperboard-texture.avif'

const KEYS = ['a', 'b', 'c', 'd', 'e', 'f', 'g']

const cbShadow = '0px 2px 5px rgba(0,0,0,0.1), 0px 9px 9px rgba(0,0,0,0.09), 0px 20px 12px rgba(0,0,0,0.05), 0px 36px 14px rgba(0,0,0,0.01)'

export default function MultipleChoice({ field, value, onChange, onNext }) {
  const choices = field.choices || []

  const handleSelect = useCallback((choiceValue) => {
    onChange(choiceValue)
    setTimeout(() => {
      onNext(choiceValue)
    }, 300)
  }, [onChange, onNext])

  // Keyboard shortcuts A-G
  useEffect(() => {
    const handleKeyDown = (e) => {
      if (e.key === 'Enter') return
      const keyIndex = KEYS.indexOf(e.key.toLowerCase())
      if (keyIndex >= 0 && keyIndex < choices.length) {
        e.preventDefault()
        handleSelect(choices[keyIndex].value)
      }
    }
    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [choices, handleSelect])

  return (
    <div className="flex flex-col gap-2 w-full">
      {choices.map((choice) => {
        const isSelected = value === choice.value
        return (
          <button
            key={choice.value}
            type="button"
            onClick={() => handleSelect(choice.value)}
            className={`group/choice relative flex items-center text-left px-2 py-2.5 rounded-lg border transition-all duration-200 overflow-hidden w-full ${
              isSelected
                ? 'border-[#F97316] ring-2 ring-[#F97316]/30'
                : 'border-[#BBB49B] hover:border-[#F97316]/50'
            }`}
            style={{
              backgroundImage: `linear-gradient(rgba(255,255,255,0.5), rgba(255,255,255,0.5)), url(${paperboardTexture})`,
              backgroundSize: 'cover',
              backgroundPosition: 'center',
              boxShadow: cbShadow,
            }}
          >
            <div className={`absolute inset-0 pointer-events-none rounded-lg transition-colors ${
              isSelected ? 'bg-black/[0.08]' : 'bg-transparent group-hover/choice:bg-black/[0.06]'
            }`} />
            <span className="relative text-[#444] text-lg md:text-xl leading-[1.5]">
              {choice.label}
            </span>
          </button>
        )
      })}
    </div>
  )
}
