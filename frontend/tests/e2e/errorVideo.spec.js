import { expect, test } from '@playwright/test'
import { simularBackend, urlEtapa } from './helpers'

/* FUNNELS-69: los errores del reproductor llegaban a Sentry como "<unknown>".
   Plyr los emite como un CustomEvent que burbujea hasta window y ahí los recoge
   el manejador global del navegador, sin mensaje ni contexto: imposible saber
   por qué falla el vídeo de nadie.

   El servidor de pruebas sirve un mp4 que no existe, así que el reproductor
   falla siempre: sirve para comprobar que ahora el error se captura con su
   motivo y deja de escaparse a ciegas. */
test.describe('error del reproductor de vídeo', () => {
  test('se captura con motivo, y ya no se cuela como error anónimo', async ({ page }) => {
    const avisos = []
    const erroresDePagina = []
    page.on('console', (m) => m.type() === 'warning' && avisos.push(m.text()))
    page.on('pageerror', (e) => erroresDePagina.push(e.message))

    await simularBackend(page)
    await page.goto(urlEtapa({ stage: 'video', video: 1 }))
    await page.waitForTimeout(2500)

    const delReproductor = avisos.filter((t) => t.includes('[VSL] error del reproductor'))
    expect(delReproductor.length).toBeGreaterThan(0)
    // El motivo concreto es lo que faltaba para poder diagnosticar.
    expect(delReproductor.join(' ')).toMatch(/ABORTED|NETWORK|DECODE|SRC_NOT_SUPPORTED|sin MediaError/)
    expect(erroresDePagina).toEqual([])
  })
})
