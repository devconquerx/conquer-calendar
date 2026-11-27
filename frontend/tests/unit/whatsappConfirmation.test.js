import { describe, expect, it } from 'vitest'
import { isWhatsappRequested, whatsappBrand, WHATSAPP_URL } from '../../src/components/WhatsappConfirmation'

describe('confirmación por WhatsApp (closers sin setter)', () => {
  it('solo se activa con ?confirmar=whatsapp', () => {
    expect(isWhatsappRequested('?event_id=1&confirmar=whatsapp')).toBe(true)
    expect(isWhatsappRequested('?event_id=1')).toBe(false)
    expect(isWhatsappRequested('')).toBe(false)
    expect(isWhatsappRequested(undefined)).toBe(false)
  })

  it('existe para Blocks, Finance y Languages, no para el resto', () => {
    expect(whatsappBrand('conquerblocks')).toBeTruthy()
    expect(whatsappBrand('conquerfinance')).toBeTruthy()
    expect(whatsappBrand('conquerlanguages')).toBeTruthy()
    expect(whatsappBrand('conquerlegal')).toBeNull()
  })

  it('lleva al canal de WhatsApp de Respond.io', () => {
    expect(WHATSAPP_URL).toBe('https://wa.me/34602407862')
  })
})

describe('vista previa', () => {
  it('solo con ?vista_previa=1', async () => {
    const { isVistaPrevia } = await import('../../src/components/WhatsappConfirmation')
    expect(isVistaPrevia('?confirmar=whatsapp&vista_previa=1')).toBe(true)
    expect(isVistaPrevia('?confirmar=whatsapp')).toBe(false)
  })
})
