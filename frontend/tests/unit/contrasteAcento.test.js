import { describe, expect, it } from 'vitest'
import conquerblocks from '../../src/themes/conquerblocks'
import conquerlanguages from '../../src/themes/conquerlanguages'
import conquerfinance from '../../src/themes/conquerfinance'
import conquerlegal from '../../src/themes/conquerlegal'

/* El acento del tema pinta los controles: los días disponibles del calendario,
   el relleno del día elegido y el borde de la opción marcada. Sobre el blanco de
   la tarjeta tiene que leerse.

   El teal de Languages estaba en 2.35:1 y se veía lavado aunque los días ya van
   en negrita — la negrita no arregla el contraste. Se cambió al teal oscuro que
   la marca ya tenía definido. Este test es para que no vuelva a aclararse. */

const luminancia = (hex) => {
  const canales = [0, 2, 4].map((i) => {
    const c = parseInt(hex.replace('#', '').slice(i, i + 2), 16) / 255
    return c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4
  })
  return 0.2126 * canales[0] + 0.7152 * canales[1] + 0.0722 * canales[2]
}

const contraste = (a, b) => {
  const [alta, baja] = [luminancia(a), luminancia(b)].sort((x, y) => y - x)
  return (alta + 0.05) / (baja + 0.05)
}

const BLANCO = '#ffffff'   // --bk-card-bg, el fondo de la tarjeta del calendario
const MINIMO = 3.0         // WCAG AA para elementos de interfaz

describe('contraste del acento del tema', () => {
  it('la función de contraste da los valores conocidos', () => {
    expect(contraste(BLANCO, BLANCO)).toBeCloseTo(1, 2)
    expect(contraste('#000000', BLANCO)).toBeCloseTo(21, 1)
    expect(contraste('#0069ff', BLANCO)).toBeCloseTo(4.7, 1)   // el azul por defecto
  })

  for (const [nombre, tema] of [
    ['Languages', conquerlanguages],
    ['Finance', conquerfinance],
    ['Legal', conquerlegal],
  ]) {
    it(`${nombre}: el acento se lee sobre la tarjeta`, () => {
      const acento = tema.cssVars['--theme-accent']
      expect(acento).toMatch(/^#[0-9a-fA-F]{6}$/)
      expect(contraste(acento, BLANCO)).toBeGreaterThanOrEqual(MINIMO)
    })
  }

  /* Blocks queda fuera del bucle a sabiendas: su naranja da 2.80:1, por debajo
     del mínimo igual que estaba el teal, pero se decidió no tocarlo de momento.
     Este test fija el valor para que la excepción sea visible y no un descuido.
     Si algún día se oscurece, subirlo al bucle de arriba y borrar esto. */
  it('Blocks sigue con el naranja de marca, por debajo del mínimo (decidido)', () => {
    const acento = conquerblocks.cssVars['--theme-accent']
    expect(acento).toBe('#F97316')
    expect(contraste(acento, BLANCO)).toBeLessThan(MINIMO)
  })

  it('Languages usa el teal oscuro, no el claro de marca', () => {
    // El claro sigue vivo en el hero y los degradados; lo que no puede volver
    // es a los controles.
    expect(conquerlanguages.cssVars['--theme-accent']).toBe('#3E7F92')
    expect(contraste('#70B3C4', BLANCO)).toBeLessThan(MINIMO)
  })

  it('el hover es más oscuro que el color en reposo', () => {
    const { '--theme-accent': acento, '--theme-accent-hover': hover } = conquerlanguages.cssVars
    expect(luminancia(hover)).toBeLessThan(luminancia(acento))
  })
})
