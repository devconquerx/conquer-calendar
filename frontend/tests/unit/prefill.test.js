import { describe, expect, it } from 'vitest'
import { getPrefillFromSearch, getPrefillRespuestas } from '../../src/lib/prefillParams'

/* El prefill es la costura entre la landing y el StepForm: la landing mete los
   datos del lead en la URL y el StepForm los lee de ahí. Si esto se rompe, el
   visitante reescribe a mano lo que ya había puesto (y muchos abandonan). */
describe('prefill desde el query string', () => {
  it('lee los datos que la landing propaga', () => {
    const p = getPrefillFromSearch('?name=Andr%C3%A9s&email=a%40b.com&phone=%2B34612345678')
    expect(p).toMatchObject({ name: 'Andrés', email: 'a@b.com', phone: '+34612345678' })
  })

  it('acepta fullname como alias de name', () => {
    expect(getPrefillFromSearch('?fullname=Ana').name).toBe('Ana')
    // `name` gana cuando vienen los dos (la landing manda ambos).
    expect(getPrefillFromSearch('?name=Ana&fullname=Otro').name).toBe('Ana')
  })

  it('reconstruye el teléfono desde las claves legacy', () => {
    expect(getPrefillFromSearch('?lead_phone=612345678&lead_phone_prefix=34').phone).toBe('+34612345678')
    expect(getPrefillFromSearch('?lead_phone=612345678').phone).toBe('+612345678')
  })

  it('devuelve vacíos con un query sin datos, sin inventar claves', () => {
    expect(getPrefillRespuestas('?utm_source=meta')).toEqual({})
    expect(getPrefillRespuestas('')).toEqual({})
    expect(getPrefillRespuestas(undefined)).toEqual({})
  })

  it('mapea solo los campos con valor a los ids de bloque del StepForm', () => {
    expect(getPrefillRespuestas('?name=Ana&email=a%40b.com')).toEqual({ name: 'Ana', email: 'a@b.com' })
  })
})
