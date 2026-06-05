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

  // Pair choices into rows of 2
  const rows = []
  for (let i = 0; i < choices.length; i += 2) {
    rows.push(choices.slice(i, i + 2))
  }

  return (
    <div className="flex flex-col gap-2">
      {rows.map((row, rowIdx) => (
        <div key={rowIdx} className="flex gap-2">
          {row.map((choice, colIdx) => {
            const idx = rowIdx * 2 + colIdx
            const isSelected = value === choice.value
            const letter = KEYS[idx]?.toUpperCase()
            const isLastOdd = row.length === 1

            return (
              <button
                key={choice.value}
                type="button"
                onClick={() => handleSelect(choice.value)}
                className={`group/choice relative flex items-center justify-between gap-4 text-left p-2 rounded-lg border transition-all duration-200 overflow-hidden ${
                  isLastOdd ? 'flex-1 max-w-[50%]' : 'flex-1'
                } ${
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
                {/* Hover overlay (CSS-only) + Selected overlay */}
                <div className={`absolute inset-0 pointer-events-none rounded-lg transition-colors ${
                  isSelected ? 'bg-black/[0.08]' : 'bg-transparent group-hover/choice:bg-black/[0.06]'
                }`} />

                <span className="relative text-[#444] text-base md:text-lg leading-[1.5]">
                  {choice.label}
                </span>

                {letter && (
                  <span className={`relative w-8 h-8 flex items-center justify-center rounded-full border text-base flex-shrink-0 transition-colors ${
                    isSelected
                      ? 'border-[#F97316] bg-[#F97316] text-white'
                      : 'border-black text-[#444]'
                  }`}>
                    {letter}
                  </span>
                )}
              </button>
            )
          })}
        </div>
      ))}
    </div>
  )
}
