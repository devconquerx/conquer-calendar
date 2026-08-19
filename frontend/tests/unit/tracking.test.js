import { describe, expect, it } from 'vitest'
import { buildTrackingPayload, getClickIds, getUtmParams } from '../../src/lib/utmParams'

describe('tracking que viaja al backend', () => {
  it('recoge los UTMs y los click ids de la URL', () => {
    window.history.replaceState({}, '', '/?utm_source=meta&utm_campaign=c1&gclid=G1&fbclid=F1&ajeno=x')
    expect(getUtmParams()).toMatchObject({ utm_source: 'meta', utm_campaign: 'c1' })
    expect(getUtmParams().ajeno).toBeUndefined()
    expect(getClickIds()).toMatchObject({ gclid: 'G1', fbclid: 'F1' })
  })

  it('no arrastra la variante A/B por sí solo: la ponen la landing o el StepForm explícitamente', () => {
    window.history.replaceState({}, '', '/?utm_form_variant=99')
    expect(getUtmParams().utm_form_variant).toBeUndefined()
  })

  it('arma el payload con ids, utms, cookies y contexto del navegador', () => {
    const payload = buildTrackingPayload({
      eventId: 'e1', journeyId: 'j1', uuid: 'u1',
      utmParams: { utm_source: 'meta' }, clickIds: { gclid: 'G1' },
      pixelCookies: { _fbp: 'p', _fbc: 'c', _ttp: 't' },
    })
    expect(payload).toMatchObject({
      event_id: 'e1', journey_id: 'j1', uuid: 'u1',
      utm_source: 'meta', gclid: 'G1', _fbp: 'p', _fbc: 'c', _ttp: 't',
    })
    expect(payload.url).toBeTruthy()
    expect(payload.user_agent).toBeTruthy()
  })

  it('omite el uuid cuando no lo hay (la landing no crea prellamada)', () => {
    expect('uuid' in buildTrackingPayload({ eventId: 'e', journeyId: 'j' })).toBe(false)
  })
})
