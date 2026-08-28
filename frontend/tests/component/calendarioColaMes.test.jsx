import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import Calendar from '../../src/components/Calendar'

/* La última fila del calendario se completa con los primeros días del mes
   siguiente y esos días son reservables: a final de mes el visitante ya no
   tiene que pasar de mes para ver las horas de pasado mañana.

   Dos reglas que este test fija, porque las dos se rompieron antes:
     * el relleno del PRINCIPIO se sigue ocultando (el mes arranca en el día 1);
     * el relleno del FINAL se pinta siempre — apagado si no tiene horas, pero
       visible: la clase `out` lleva visibility:hidden y dejaba huecos en mitad
       de la fila.

   Marzo de 2027 empieza en lunes y tiene 31 días: la cuadrícula sale de 5 filas
   exactas y la cola es del 1 al 4 de abril. */

const MARZO = {
  mes: '2027-03-01',
  mes_anterior: null,
  mes_siguiente: '2027-04-01',
  max_fecha: '2027-05-09',
  dias: {
    '2027-03-31': ['09:00'],
    '2027-04-01': ['09:00'],
    '2027-04-02': ['09:00'],
    // 3 y 4 de abril (sábado y domingo) sin horas: apagados pero visibles.
  },
  slots_utc: {},
}

function celda(container, dia) {
  return [...container.querySelectorAll('.bk-day')].find(el => el.textContent.trim() === String(dia))
}

describe('cola de la cuadrícula del calendario del funnel', () => {
  beforeEach(() => {
    vi.useFakeTimers({ shouldAdvanceTime: true })
    vi.setSystemTime(new Date('2027-03-10T09:00:00'))
    vi.stubGlobal('fetch', vi.fn(() => Promise.resolve({ json: () => Promise.resolve(MARZO) })))
  })

  afterEach(() => {
    vi.useRealTimers()
    vi.unstubAllGlobals()
  })

  const montar = () => render(
    <Calendar hostSlug="host" eventTypeSlug="evento" eventoInfo={null} onSlotSelected={() => {}} theme={null} />
  )

  it('los días de la cola con horas son reservables', async () => {
    const { container } = montar()
    await waitFor(() => expect(container.querySelector('.bk-day')).toBeTruthy())
    // Se busca en la última fila para no confundir el 1 de abril con el 1 de marzo.
    const ultima = [...container.querySelectorAll('tbody tr')].pop()
    const dias = [...ultima.querySelectorAll('.bk-day')].map(el => [el.textContent.trim(), el.className, el.tagName])
    expect(dias.map(d => d[0])).toEqual(['29', '30', '31', '1', '2', '3', '4'])
    expect(dias.find(d => d[0] === '1')[1]).toContain('avail')
    expect(dias.find(d => d[0] === '2')[1]).toContain('avail')
  })

  it('los días de la cola sin horas se ven apagados, no ocultos', async () => {
    const { container } = montar()
    await waitFor(() => expect(container.querySelector('.bk-day')).toBeTruthy())
    const ultima = [...container.querySelectorAll('tbody tr')].pop()
    const dias = [...ultima.querySelectorAll('.bk-day')]
    for (const dia of ['3', '4']) {
      const el = dias.find(e => e.textContent.trim() === dia)
      expect(el.className).not.toContain('out')
      expect(el.className).not.toContain('avail')
    }
  })

  it('el relleno del principio sigue oculto', async () => {
    // Abril de 2027 empieza en jueves: la primera fila arrastra 29, 30 y 31 de
    // marzo, que se ocultan aunque el 31 tenga horas.
    vi.stubGlobal('fetch', vi.fn(() => Promise.resolve({
      json: () => Promise.resolve({ ...MARZO, mes: '2027-04-01' }),
    })))
    const { container } = montar()
    await waitFor(() => expect(container.querySelector('.bk-day')).toBeTruthy())
    const primera = container.querySelector('tbody tr')
    const dias = [...primera.querySelectorAll('.bk-day')]
    for (const dia of ['29', '30', '31']) {
      expect(dias.find(e => e.textContent.trim() === dia).className).toContain('out')
    }
  })
})
