/**
 * El uuid de la Prellamada tiene que sobrevivir a volver a entrar al embudo.
 *
 * Antes se generaba por montaje y no se guardaba, así que reingresar creaba una
 * Prellamada nueva; al pedir la misma hora ya reservada, la reserva (OneToOne)
 * ya tenía dueña y el POST devolvía 500 (FUNNELS-96). Ahora se reutiliza 24h.
 */
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import {
  UUID_PRELLAMADA_TTL_MS,
  generatePrellamadaUuid,
  getOrCreatePrellamadaUuid,
} from '../../src/lib/trackingIds'

const CLAVE = 'cqx_prellamada_uuid'

describe('uuid de la Prellamada', () => {
  beforeEach(() => { localStorage.clear(); vi.useRealTimers() })
  afterEach(() => { vi.useRealTimers() })

  it('se reutiliza al volver a entrar', () => {
    const primero = getOrCreatePrellamadaUuid()
    expect(getOrCreatePrellamadaUuid()).toBe(primero)
  })

  it('caduca a las 24 horas', () => {
    vi.useFakeTimers()
    const primero = getOrCreatePrellamadaUuid()

    vi.advanceTimersByTime(UUID_PRELLAMADA_TTL_MS - 1000)
    expect(getOrCreatePrellamadaUuid()).toBe(primero)

    vi.advanceTimersByTime(2000)
    expect(getOrCreatePrellamadaUuid()).not.toBe(primero)
  })

  it('es un uuid v4 válido', () => {
    expect(getOrCreatePrellamadaUuid()).toMatch(
      /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i
    )
  })

  it('un valor corrupto no lo rompe: genera uno nuevo', () => {
    localStorage.setItem(CLAVE, 'no-es-json')
    expect(getOrCreatePrellamadaUuid()).toMatch(/^[0-9a-f]{8}-/i)
  })

  it('un valor del formato viejo (uuid pelado) se descarta', () => {
    localStorage.setItem(CLAVE, '11111111-1111-4111-8111-111111111111')
    expect(getOrCreatePrellamadaUuid()).not.toBe('11111111-1111-4111-8111-111111111111')
  })

  it('con el almacenamiento bloqueado sigue dando uuids, sin lanzar', () => {
    const original = Object.getOwnPropertyDescriptor(window, 'localStorage')
    Object.defineProperty(window, 'localStorage', {
      configurable: true,
      get() { throw new DOMException('Access is denied for this document.', 'SecurityError') },
    })
    try {
      expect(getOrCreatePrellamadaUuid()).toMatch(/^[0-9a-f]{8}-/i)
    } finally {
      Object.defineProperty(window, 'localStorage', original)
    }
  })

  it('generatePrellamadaUuid sigue dando uno suelto cada vez', () => {
    expect(generatePrellamadaUuid()).not.toBe(generatePrellamadaUuid())
  })
})
