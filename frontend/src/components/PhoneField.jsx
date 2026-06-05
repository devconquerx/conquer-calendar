import React, { useRef, useEffect } from 'react'

export default function PhoneField({ value, onChange, error, onKeyDown }) {
  const ref = useRef(null)

  useEffect(() => { ref.current?.focus() }, [])

  return (
    <div>
      <input
        ref={ref}
        type="tel"
        className="field-input"
        value={value}
        onChange={e => onChange(e.target.value)}
        onKeyDown={onKeyDown}
        placeholder="+34 612 345 678"
        autoComplete="tel"
      />
      {error && <div className="field-error">{error}</div>}
    </div>
  )
}
