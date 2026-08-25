import { useEffect, useCallback } from 'react'

import paperboardTextureAsset from '../../../assets/img/cb/paperboard-texture.avif'
import { useTheme } from '../../../themes'

const KEYS = ['a', 'b', 'c', 'd', 'e', 'f', 'g']

const cbShadow = '0px 2px 5px rgba(0,0,0,0.1), 0px 9px 9px rgba(0,0,0,0.09), 0px 20px 12px rgba(0,0,0,0.05), 0px 36px 14px rgba(0,0,0,0.01)'

export default function MultipleChoice({ field, value, onChange, onNext }) {
  const choices = field.choices || []
  const theme = useTheme()
  // La textura sale del tema para que la variante A/B de fondo blanco (que la
  // pone a null) también alcance a estas tarjetas; el asset importado es el
  // fallback de los temas que no declaran la suya.
  const paperboardTexture = 'paperboardTexture' in (theme.assets || {})
    ? theme.assets.paperboardTexture
    : paperboardTextureAsset
  const choiceBg = paperboardTexture
    ? {
        backgroundImage: `linear-gradient(rgba(255,255,255,0.5), rgba(255,255,255,0.5)), url(${paperboardTexture})`,
        backgroundSize: 'cover',
        backgroundPosition: 'center',
      }
    : { backgroundColor: '#FFFFFF' }

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

  // Hexboard (Finance): opciones grises de QuillForms en producción
  // (answersColor #000000bf): fondo negro al 10% (20% hover, 75% seleccionada
  // con texto blanco), borde 1px negro 75%, radio 5px y badge de letra con
  // borde negro al 40%. Mismo layout apilado.
  if (theme?.hexboard) {
    return (
      <div className="flex flex-col gap-2 w-full">
        {choices.map((choice, i) => {
          const isSelected = value === choice.value
          return (
            <button
              key={choice.value}
              type="button"
              onClick={() => handleSelect(choice.value)}
              className={`flex items-center justify-between gap-3 text-left px-[10px] py-[10px] rounded-[5px] border w-full transition-colors duration-150 border-black/75 ${
                isSelected ? 'bg-black/75 text-white' : 'bg-black/10 hover:bg-black/20 text-black/75'
              }`}
            >
              <span className="text-base md:text-xl leading-[1.4]">{choice.label}</span>
              <span
                className={`flex items-center justify-center w-8 h-8 rounded-full border text-sm font-bold uppercase flex-shrink-0 ${
                  isSelected ? 'border-white text-white' : 'border-black/40 bg-black/10 text-black/75'
                }`}
              >
                {KEYS[i] || ''}
              </span>
            </button>
          )
        })}
      </div>
    )
  }

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
                ? ''
                : 'border-[#BBB49B] hover:border-[color:var(--theme-accent,#F97316)]'
            }`}
            style={{
              ...choiceBg,
              // Acento de marca por CSS var (naranja Blocks / azul Legal). El aro
              // translúcido va por box-shadow para poder usar el color del tema.
              borderColor: isSelected ? 'var(--theme-accent, #F97316)' : undefined,
              boxShadow: isSelected
                ? `0 0 0 2px var(--theme-accent-ring, rgba(249,115,22,0.3)), ${cbShadow}`
                : cbShadow,
            }}
          >
            <div className={`absolute inset-0 pointer-events-none rounded-lg transition-colors ${
              isSelected ? 'bg-black/[0.08]' : 'bg-transparent group-hover/choice:bg-black/[0.06]'
            }`} />
            <span className="relative text-[#444] text-base md:text-xl leading-[1.5]">
              {choice.label}
            </span>
          </button>
        )
      })}
    </div>
  )
}
