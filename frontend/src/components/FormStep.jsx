import React, { useState, useEffect } from 'react'
import { isValidPhoneNumber } from 'libphonenumber-js'
import TextField from './form-engine/fields/TextField'
import EmailField from './form-engine/fields/EmailField'
import LongTextField from './form-engine/fields/LongTextField'
import MultipleChoice from './form-engine/fields/MultipleChoice'
import PhoneField from './form-engine/fields/PhoneField'
import NavigationControls from './form-engine/NavigationControls'

const FIELD_COMPONENTS = {
  'short-text': TextField,
  'email': EmailField,
  'long-text': LongTextField,
  'multiple-choice': MultipleChoice,
  'phone-number': PhoneField,
}

export default function FormStep({
  block,
  value,
  onChange,
  onNext,
  onBack,
  messages,
  stepNumber,
  isFirst,
  isLast,
}) {
  const [fieldError, setFieldError] = useState('')

  useEffect(() => {
    setFieldError('')
  }, [block.id])

  // Cuando el teclado virtual aparece en móvil, hace scroll para que el input
  // y el botón "Siguiente" no queden tapados.
  useEffect(() => {
    const vv = window.visualViewport
    if (!vv) return
    const onResize = () => {
      const el = document.activeElement
      if (el && el.tagName !== 'BODY') {
        setTimeout(() => el.scrollIntoView({ behavior: 'smooth', block: 'center' }), 50)
      }
    }
    vv.addEventListener('resize', onResize)
    return () => vv.removeEventListener('resize', onResize)
  }, [])

  // Normalize the block into the shape the field components expect
  const field = {
    id: block.id,
    type: block.name,
    label: block.attributes?.label,
    description: block.attributes?.description,
    required: block.attributes?.required,
    placeholder: block.attributes?.placeholder,
    choices: block.attributes?.choices,
    buttonText: block.attributes?.buttonText,
  }

  const validate = () => {
    const req = field.required

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

  // Validate then advance (OK button / Enter / phone Enter)
  const handleOk = () => {
    if (validate()) onNext(value)
  }

  // Enter advances; Shift+Enter is a newline inside long-text
  const handleKeyDown = (e) => {
    if (e.key !== 'Enter' || e.shiftKey) return
    e.preventDefault()
    handleOk()
  }

  const handleFieldChange = (val) => {
    onChange(val)
    setFieldError('')
  }

  const FieldComponent = FIELD_COMPONENTS[block.name]

  return (
    <div className="max-w-3xl mx-auto flex flex-col justify-center min-h-[50vh]">
      <div className="mb-5 md:mb-10">
        <h2 className="text-black text-2xl md:text-[27px] font-semibold leading-[1.3]">
          {stepNumber}
          <svg className="inline-block mx-2 align-middle" width="14" height="12" viewBox="0 0 18 14" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
            <line x1="0" y1="7" x2="14" y2="7" />
            <polyline points="8,1 14,7 8,13" />
          </svg>
          {field.label}{field.required && <span className="text-red-500">*</span>}
        </h2>
        {field.description && (
          <p className="text-gray-500 text-base mt-3">{field.description}</p>
        )}
      </div>

      {FieldComponent ? (
        <FieldComponent
          field={field}
          value={value || ''}
          error={fieldError}
          onChange={handleFieldChange}
          onKeyDown={handleKeyDown}
          onNext={block.name === 'multiple-choice' ? onNext : handleOk}
        />
      ) : (
        <p className="text-gray-900">Tipo de campo desconocido: {block.name}</p>
      )}

      {fieldError && (
        <p className="text-red-500 text-sm mt-3">{fieldError}</p>
      )}

      <NavigationControls
        isFirst={isFirst}
        isLast={isLast}
        isSubmitting={false}
        onOk={handleOk}
        onBack={onBack}
        messages={messages}
      />
    </div>
  )
}
