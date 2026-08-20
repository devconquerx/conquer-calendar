import { describe, expect, it, vi } from 'vitest'
import { fireEvent, screen, waitFor } from '@testing-library/react'
import LandingForm from '../../src/components/landing/LandingForm'
import { registerLead } from '../../src/api'
import { getTheme } from '../../src/themes'
import { renderConFunnel } from './helpers'

vi.mock('../../src/api', () => ({ registerLead: vi.fn() }))
vi.mock('../../src/lib/pixelEvents', () => ({ fireAllLead: vi.fn(), pushToDataLayer: vi.fn() }))

const CONFIG = { landing: { title: 't', bullets: ['a'], buttonText: 'Ver vídeo gratis' } }

function temaDePagina(escuela) {
  const base = getTheme(escuela)
  return !base.paperboard && base.landingVariant === 'paperboard'
    ? { ...base, ...base.landingPaper, paperboard: true, hexboard: false }
    : base
}

function montar(opts = {}) {
  const escuela = opts.escuela || 'conquer-blocks'
  return renderConFunnel(
    <LandingForm program="fullstack" region={opts.region || 'latam'} formConfig={CONFIG}
                 school={{ slug: escuela }} funnelSlug={opts.slug || 'blocks-latam'}
                 themeOverride={temaDePagina(escuela)} />,
    { escuela, ...opts }
  )
}

/* jsdom no dispara el submit de forma fiable al pulsar el botón, así que los
   tests envían el <form> directamente: es el mismo camino que recorre el
   navegador (onSubmit → validate → registerLead). */
const enviarForm = (container) => fireEvent.submit(container.querySelector('form'))

async function enviar(container, { nombre = 'Ana', email = 'ana@ejemplo.com' } = {}) {
  fireEvent.change(screen.getByPlaceholderText(/nombre/i), { target: { value: nombre } })
  fireEvent.change(screen.getByPlaceholderText(/email/i), { target: { value: email } })
  enviarForm(container)
  await waitFor(() => expect(registerLead).toHaveBeenCalled())
  return registerLead.mock.calls.at(-1)[0]
}

describe('formulario de la landing', () => {
  it('manda la variante del test de fondo como utm_form_variant', async () => {
    const { container } = montar({ slug: 'blocks-latam', storageKey: 'form_variant_cb_latam', variante: '58' })
    expect((await enviar(container)).utm_form_variant).toBe('58')
  })

  it('no manda utm_form_variant en un funnel sin experimento', async () => {
    // languages-ge no participa en ningún A/B (las tres regiones grandes sí).
    const { container } = montar({ slug: 'languages-ge', escuela: 'conquer-languages', region: 'ge' })
    expect('utm_form_variant' in (await enviar(container))).toBe(false)
  })

  it('manda el prefijo del pais detectado aunque el lead no deje telefono', async () => {
    // El CRM recibia este campo siempre relleno. El funnel viejo lo lograba
    // metiendo un '+34' fijo; aqui va el prefijo real del pais del visitante.
    const { container } = montar({ slug: 'blocks-latam' })
    const body = await enviar(container)
    expect('lead_phone' in body).toBe(false)
    expect(body.lead_phone_prefix).toMatch(/^\+\d+$/)
  })

  it('el honeypot de apellido pide el autofill del navegador (family-name)', async () => {
    // Con autocomplete="off" el navegador no lo rellenaba y last_name llegaba
    // siempre vacio al CRM.
    const { container } = montar({ slug: 'blocks-latam' })
    const hp = container.querySelector('input[name="last_name"]')
    expect(hp).toBeTruthy()
    expect(hp.getAttribute('autocomplete')).toBe('family-name')
  })

  it('NO manda la variante del vídeo en el lead: esa va en la prellamada', async () => {
    const { container } = montar({ slug: 'blocks-latam', storageKey: 'form_variant_video_cb_latam', variante: '4' })
    const body = await enviar(container)
    // Manda la del test de la landing (57/58), nunca el código del vídeo.
    expect(['57', '58']).toContain(body.utm_form_variant)
  })

  it('incluye escuela, funnel, consentimiento y el email normalizado', async () => {
    const { container } = montar({ slug: 'blocks-latam' })
    const body = await enviar(container, { email: '  ANA@Ejemplo.COM ' })
    expect(body).toMatchObject({ escuela: 'conquer-blocks', funnel: 'blocks-latam', email: 'ana@ejemplo.com' })
    expect(body.conditions).toMatch(/^Acepta las políticas: /)
  })

  it('exige nombre y correo antes de registrar nada', async () => {
    const { container } = montar({ slug: 'blocks-latam' })
    enviarForm(container)
    await waitFor(() => expect(screen.getAllByText(/obligatorio/i).length).toBeGreaterThan(0))
    expect(registerLead).not.toHaveBeenCalled()
  })

  it('avisa de un correo mal escrito', async () => {
    const { container } = montar({ slug: 'blocks-latam' })
    fireEvent.change(screen.getByPlaceholderText(/nombre/i), { target: { value: 'Ana' } })
    fireEvent.change(screen.getByPlaceholderText(/email/i), { target: { value: 'ana@' } })
    enviarForm(container)
    await waitFor(() => expect(screen.getByText(/no valido|no válido/i)).toBeInTheDocument())
    expect(registerLead).not.toHaveBeenCalled()
  })
})

/* Los A/B de teléfono/WhatsApp llevan meses vivos en EU: estos tests fijan su
   comportamiento para que un cambio en el registro de experimentos no los
   altere sin que nos enteremos. */
describe('A/B de teléfono/WhatsApp (EU)', () => {
  /* Se busca el checkbox real, no el texto: el aviso legal de Finance también
     menciona WhatsApp en las DOS variantes y haría ambigua la búsqueda. */
  const hayCheckbox = (container) => !!container.querySelector('input[type="checkbox"]')

  it('Blocks EU 51 (control): sin checkbox', () => {
    const { container } = montar({ slug: 'blocks-eu', region: 'eu', storageKey: 'form_variant_cb_eu', variante: '51' })
    expect(hayCheckbox(container)).toBe(false)
  })

  it('Blocks EU 52 (test): con checkbox de WhatsApp', () => {
    const { container } = montar({ slug: 'blocks-eu', region: 'eu', storageKey: 'form_variant_cb_eu', variante: '52' })
    expect(hayCheckbox(container)).toBe(true)
    expect(screen.getByText(/repetición por WhatsApp/i)).toBeInTheDocument()
  })

  it('Finance EU 55: checkbox; 56: teléfono siempre visible y obligatorio', async () => {
    const primera = montar({ slug: 'finance-eu', escuela: 'conquer-finance', region: 'eu', storageKey: 'form_variant_cf', variante: '55' })
    expect(hayCheckbox(primera.container)).toBe(true)
    primera.unmount()

    localStorage.setItem('form_variant_cf', '56')
    const { container } = montar({ slug: 'finance-eu', escuela: 'conquer-finance', region: 'eu' })
    expect(screen.getByPlaceholderText(/número de whatsapp \*/i)).toBeInTheDocument()
    fireEvent.change(screen.getByPlaceholderText(/nombre/i), { target: { value: 'Ana' } })
    fireEvent.change(screen.getByPlaceholderText(/email/i), { target: { value: 'ana@ejemplo.com' } })
    enviarForm(container)
    await waitFor(() => expect(screen.getByText(/ingresa tu número de whatsapp/i)).toBeInTheDocument())
    expect(registerLead).not.toHaveBeenCalled()
  })

  it('Blocks LATAM no hereda el checkbox de EU', () => {
    const { container } = montar({ slug: 'blocks-latam', storageKey: 'form_variant_cb_latam', variante: '58' })
    expect(hayCheckbox(container)).toBe(false)
  })
})
