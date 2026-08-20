/**
 * El funnel con el almacenamiento denegado por el navegador (FUNNELS-4D).
 *
 * No se simula "localStorage lleno" ni "setItem falla": se reproduce lo que
 * hace de verdad el navegador cuando bloquea el almacenamiento — que el GETTER
 * de `window.localStorage` lance SecurityError. Es la diferencia que hacía
 * inútiles los guards tipo `typeof localStorage !== 'undefined'` y que dejaba
 * la landing entera en blanco para ~47 visitas de pago al día.
 */
import { describe, expect, it, vi, afterEach } from 'vitest'
import { render, screen } from '@testing-library/react'
import Landing from '../../src/pages/Landing'
import ErrorBoundary from '../../src/components/ErrorBoundary'
import { leer, guardar } from '../../src/lib/safeStorage'
import { renderConFunnel } from './helpers'

vi.mock('../../src/api', () => ({ registerLead: vi.fn() }))

const CONFIG = {
  landing: {
    title: 'Titular', subtitle: 'sub', description: 'desc',
    bullets: ['uno'], buttonText: 'Ver vídeo gratis',
    instructor: { name: 'X', role: 'Y', description: 'z' },
  },
}

const real = Object.getOwnPropertyDescriptor(window, 'localStorage')

function bloquearAlmacenamiento() {
  Object.defineProperty(window, 'localStorage', {
    configurable: true,
    get() {
      throw new DOMException('Access is denied for this document.', 'SecurityError')
    },
  })
}

afterEach(() => {
  if (real) Object.defineProperty(window, 'localStorage', real)
})

describe('almacenamiento bloqueado por el navegador', () => {
  it('leer la propiedad localStorage lanza: por eso el guard `typeof` no vale', () => {
    bloquearAlmacenamiento()
    expect(() => typeof localStorage).toThrow(/Access is denied/)
  })

  it('safeStorage lo absorbe en vez de propagarlo', () => {
    bloquearAlmacenamiento()
    expect(leer('lo_que_sea')).toBeNull()
    expect(guardar('lo_que_sea', 'valor')).toBe(false)
  })

  it('la landing sigue pintando, con su formulario y su botón', () => {
    bloquearAlmacenamiento()
    renderConFunnel(
      <Landing school={{ slug: 'conquer-blocks' }} program="fullstack" region="latam"
               formConfig={CONFIG} funnelSlug="blocks-latam" videoEnabled />
    )
    expect(screen.getByRole('button', { name: /ver vídeo gratis/i })).toBeInTheDocument()
    expect(screen.getByPlaceholderText(/nombre/i)).toBeInTheDocument()
    expect(screen.getByPlaceholderText(/email/i)).toBeInTheDocument()
  })
})

describe('ErrorBoundary', () => {
  it('un fallo en el render pinta el plan B en vez de dejar la página vacía', () => {
    vi.spyOn(console, 'error').mockImplementation(() => {})
    const Explota = () => { throw new Error('boom') }

    const { container } = render(
      <ErrorBoundary><Explota /></ErrorBoundary>
    )

    expect(container.textContent).not.toBe('')
    expect(screen.getByRole('alert')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /reintentar/i })).toBeInTheDocument()
  })

  it('no estorba cuando no hay fallo', () => {
    render(<ErrorBoundary><p>contenido normal</p></ErrorBoundary>)
    expect(screen.getByText('contenido normal')).toBeInTheDocument()
  })
})
