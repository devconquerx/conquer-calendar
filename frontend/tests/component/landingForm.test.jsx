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
  // `landing` permite simular las banderas que en producción vienen de la
  // config del funnel en BD (hoy: `whatsappOptin` en las dos landings de EU).
  const config = opts.landing
    ? { ...CONFIG, landing: { ...CONFIG.landing, ...opts.landing } }
    : CONFIG
  return renderConFunnel(
    <LandingForm program="fullstack" region={opts.region || 'latam'} formConfig={config}
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

  /* El honeypot es un input[type=tel] dentro de un contenedor aria-hidden
     colocado a -10000px, así que «pedir el teléfono» = tener un tel FUERA de
     esa caja. */
  const telefonoVisible = (container) => [...container.querySelectorAll('input[type="tel"]')]
    .some((i) => !i.closest('[aria-hidden="true"]'))

  /* Blocks EU ya NO prueba el checkbox: ganó la rama que lo lleva y quedó fija
     por config (`landing.whatsappOptin`, migración 0027), así que sale en las
     DOS ramas del test de fondo que corre ahora en su lugar. */
  for (const [rama, variante] of [['control', '69'], ['fondo blanco', '70']])
    it(`Blocks EU (${rama}): el checkbox sale igual, ya no depende de la variante`, () => {
      const { container } = montar({
        slug: 'blocks-eu', region: 'eu',
        storageKey: 'form_variant_cb_eu_fondo', variante,
        landing: { whatsappOptin: true },
      })
      expect(hayCheckbox(container)).toBe(true)
      expect(screen.getByText(/repetición por WhatsApp/i)).toBeInTheDocument()
    })

  /* US estrena el 14/09/2026 su propio A/B de captura de teléfono: control sin
     pedirlo (solo honeypot) frente a la rama con el checkbox de WhatsApp. Es el
     mismo mecanismo que corrió en EU, con códigos propios. */
  for (const c of [
    { marca: 'Blocks US', slug: 'blocks-us', escuela: 'conquer-blocks', storageKey: 'form_variant_cb_us_tel', sinTelefono: '73', conCheckbox: '74' },
    { marca: 'Languages US', slug: 'languages-us', escuela: 'conquer-languages', storageKey: 'form_variant_cl_us_tel', sinTelefono: '75', conCheckbox: '76' },
  ]) {
    it(`${c.marca} ${c.sinTelefono} (control): no se pide el teléfono`, () => {
      const { container } = montar({ slug: c.slug, escuela: c.escuela, region: 'us', storageKey: c.storageKey, variante: c.sinTelefono })
      expect(hayCheckbox(container)).toBe(false)
      // El honeypot sí existe (capta el autofill del navegador), pero va
      // escondido fuera de pantalla: lo que no debe haber es un campo visible.
      expect(telefonoVisible(container)).toBe(false)
    })

    it(`${c.marca} ${c.conCheckbox} (test): sale el checkbox de WhatsApp`, () => {
      const { container } = montar({ slug: c.slug, escuela: c.escuela, region: 'us', storageKey: c.storageKey, variante: c.conCheckbox })
      expect(hayCheckbox(container)).toBe(true)
      expect(screen.getByText(/repetición por WhatsApp/i)).toBeInTheDocument()
    })

    it(`${c.marca}: la variante viaja en el lead`, async () => {
      const { container } = montar({ slug: c.slug, escuela: c.escuela, region: 'us', storageKey: c.storageKey, variante: c.conCheckbox })
      expect((await enviar(container)).utm_form_variant).toBe(c.conCheckbox)
    })
  }

  it('Blocks EU sin la bandera de config se queda sin checkbox', () => {
    // Fija que el checkbox depende SOLO de la config: si la migración no llega
    // a una fila, la landing pierde el check y hay que enterarse.
    const { container } = montar({ slug: 'blocks-eu', region: 'eu', storageKey: 'form_variant_cb_eu_fondo', variante: '70' })
    expect(hayCheckbox(container)).toBe(false)
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

  /* Conquer AI no corre ningún A/B: pide el teléfono siempre y obligatorio, sin
     checkbox, fijo por config (`landing.phoneRequired`, migración 0032). Su
     landing clonó de Blocks EU la bandera `whatsappOptin`, que la migración
     quita; estos tests fijan que el campo no dependa de ninguna variante. */
  it('Conquer AI: teléfono visible y obligatorio, sin checkbox', async () => {
    const { container } = montar({
      slug: 'ai-eu', region: 'eu', landing: { phoneRequired: true },
    })
    expect(hayCheckbox(container)).toBe(false)
    expect(telefonoVisible(container)).toBe(true)
    expect(screen.getByPlaceholderText(/número de whatsapp \*/i)).toBeInTheDocument()

    fireEvent.change(screen.getByPlaceholderText(/nombre/i), { target: { value: 'Ana' } })
    fireEvent.change(screen.getByPlaceholderText(/email/i), { target: { value: 'ana@ejemplo.com' } })
    enviarForm(container)
    await waitFor(() => expect(screen.getByText(/ingresa tu número de whatsapp/i)).toBeInTheDocument())
    expect(registerLead).not.toHaveBeenCalled()
  })

  it('el teléfono obligatorio manda sobre el checkbox de la config', () => {
    // Si una fila conserva las dos banderas (la migración se aplica sobre una
    // config clonada), no puede salir el check: no hay nada que revelar.
    const { container } = montar({
      slug: 'ai-eu', region: 'eu', landing: { phoneRequired: true, whatsappOptin: true },
    })
    expect(hayCheckbox(container)).toBe(false)
    expect(telefonoVisible(container)).toBe(true)
  })

  it('Blocks LATAM no hereda el checkbox de EU', () => {
    const { container } = montar({ slug: 'blocks-latam', storageKey: 'form_variant_cb_latam', variante: '58' })
    expect(hayCheckbox(container)).toBe(false)
  })
})
