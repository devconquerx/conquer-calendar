/**
 * El ping de progreso del vídeo (FUNNELS-3R).
 *
 * Es telemetría fire-and-forget: sale hasta 10 veces por espectador y no debe
 * costarle nada al visitante. Se manda con sendBeacon para que sobreviva a que
 * la página se cierre y para no arrastrar un preflight CORS por ping.
 */
import { describe, expect, it, vi, afterEach } from 'vitest'
import { sendVideoProgressToBackend } from '../../src/api'

const DATOS = { email: 'qa@ejemplo.com', percent: 30, school: 'conquer-blocks', region: 'latam' }

afterEach(() => {
  vi.restoreAllMocks()
  vi.unstubAllGlobals()
})

describe('sendVideoProgressToBackend', () => {
  it('usa sendBeacon cuando el navegador lo soporta, y no toca fetch', async () => {
    const beacon = vi.fn(() => true)
    vi.stubGlobal('navigator', { sendBeacon: beacon })
    const fetchSpy = vi.fn()
    vi.stubGlobal('fetch', fetchSpy)

    sendVideoProgressToBackend(DATOS)

    expect(beacon).toHaveBeenCalledTimes(1)
    expect(fetchSpy).not.toHaveBeenCalled()

    const [url, blob] = beacon.mock.calls[0]
    expect(url).toContain('/f/api/video-progress/')
    // text/plain = simple request = sin preflight CORS.
    expect(blob.type).toMatch(/text\/plain/)
    // jsdom no implementa Blob.text(), así que se lee con FileReader.
    const texto = await new Promise((resolve) => {
      const lector = new FileReader()
      lector.onload = () => resolve(lector.result)
      lector.readAsText(blob)
    })
    expect(JSON.parse(texto)).toEqual(DATOS)
  })

  it('cae a fetch si el navegador no tiene sendBeacon', () => {
    vi.stubGlobal('navigator', {})
    const fetchSpy = vi.fn(() => Promise.resolve({ ok: true }))
    vi.stubGlobal('fetch', fetchSpy)

    sendVideoProgressToBackend(DATOS)

    expect(fetchSpy).toHaveBeenCalledTimes(1)
    expect(JSON.parse(fetchSpy.mock.calls[0][1].body)).toEqual(DATOS)
  })

  it('si sendBeacon rechaza el envío, se intenta por fetch', () => {
    vi.stubGlobal('navigator', { sendBeacon: vi.fn(() => false) })
    const fetchSpy = vi.fn(() => Promise.resolve({ ok: true }))
    vi.stubGlobal('fetch', fetchSpy)

    sendVideoProgressToBackend(DATOS)

    expect(fetchSpy).toHaveBeenCalledTimes(1)
  })

  it('un fallo de red no propaga ni tumba nada', async () => {
    vi.spyOn(console, 'warn').mockImplementation(() => {})
    vi.stubGlobal('navigator', {})
    vi.stubGlobal('fetch', vi.fn(() => Promise.reject(new TypeError('Failed to fetch'))))

    expect(() => sendVideoProgressToBackend(DATOS)).not.toThrow()
    await new Promise((r) => setTimeout(r, 0))
    expect(console.warn).toHaveBeenCalled()
  })
})
