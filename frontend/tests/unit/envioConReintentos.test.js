/**
 * Registro del lead y prellamada intermedia (FUNNELS-D2/7K/7P).
 *
 * Son fire-and-forget: un "Failed to fetch" (red móvil, navegador in-app) los
 * perdía. Ahora se reintentan dos veces antes de darlos por perdidos.
 */
import { describe, expect, it, vi, afterEach, beforeEach } from 'vitest'
import * as Sentry from '@sentry/react'
import { registerLead, sendPreSchedule } from '../../src/api'

vi.mock('@sentry/react', () => ({ captureException: vi.fn() }))

const ok = () => Promise.resolve(new Response('{}', { status: 200 }))
const sinRed = () => Promise.reject(new TypeError('Failed to fetch'))

beforeEach(() => {
  vi.useFakeTimers()
  vi.spyOn(console, 'error').mockImplementation(() => {})
})

afterEach(() => {
  vi.useRealTimers()
  vi.restoreAllMocks()
  vi.unstubAllGlobals()
  Sentry.captureException.mockClear()
})

describe('envíos fire-and-forget con reintento', () => {
  it('si la red falla una vez, el reintento entrega el lead y no avisa a Sentry', async () => {
    const fetchSpy = vi.fn().mockImplementationOnce(sinRed).mockImplementation(ok)
    vi.stubGlobal('fetch', fetchSpy)

    const envio = registerLead({ email: 'qa@ejemplo.com' })
    await vi.runAllTimersAsync()
    await envio

    expect(fetchSpy).toHaveBeenCalledTimes(2)
    expect(fetchSpy.mock.calls[1][1].body).toBe(JSON.stringify({ email: 'qa@ejemplo.com' }))
    expect(Sentry.captureException).not.toHaveBeenCalled()
  })

  it('tras tres intentos fallidos lo reporta una sola vez', async () => {
    const fetchSpy = vi.fn().mockImplementation(sinRed)
    vi.stubGlobal('fetch', fetchSpy)

    const envio = sendPreSchedule('cb-latam', { q: 1 })
    await vi.runAllTimersAsync()
    await envio

    expect(fetchSpy).toHaveBeenCalledTimes(3)
    expect(Sentry.captureException).toHaveBeenCalledTimes(1)
    expect(Sentry.captureException.mock.calls[0][1].tags.action).toBe('sendPreSchedule')
  })

  it('un error que no es de red no se reintenta', async () => {
    const fetchSpy = vi.fn().mockImplementation(() => Promise.reject(new Error('otro')))
    vi.stubGlobal('fetch', fetchSpy)

    const envio = registerLead({ email: 'qa@ejemplo.com' })
    await vi.runAllTimersAsync()
    await envio

    expect(fetchSpy).toHaveBeenCalledTimes(1)
    expect(Sentry.captureException).toHaveBeenCalledTimes(1)
  })
})
