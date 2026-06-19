import { useState, useRef, useEffect, useMemo } from 'react'
import { isPossiblePhoneNumber, AsYouType, getExampleNumber, parsePhoneNumberFromString } from 'libphonenumber-js'
import examples from 'libphonenumber-js/mobile/examples'
import Spinner from '../shared/Spinner'
import useTracking from '../../hooks/useTracking'
import useGeoLocation from '../../hooks/useGeoLocation'
import { fireAllLead } from '../../lib/pixelEvents'
import { registerLead } from '../../api'
import { useRouter } from '../../lib/router'
import { autocorrectEmail } from '../../lib/emailCorrection'
import { getTheme } from '../../themes'
import countries from '../../data/countries'

const getFlagUrl = (iso2) => `https://flagcdn.com/w40/${iso2?.toLowerCase()}.png`

function parseAutofillPhone(rawValue, fallbackCountry) {
  const compactValue = String(rawValue || '').trim().replace(/\s/g, '')
  const digits = compactValue.replace(/\D/g, '')
  if (!digits) return null

  const attempts = []
  if (compactValue.startsWith('+')) attempts.push([compactValue, undefined])
  if (compactValue.startsWith('00') && digits.length > 2) attempts.push([`+${digits.slice(2)}`, undefined])
  if (fallbackCountry?.phoneCode && digits.startsWith(fallbackCountry.phoneCode) && digits.length > fallbackCountry.phoneCode.length + 4) {
    attempts.push([`+${digits}`, undefined])
  }
  if (fallbackCountry?.iso2) attempts.push([digits, fallbackCountry.iso2])

  for (const [value, countryIso2] of attempts) {
    try {
      const parsed = countryIso2
        ? parsePhoneNumberFromString(value, countryIso2)
        : parsePhoneNumberFromString(value)

      if (!parsed?.nationalNumber || !parsed.countryCallingCode) continue
      if (typeof parsed.isPossible === 'function' && !parsed.isPossible()) continue

      const parsedCountry = countries.find((country) => country.iso2 === parsed.country)
      return {
        phoneData: parsed.number,
        phoneDigits: parsed.nationalNumber,
        phonePrefix: `+${parsed.countryCallingCode}`,
        leadCountry: parsedCountry?.en || fallbackCountry?.en || '',
      }
    } catch {}
  }

  return null
}

export default function LandingForm({ program, region, formConfig, school, nextUrl = '', funnelSlug = '', videoEnabled = false }) {
  const router = useRouter()
  const [name, setName] = useState('')
  const [email, setEmail] = useState('')
  const [phone, setPhone] = useState('')
  const [selectedCountry, setSelectedCountry] = useState(null)
  const [dropdownOpen, setDropdownOpen] = useState(false)
  const [search, setSearch] = useState('')
  const [errors, setErrors] = useState({})
  const [submitting, setSubmitting] = useState(false)
  const [wantsWhatsapp, setWantsWhatsapp] = useState(false)
  const honeypotRef = useRef(null)
  const phoneHoneypotRef = useRef(null)
  const dropdownRef = useRef(null)
  const searchInputRef = useRef(null)
  const { eventId, journeyId, pixelCookies, buildFullPayload } = useTracking()
  const { countryCode: geoCountryCode, loading: geoLoading } = useGeoLocation()

  const theme = getTheme(school?.slug)
  const t = theme.landing.form
  const isPaper = !!theme.paperboard
  const accent = theme.accent || {}

  const landing = formConfig?.landing || formConfig?.welcome || {}
  const buttonText = landing.buttonText || 'Ver video gratis'

  // Check opcional "Envíame la repetición por WhatsApp". Al marcarlo se revela el
  // campo de teléfono para capturar el número de WhatsApp del lead. Activo en
  // Conquer Legal y en Conquer Blocks EU (igual que el funnel de referencia, donde
  // el check solo existe en EU). Forzable por config con landing.whatsappOptin.
  const isEuRegion = String(region || '').toLowerCase() === 'eu'
  const showWhatsappOptin = landing.whatsappOptin != null
    ? !!landing.whatsappOptin
    : (theme.id === 'conquerlegal' || (theme.id === 'conquerblocks' && isEuRegion))

  // Mostrar campo de teléfono visible: por config (showPhone) o al marcar el check
  // de WhatsApp. Si no es visible, el teléfono se captura por honeypot/autofill.
  const showPhone = !!landing.showPhone
  const phoneVisible = showPhone || (showWhatsappOptin && wantsWhatsapp)
  const enablePhoneHoneypot = !phoneVisible

  // País desde geo
  useEffect(() => {
    if (geoLoading || selectedCountry) return
    const code = geoCountryCode || 'ES'
    const found = countries.find((c) => c.iso2 === code)
    if (found) setSelectedCountry(found)
  }, [geoCountryCode, geoLoading, selectedCountry])

  useEffect(() => {
    if (!phoneVisible) return
    const handleClick = (e) => {
      if (dropdownRef.current && !dropdownRef.current.contains(e.target)) setDropdownOpen(false)
    }
    document.addEventListener('mousedown', handleClick)
    return () => document.removeEventListener('mousedown', handleClick)
  }, [phoneVisible])

  useEffect(() => {
    if (dropdownOpen) setTimeout(() => searchInputRef.current?.focus(), 50)
  }, [dropdownOpen])

  const phonePlaceholder = useMemo(() => {
    if (showWhatsappOptin) return 'Número de WhatsApp'
    if (!selectedCountry?.iso2) return 'Teléfono *'
    try {
      const ex = getExampleNumber(selectedCountry.iso2, examples)
      if (ex) return ex.format('NATIONAL')
    } catch {}
    return 'Teléfono *'
  }, [selectedCountry, showWhatsappOptin])

  const filteredCountries = useMemo(() => {
    if (!search) return countries
    const q = search.toLowerCase()
    return countries.filter((c) =>
      c.es.toLowerCase().includes(q) || c.phoneCode.includes(q) || c.iso2.toLowerCase().includes(q)
    )
  }, [search])

  const handlePhoneChange = (e) => {
    if (!selectedCountry?.iso2) {
      setPhone(e.target.value.replace(/\D/g, ''))
      return
    }
    const formatter = new AsYouType(selectedCountry.iso2)
    setPhone(formatter.input(e.target.value))
  }

  const handleCountrySelect = (c) => {
    setSelectedCountry(c)
    setDropdownOpen(false)
    setSearch('')
    if (phone) {
      const digits = phone.replace(/\D/g, '')
      const formatter = new AsYouType(c.iso2)
      setPhone(formatter.input(digits))
    }
  }

  const validate = () => {
    const newErrors = {}
    if (!name.trim()) {
      newErrors.name = 'El nombre es obligatorio'
    } else if (isPaper && name.trim().length < 2) {
      newErrors.name = 'El nombre debe tener al menos 2 caracteres'
    }
    if (!email.trim()) {
      newErrors.email = 'El correo es obligatorio'
    } else if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) {
      newErrors.email = 'Correo electronico no valido'
    }
    if (phoneVisible) {
      const digits = phone.replace(/\D/g, '')
      if (wantsWhatsapp && !digits) {
        newErrors.phone = 'Ingresa tu número de WhatsApp'
      } else if (digits) {
        const fullNumber = `+${selectedCountry?.phoneCode || ''}${digits}`
        if (!isPossiblePhoneNumber(fullNumber)) {
          newErrors.phone = 'Teléfono no válido'
        }
      }
    }
    setErrors(newErrors)
    return Object.keys(newErrors).length === 0
  }

  const handleSubmit = async (e) => {
    e.preventDefault()
    if (!validate()) return

    setSubmitting(true)

    const trimmedName = name.trim()
    const rawEmail = email.trim().toLowerCase()
    const { corrected: trimmedEmail, original: originalEmail, wasCorrected } = autocorrectEmail(rawEmail)

    const fallbackCountry = selectedCountry || countries.find((c) => c.iso2 === (geoCountryCode || 'ES')) || null
    let phoneData = ''
    let phoneDigits = ''
    let phonePrefix = ''
    let phoneCountry = ''

    if (phoneVisible && phone.trim() && selectedCountry) {
      phoneDigits = phone.replace(/\D/g, '')
      phonePrefix = `+${selectedCountry.phoneCode}`
      phoneData = `${phonePrefix}${phoneDigits}`
      phoneCountry = selectedCountry.en
    } else if (enablePhoneHoneypot) {
      const autofillPhone = parseAutofillPhone(phoneHoneypotRef.current?.value, fallbackCountry)
      if (autofillPhone) {
        phoneData = autofillPhone.phoneData
        phoneDigits = autofillPhone.phoneDigits
        phonePrefix = autofillPhone.phonePrefix
        phoneCountry = autofillPhone.leadCountry
      }
    }

    const trackingPayload = buildFullPayload()

    const body = {
      ...trackingPayload,
      name: trimmedName,
      email: trimmedEmail,
      escuela: school?.slug || '',
      funnel: funnelSlug,
      last_name: honeypotRef.current?.value || '',
    }

    if (phoneData) {
      body.lead_phone = phoneDigits
      body.lead_phone_prefix = phonePrefix
      body.lead_country = phoneCountry
    }
    if (wasCorrected) body.original_email = originalEmail
    if (showWhatsappOptin) body.wants_whatsapp = wantsWhatsapp

    // Fire-and-forget: crea el Lead en backend (dispara tareas Celery del lado lead)
    registerLead(body)

    // Dispara el evento Lead en todas las plataformas
    fireAllLead({
      eventId, journeyId,
      email: trimmedEmail,
      phone: phoneData,
      name: trimmedName,
      schoolSlug: school?.slug,
      fbp: pixelCookies._fbp || '',
      fbc: pixelCookies._fbc || '',
    })

    await new Promise((resolve) => setTimeout(resolve, 300))

    // Prefill para la siguiente etapa (video → StepForm)
    const params = new URLSearchParams(window.location.search)
    params.set('name', trimmedName)
    params.set('fullname', trimmedName)
    params.set('email', trimmedEmail)
    if (wasCorrected) params.set('original_email', originalEmail)
    if (phoneData) params.set('phone', phoneData)
    params.set('event_id', eventId)
    params.set('journey_id', journeyId)

    // Siguiente etapa: video si la marca lo tiene configurado, si no el
    // StepForm. Dentro de la SPA navegamos con pushState (sin recarga);
    // fuera de ella (fallback) con recarga completa usando data-next-url.
    if (router) {
      router.navigate(videoEnabled ? 'video' : 'stepform', { search: `?${params.toString()}` })
      return
    }
    const dest = nextUrl || (program && region ? `/agenda/${program}/${region}/` : window.location.pathname)
    window.location.href = `${dest}?${params.toString()}`
  }

  const honeypotField = (
    <div style={{ position: 'absolute', left: '-9999px', top: '-9999px' }} aria-hidden="true">
      <input type="text" name="last_name" ref={honeypotRef} tabIndex={-1} autoComplete="off" placeholder="Apellido" />
    </div>
  )

  const phoneHoneypotField = enablePhoneHoneypot ? (
    <div style={{ position: 'absolute', left: '-10000px', top: 0, width: 1, height: 1, opacity: 0, overflow: 'hidden' }} aria-hidden="true">
      <input type="hidden" name="lead_phone_prefix" value={selectedCountry ? `+${selectedCountry.phoneCode}` : ''} readOnly />
      <input type="tel" name="lead_phone" ref={phoneHoneypotRef} autoComplete="tel" tabIndex={-1} />
      <input type="hidden" name="lead_country" value={selectedCountry?.en || ''} readOnly />
    </div>
  ) : null

  const phoneField = phoneVisible ? (
    <div>
      <div className={`flex ${isPaper ? '' : 'gap-1'}`}>
        <div className="relative" ref={dropdownRef}>
          <button
            type="button"
            onClick={() => setDropdownOpen(!dropdownOpen)}
            className={isPaper
              ? `flex items-center gap-1.5 px-2 py-2 rounded-l rounded-r-none border border-r-0 bg-white text-base text-black shadow-[inset_0px_2px_4px_rgba(0,0,0,0.15)] min-w-[90px] ${errors.phone ? 'border-red-500' : 'border-[#404040]'}`
              : `flex items-center gap-1.5 px-3 py-3.5 rounded-xl border text-sm min-w-[100px] ${errors.phone ? t.inputError : t.input}`
            }
          >
            {selectedCountry ? (
              <>
                <img src={getFlagUrl(selectedCountry.iso2)} alt="" width="20" height="14" className="rounded-sm object-cover" />
                <span>+{selectedCountry.phoneCode}</span>
                <svg className="w-3 h-3 opacity-40 ml-auto" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" /></svg>
              </>
            ) : (
              <span className="opacity-50">País</span>
            )}
          </button>

          {dropdownOpen && (
            <div className="absolute top-full left-0 mt-1 w-72 max-h-56 bg-white border border-gray-200 rounded-lg shadow-xl z-50 overflow-hidden">
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
              <div className="overflow-y-auto max-h-48">
                {filteredCountries.map((c, idx) => (
                  <button
                    key={`${c.iso2}-${idx}`}
                    type="button"
                    onClick={() => handleCountrySelect(c)}
                    className={`w-full text-left px-3 py-2 text-sm hover:bg-gray-100 flex items-center gap-2 ${selectedCountry?.iso2 === c.iso2 ? 'bg-gray-100 font-medium' : 'text-gray-600'}`}
                  >
                    <img src={getFlagUrl(c.iso2)} alt="" width="20" height="14" className="rounded-sm object-cover flex-shrink-0" />
                    <span className="flex-1 truncate">{c.es}</span>
                    <span className="text-gray-400 flex-shrink-0">+{c.phoneCode}</span>
                  </button>
                ))}
              </div>
            </div>
          )}
        </div>

        <input
          type="tel"
          placeholder={phonePlaceholder}
          value={phone}
          onChange={handlePhoneChange}
          style={isPaper ? { '--tw-ring-color': accent.ring } : undefined}
          className={isPaper
            ? `flex-1 px-3 py-2 rounded-r rounded-l-none border border-l-0 bg-cb-bg text-base text-[#404040] placeholder:text-[#404040]/60 placeholder:text-sm placeholder:font-light focus:outline-none shadow-[inset_0px_2px_4px_rgba(0,0,0,0.15)] ${errors.phone ? 'border-red-500' : 'border-[#404040]'}`
            : `flex-1 px-4 py-3.5 rounded-xl border focus:outline-none text-sm transition-colors ${errors.phone ? t.inputError : t.input}`
          }
        />
      </div>
      {errors.phone && <p className={`text-xs mt-1 ${isPaper ? 'text-red-500' : 'text-red-400'}`}>{errors.phone}</p>}
    </div>
  ) : null

  // Check opcional para recibir la repetición por WhatsApp (Conquer Legal).
  const whatsappOptinField = showWhatsappOptin ? (
    <label className="flex items-start gap-2 cursor-pointer select-none">
      <input
        type="checkbox"
        checked={wantsWhatsapp}
        onChange={(e) => {
          const checked = e.target.checked
          setWantsWhatsapp(checked)
          if (!checked) {
            setPhone('')
            setErrors((prev) => ({ ...prev, phone: undefined }))
          }
        }}
        className="mt-0.5 h-[18px] w-[18px] shrink-0 cursor-pointer"
        style={{ accentColor: accent.ring || '#1845D6' }}
      />
      <span className={`text-[15px] font-medium leading-snug ${isPaper ? 'text-black' : t.consent}`}>
        OPCIONAL: Envíame un acceso directo a la repetición por WhatsApp
      </span>
    </label>
  ) : null

  // ── CB layout ──
  if (isPaper) {
    return (
      <form onSubmit={handleSubmit}>
        {honeypotField}
        {phoneHoneypotField}

        <div className={`grid grid-cols-1 gap-4 ${phoneVisible ? 'md:grid-cols-3' : 'md:grid-cols-2'}`}>
          <div>
            <input
              type="text"
              placeholder="Nombre sin apellidos *"
              value={name}
              onChange={(e) => setName(e.target.value)}
              style={{ '--tw-ring-color': accent.ring }}
              className={`w-full px-3 py-2 rounded border bg-cb-bg text-base text-[#404040] placeholder:text-[#404040]/60 placeholder:text-sm placeholder:font-light focus:outline-none shadow-[inset_0px_2px_4px_rgba(0,0,0,0.15)] ${errors.name ? 'border-red-500' : 'border-[#404040]'}`}
            />
            {errors.name && <p className="text-red-500 text-xs mt-1">{errors.name}</p>}
          </div>

          <div>
            <input
              type="email"
              placeholder="Tu mejor email *"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              style={{ '--tw-ring-color': accent.ring }}
              className={`w-full px-3 py-2 rounded border bg-cb-bg text-base text-[#404040] placeholder:text-[#404040]/60 placeholder:text-sm placeholder:font-light focus:outline-none shadow-[inset_0px_2px_4px_rgba(0,0,0,0.15)] ${errors.email ? 'border-red-500' : 'border-[#404040]'}`}
            />
            {errors.email && <p className="text-red-500 text-xs mt-1">{errors.email}</p>}
          </div>

          {phoneField}
        </div>

        {whatsappOptinField && <div className="mt-3">{whatsappOptinField}</div>}

        <div className="mt-3 text-xs text-black leading-relaxed">
          <p className="mb-0">
            Al proporcionarnos tu correo electrónico, aceptas recibir comunicaciones comerciales por parte de nuestra empresa.
          </p>
          <p>
            Al continuar, confirmas que has leído y aceptas nuestra{' '}
            <a href={school?.privacyPolicyUrl || theme.footer?.legal?.privacy || '#'} target="_blank" rel="noopener noreferrer" style={{ backgroundImage: accent.linkGradient }} className="underline bg-clip-text text-transparent">
              política de privacidad.
            </a>
          </p>
        </div>

        <button
          type="submit"
          disabled={submitting}
          className="mt-4 w-full px-6 py-3 text-[#FAFAFA] uppercase flex items-center justify-center gap-2 hover:brightness-105 active:scale-[0.99] transition-all disabled:opacity-50"
          style={{ backgroundImage: accent.buttonGradient, fontWeight: accent.buttonWeight || '400', clipPath: 'polygon(97.74% 73.83%, 97.74% 82.56%, 100% 82.56%, 100% 100%, 95.47% 100%, 95.47% 91.28%, 81.5% 91.28%, 81.5% 100%, 19.87% 100%, 19.87% 91.28%, 9.06% 91.28%, 9.06% 100%, 2.26% 100%, 2.26% 80.24%, 0% 80.24%, 0% 26.16%, 2.26% 26.16%, 2.26% 17.44%, 0% 17.44%, 0% 0%, 4.53% 0%, 4.53% 8.72%, 12.82% 8.72%, 12.82% 0%, 72.03% 0%, 72.03% 8.72%, 88.67% 8.72%, 88.67% 0%, 97.74% 0%, 97.74% 8.72%, 100% 8.72%, 100% 73.83%)' }}
        >
          {submitting ? <Spinner /> : buttonText}
        </button>
      </form>
    )
  }

  // ── Default theme: vertical layout ──
  return (
    <form onSubmit={handleSubmit} className="space-y-3">
      {honeypotField}
      {phoneHoneypotField}

      <div>
        <input
          type="text"
          placeholder="Nombre sin apellidos *"
          value={name}
          onChange={(e) => setName(e.target.value)}
          className={`w-full px-4 py-3.5 rounded-xl border focus:outline-none text-sm transition-colors ${errors.name ? t.inputError : t.input}`}
        />
        {errors.name && <p className="text-red-400 text-xs mt-1">{errors.name}</p>}
      </div>

      <div>
        <input
          type="email"
          placeholder="Tu mejor email *"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          className={`w-full px-4 py-3.5 rounded-xl border focus:outline-none text-sm transition-colors ${errors.email ? t.inputError : t.input}`}
        />
        {errors.email && <p className="text-red-400 text-xs mt-1">{errors.email}</p>}
      </div>

      {phoneField}

      {whatsappOptinField}

      <button
        type="submit"
        disabled={submitting}
        className={`w-full py-4 px-6 text-white font-bold text-sm uppercase tracking-wider rounded-xl active:scale-[0.98] transition-all disabled:opacity-50 flex items-center justify-center gap-2 ${t.button}`}
      >
        {submitting ? <Spinner /> : buttonText}
      </button>

      <p className={`text-[10px] ${t.consent} leading-relaxed text-center pt-0.5`}>
        Al continuar, aceptas recibir comunicaciones comerciales.
        {school?.privacyPolicyUrl && (
          <>
            {' '}
            <a href={school.privacyPolicyUrl} target="_blank" rel="noopener noreferrer" className={`${t.consentLink} hover:underline`}>
              Politica de privacidad
            </a>.
          </>
        )}
      </p>

      <div className="flex items-center justify-center gap-4 pt-0.5">
        <div className={`flex items-center gap-1.5 ${t.trustText}`}>
          <svg className="w-3 h-3" fill="currentColor" viewBox="0 0 20 20">
            <path fillRule="evenodd" d="M5 9V7a5 5 0 0110 0v2a2 2 0 012 2v5a2 2 0 01-2 2H5a2 2 0 01-2-2v-5a2 2 0 012-2zm8-2v2H7V7a3 3 0 016 0z" clipRule="evenodd" />
          </svg>
          <span className="text-[10px]">Datos seguros</span>
        </div>
        <div className={`w-px h-3 ${t.trustDivider}`} />
        <div className={`flex items-center gap-1.5 ${t.trustText}`}>
          <svg className="w-3 h-3" fill="currentColor" viewBox="0 0 20 20">
            <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clipRule="evenodd" />
          </svg>
          <span className="text-[10px]">100% gratuito</span>
        </div>
      </div>
    </form>
  )
}
