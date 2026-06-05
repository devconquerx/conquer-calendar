import React, { useState, useRef, useEffect, forwardRef, useImperativeHandle } from 'react'
import { isValidPhoneNumber } from 'libphonenumber-js'
import PhoneField from './PhoneField'

const LETTERS = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ'

const FormStep = forwardRef(function FormStep(
  { block, value, onChange, onNext, messages },
  ref
) {
  const [fieldError, setFieldError] = useState('')
  const inputRef = useRef(null)

  useEffect(() => {
    setFieldError('')
    const { name } = block
    if (name !== 'phone-number' && name !== 'multiple-choice' && name !== 'welcome-screen') {
      inputRef.current?.focus()
    }
  }, [block.id])

  const validate = () => {
    if (block.name === 'welcome-screen') return true
    const req = block.attributes?.required

    if (block.name === 'phone-number') {
      if (!value?.trim()) {
        setFieldError('El teléfono es obligatorio')
        return false
      }
      try {
        if (!isValidPhoneNumber(value)) {
          setFieldError('Número inválido. Incluye el código de país (ej: +34 612345678)')
          return false
        }
      } catch {
        setFieldError('Número inválido. Incluye el código de país (ej: +34 612345678)')
        return false
      }
      return true
    }

    if (req && !value?.trim()) {
      setFieldError(messages?.['label.errorAlert.required'] || '¡Este campo es obligatorio!')
      return false
    }

    if (block.name === 'email' && value) {
      if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(value)) {
        setFieldError(messages?.['label.errorAlert.email'] || '¡Correo electrónico no válido!')
        return false
      }
    }

    return true
  }

  // Exposed to Funnel via ref — called when the bottom ↓ button is pressed
  useImperativeHandle(ref, () => ({
    validateAndGetValue() {
      if (!validate()) return null
      return value ?? ''
    },
  }), [value, block.id])

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && block.name !== 'long-text') {
      e.preventDefault()
      const result = validate()
      if (result) onNext(value)
    }
  }

  const handleChoiceSelect = (choiceValue) => {
    onChange(choiceValue)
    setTimeout(() => onNext(choiceValue), 150)
  }

  return (
    <div className="block-card">
      <div className="block-label">{block.attributes.label}</div>

      {block.attributes.description && (
        <div className="block-description">{block.attributes.description}</div>
      )}

      {block.name === 'short-text' && (
        <input
          ref={inputRef}
          type="text"
          className="field-input"
          value={value || ''}
          onChange={e => { onChange(e.target.value); setFieldError('') }}
          onKeyDown={handleKeyDown}
          placeholder={block.attributes.placeholder || ''}
        />
      )}

      {block.name === 'email' && (
        <input
          ref={inputRef}
          type="email"
          className="field-input"
          value={value || ''}
          onChange={e => { onChange(e.target.value); setFieldError('') }}
          onKeyDown={handleKeyDown}
          placeholder={block.attributes.placeholder || ''}
        />
      )}

      {block.name === 'phone-number' && (
        <PhoneField
          value={value || ''}
          onChange={v => { onChange(v); setFieldError('') }}
          error={fieldError}
          onKeyDown={handleKeyDown}
        />
      )}

      {block.name === 'multiple-choice' && (
        <ul className="choices-list">
          {block.attributes.choices.map((choice, i) => (
            <li
              key={choice.value}
              className={`choice-item${value === choice.value ? ' selected' : ''}`}
              onClick={() => handleChoiceSelect(choice.value)}
            >
              <span className="choice-letter">{LETTERS[i]}</span>
              {choice.label}
            </li>
          ))}
        </ul>
      )}

      {block.name === 'long-text' && (
        <textarea
          ref={inputRef}
          className="long-text-input"
          value={value || ''}
          onChange={e => { onChange(e.target.value); setFieldError('') }}
          placeholder={block.attributes.placeholder || ''}
          rows={4}
        />
      )}

      {fieldError && block.name !== 'phone-number' && (
        <div className="field-error">{fieldError}</div>
      )}

      {/* Welcome screen keeps its inline CTA — bottom nav is not shown for it */}
      {block.name === 'welcome-screen' && (
        <div className="welcome-nav">
          <button className="btn-comenzar" type="button" onClick={() => onNext(null)}>
            {block.attributes.buttonText || 'Comenzar'}
          </button>
        </div>
      )}
    </div>
  )
})

export default FormStep
