import { useState, useRef, useEffect, useMemo } from 'react'
import { AsYouType, getExampleNumber, parsePhoneNumber } from 'libphonenumber-js'
import examples from 'libphonenumber-js/mobile/examples'
import countries from '../../../data/countries'
import useGeoLocation from '../../../hooks/useGeoLocation'
import paperboardTexture from '../../../assets/img/cb/paperboard-texture.avif'

const getFlagUrl = (iso2) => `https://flagcdn.com/w40/${iso2?.toLowerCase()}.png`

export default function PhoneField({ field, value, onChange, onNext }) {
  const { countryCode: geoCountryCode, loading: geoLoading } = useGeoLocation()
  const [selectedCountry, setSelectedCountry] = useState(null)
  const [phoneNumber, setPhoneNumber] = useState('')
  const [dropdownOpen, setDropdownOpen] = useState(false)
  const [search, setSearch] = useState('')
  const inputRef = useRef(null)
  const dropdownRef = useRef(null)
  const searchInputRef = useRef(null)

  // Set country from geo result, fallback to Spain once geo resolves
  useEffect(() => {
    if (geoLoading || selectedCountry) return
    const code = geoCountryCode || 'ES'
    const found = countries.find((c) => c.iso2 === code)
    if (found) setSelectedCountry(found)
  }, [geoCountryCode, geoLoading])

  // Parse existing value if coming from prefill (E.164 string). Separa el código
  // de país del número nacional para no duplicar el prefijo al reconstruirlo.
  useEffect(() => {
    if (!value || typeof value !== 'string') return
    const e164 = value.startsWith('+') ? value : `+${value.replace(/[^\d]/g, '')}`
    try {
      const parsed = parsePhoneNumber(e164)
      if (parsed) {
        const found = countries.find((c) => c.iso2 === parsed.country)
        if (found) {
          setSelectedCountry(found)
          setPhoneNumber(parsed.nationalNumber)
          return
        }
        // País detectado no está en nuestra lista: resuelve por prefijo abajo.
      }
    } catch (_) {}
    // Fallback: empareja por el phoneCode más largo que prefije los dígitos.
    const digits = value.replace(/[^\d]/g, '')
    const sorted = [...countries].sort(
      (a, b) => String(b.phoneCode).replace(/\D/g, '').length - String(a.phoneCode).replace(/\D/g, '').length
    )
    const match = sorted.find((c) => digits.startsWith(String(c.phoneCode).replace(/\D/g, '')))
    if (match) {
      setSelectedCountry(match)
      setPhoneNumber(digits.slice(String(match.phoneCode).replace(/\D/g, '').length))
    } else if (digits) {
      setPhoneNumber(digits)
    }
  }, [])

  // Focus input
  useEffect(() => {
    inputRef.current?.focus()
  }, [field.id])

  // Close dropdown on outside click
  useEffect(() => {
    const handleClick = (e) => {
      if (dropdownRef.current && !dropdownRef.current.contains(e.target)) {
        setDropdownOpen(false)
      }
    }
    document.addEventListener('mousedown', handleClick)
    return () => document.removeEventListener('mousedown', handleClick)
  }, [])

  // Focus search input when dropdown opens
  useEffect(() => {
    if (dropdownOpen) {
      setTimeout(() => searchInputRef.current?.focus(), 50)
    }
  }, [dropdownOpen])

  // Update parent with full E.164 phone string
  useEffect(() => {
    if (selectedCountry && phoneNumber) {
      const rawDigits = phoneNumber.replace(/\D/g, '')
      const fullNumber = `+${selectedCountry.phoneCode}${rawDigits}`
      onChange(fullNumber)
    }
  }, [selectedCountry, phoneNumber])

  // Example phone number as placeholder
  const placeholder = useMemo(() => {
    if (!selectedCountry?.iso2) return 'Número de teléfono'
    try {
      const example = getExampleNumber(selectedCountry.iso2, examples)
      if (example) return example.format('NATIONAL')
    } catch {}
    return 'Número de teléfono'
  }, [selectedCountry])

  const filteredCountries = useMemo(() => {
    if (!search) return countries
    const q = search.toLowerCase()
    return countries.filter((c) =>
      c.es.toLowerCase().includes(q) ||
      c.en.toLowerCase().includes(q) ||
      c.phoneCode.includes(q) ||
      c.iso2.toLowerCase().includes(q)
    )
  }, [search])

  const handlePhoneChange = (e) => {
    if (!selectedCountry?.iso2) {
      setPhoneNumber(e.target.value.replace(/\D/g, ''))
      return
    }
    // Use AsYouType to format as user types
    const formatter = new AsYouType(selectedCountry.iso2)
    const formatted = formatter.input(e.target.value)
    setPhoneNumber(formatted)
  }

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      e.stopPropagation()
      onNext()
    }
  }

  const handleCountrySelect = (c) => {
    setSelectedCountry(c)
    setDropdownOpen(false)
    setSearch('')
    // Reset phone when changing country to avoid formatting mismatches
    if (phoneNumber) {
      const digits = phoneNumber.replace(/\D/g, '')
      const formatter = new AsYouType(c.iso2)
      setPhoneNumber(formatter.input(digits))
    }
    inputRef.current?.focus()
  }

  return (
    <div>
      <div className="flex gap-2">
        {/* Country selector */}
        <div className="relative" ref={dropdownRef}>
          <button
            type="button"
            onClick={() => setDropdownOpen(!dropdownOpen)}
            className="relative flex items-center gap-2 border border-[#BBB49B] rounded-lg px-4 py-4 text-black text-xl hover:border-[#F97316]/50 transition-colors min-w-[130px] overflow-hidden"
            style={{
              backgroundImage: `linear-gradient(rgba(255,255,255,0.5), rgba(255,255,255,0.5)), url(${paperboardTexture})`,
              backgroundSize: 'cover',
              backgroundPosition: 'center',
              boxShadow: '0px 2px 5px rgba(0,0,0,0.1), 0px 9px 9px rgba(0,0,0,0.09), 0px 20px 12px rgba(0,0,0,0.05), 0px 36px 14px rgba(0,0,0,0.01)',
            }}
          >
            {selectedCountry ? (
              <>
                <img
                  src={getFlagUrl(selectedCountry.iso2)}
                  alt={selectedCountry.iso2}
                  width="24"
                  height="16"
                  className="rounded-sm object-cover"
                />
                <span className="text-lg">+{selectedCountry.phoneCode}</span>
                <svg className="w-4 h-4 text-[#444] ml-auto" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                </svg>
              </>
            ) : (
              <span className="text-gray-400 text-sm">País</span>
            )}
          </button>

          {dropdownOpen && (
            <div className="absolute top-full left-0 mt-1 w-80 max-h-64 bg-white border border-gray-200 rounded-lg shadow-xl z-50 overflow-hidden">
              <div className="p-2 border-b border-gray-200">
                <input
                  ref={searchInputRef}
                  type="text"
                  value={search}
                  onChange={(e) => setSearch(e.target.value)}
                  placeholder="Buscar país..."
                  className="w-full bg-gray-100 text-gray-900 text-sm px-3 py-2 rounded outline-none placeholder:text-gray-400"
                />
              </div>
              <div className="overflow-y-auto max-h-52">
                {filteredCountries.map((c, idx) => (
                  <button
                    key={`${c.iso2}-${idx}`}
                    type="button"
                    onClick={() => handleCountrySelect(c)}
                    className={`w-full text-left px-3 py-2 text-sm hover:bg-gray-100 transition-colors flex items-center gap-2 ${
                      selectedCountry?.iso2 === c.iso2 ? 'bg-gray-100 text-gray-900' : 'text-gray-600'
                    }`}
                  >
                    <img
                      src={getFlagUrl(c.iso2)}
                      alt={c.iso2}
                      width="24"
                      height="16"
                      className="rounded-sm object-cover flex-shrink-0"
                    />
                    <span className="flex-1 truncate">{c.es}</span>
                    <span className="text-gray-400 flex-shrink-0">+{c.phoneCode}</span>
                  </button>
                ))}
              </div>
            </div>
          )}
        </div>

        {/* Phone input */}
        <input
          ref={inputRef}
          type="tel"
          value={phoneNumber}
          onChange={handlePhoneChange}
          onKeyDown={handleKeyDown}
          placeholder={placeholder}
          className="flex-1 bg-transparent border-b-2 border-black focus:border-black text-black text-2xl md:text-3xl py-4 px-1 outline-none transition-colors placeholder:text-[#aaa]"
        />
      </div>
    </div>
  )
}
