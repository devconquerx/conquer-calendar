import { describe, expect, it } from 'vitest'
import { toWhiteBackground } from '../../src/themes/whiteBackground'
import conquerblocks from '../../src/themes/conquerblocks'
import conquerlegal from '../../src/themes/conquerlegal'

/* La variante de fondo blanco se aplica al tema, así que estos tests fijan el
   contrato: qué desaparece (el papel) y qué NO se toca (marca y estructura). */
describe('tema con fondo blanco', () => {
  for (const [nombre, tema] of [['Blocks', conquerblocks], ['Legal', conquerlegal]]) {
    describe(nombre, () => {
      const blanco = toWhiteBackground(tema)

      it('quita la textura de papel', () => {
        expect(tema.assets.paperboardTexture).toBeTruthy()
        expect(blanco.assets.paperboardTexture).toBeNull()
        expect(blanco.landing.bg).toBe('bg-white')
        expect(blanco.whiteBackground).toBe(true)
      })

      it('blanquea también el resto de etapas, no solo la landing', () => {
        // StepForm y calendario: wrapper y tarjeta.
        expect(tema.page.backgroundImage).toContain('url(')
        expect(blanco.page.backgroundImage).toBeUndefined()
        expect(blanco.page.backgroundColor).toBe('#FFFFFF')
        expect(blanco.cssVars['--theme-page-bg']).toBe('#FFFFFF')
        expect(blanco.cssVars['--theme-form-bg']).toBe('#FFFFFF')
        expect(blanco.cssVars['--theme-form-texture']).toBe('none')
      })

      it('anula la textura propia de la confirmación', () => {
        // Blocks trae una textura aparte en `confirmation`, así que no basta
        // con anular la del tema.
        if (!tema.confirmation) return
        expect(blanco.confirmation.texture).toBeNull()
        expect(blanco.confirmation.paso1Badge).toEqual(tema.confirmation.paso1Badge)
      })

      it('conserva el acento de marca, el logo y el resto de assets', () => {
        expect(blanco.accent).toEqual(tema.accent)
        expect(blanco.assets.logo).toBe(tema.assets.logo)
        expect(blanco.id).toBe(tema.id)
        expect(blanco.footer).toEqual(tema.footer)
      })

      it('no muta el tema original (lo comparten las demás etapas)', () => {
        expect(tema.assets.paperboardTexture).toBeTruthy()
        expect(tema.whiteBackground).toBeUndefined()
        expect(tema.landing.bg).not.toBe('bg-white')
        expect(tema.cssVars['--theme-form-texture']).toContain('url(')
        expect(tema.confirmation?.texture ?? null).not.toBeNull()
      })
    })
  }

  it('no revienta con un tema vacío', () => {
    expect(toWhiteBackground(null)).toBeNull()
    expect(toWhiteBackground({}).whiteBackground).toBe(true)
  })
})
