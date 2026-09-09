/**
 * El `journey_id` no puede arrastrar la query string que se le pegue detrás.
 *
 * Viaja de etapa a etapa por la URL y va SIEMPRE el último parámetro, así que
 * cuando Facebook añade su `?fbclid=…` al final de la URL entera, aterriza
 * dentro de su valor. En producción se vieron identificadores de 237 caracteres
 * para un formato que mide 24, y el CRM rechazaba la prellamada entera contra su
 * varchar(100) (FUNNELS-7T).
 */
import { describe, expect, it } from 'vitest'

import { saneaId } from '../../src/lib/trackingIds'

// El valor real que llegó de la prellamada 20014 en producción.
const CONTAMINADO = 'jrn_1788885337291_tvn8i8?fbclid=IwVERFWAUNGOZwZG9mBWZk'
  + 'aWQWUOA1FncpGP4kWbgJf5Y7QDJcN7Z-RWV4dG4DYWVtATAAYWRpZAGrNbptedS1c3J0YwZhcHBf'
const LIMPIO = 'jrn_1788885337291_tvn8i8'

describe('saneaId', () => {
  it('quita el fbclid que Facebook pega detrás', () => {
    expect(saneaId(CONTAMINADO)).toBe(LIMPIO)
  })

  it('deja el identificador dentro del varchar(100) del CRM', () => {
    expect(CONTAMINADO.length).toBeGreaterThan(100)
    expect(saneaId(CONTAMINADO).length).toBeLessThanOrEqual(100)
  })

  it('corta también por & y por #', () => {
    expect(saneaId('jrn_123_abc&utm_source=fb')).toBe('jrn_123_abc')
    expect(saneaId('jrn_123_abc#seccion')).toBe('jrn_123_abc')
  })

  it('no toca un identificador limpio', () => {
    expect(saneaId(LIMPIO)).toBe(LIMPIO)
    expect(saneaId('1788885337291_00v86z')).toBe('1788885337291_00v86z')
  })

  it('aguanta los vacíos', () => {
    expect(saneaId(null)).toBe('')
    expect(saneaId(undefined)).toBe('')
    expect(saneaId('')).toBe('')
  })
})
