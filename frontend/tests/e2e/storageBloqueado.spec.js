import { expect, test } from '@playwright/test'
import { enviarLanding, simularBackend, urlEtapa } from './helpers'

/* El funnel en un navegador que deniega el almacenamiento (FUNNELS-4D).
   Se reproduce la condición real: el GETTER de window.localStorage lanza
   SecurityError, instalado con addInitScript para que ocurra ANTES de que corra
   el bundle. Antes del arreglo, esto dejaba la página completamente en blanco;
   ahora el visitante tiene que poder convertir igual. */
const BLOQUEAR = () => {
  Object.defineProperty(window, 'localStorage', {
    configurable: true,
    get() { throw new DOMException('Access is denied for this document.', 'SecurityError') },
  })
}

test.describe('almacenamiento denegado por el navegador', () => {
  test('la landing pinta y no lanza ningún error', async ({ page }) => {
    const errores = []
    page.on('pageerror', (e) => errores.push(e.message))

    await simularBackend(page)
    await page.addInitScript(BLOQUEAR)
    await page.goto(urlEtapa({}))

    await expect(page.getByRole('button', { name: /ver vídeo gratis/i })).toBeVisible()
    const texto = (await page.locator('#funnel-root').innerText()).trim()
    expect(texto.length).toBeGreaterThan(50)
    expect(errores).toEqual([])
  })

  test('el visitante convierte y el lead llega con su atribución', async ({ page }) => {
    const enviado = await simularBackend(page)
    await page.addInitScript(BLOQUEAR)
    await page.goto(urlEtapa({ query: 'utm_source=meta&utm_campaign=agosto&gclid=G1' }))
    await enviarLanding(page, { nombre: 'QA sin storage', email: 'qa@ejemplo.com' })

    await expect.poll(() => enviado.leads.length).toBe(1)
    // Lo que importa del negocio: la campaña y el gclid viajan igual, porque
    // salen de la URL y no del almacenamiento.
    expect(enviado.leads[0]).toMatchObject({
      name: 'QA sin storage', email: 'qa@ejemplo.com',
      utm_source: 'meta', utm_campaign: 'agosto', gclid: 'G1',
    })
    expect(enviado.leads[0].journey_id).toBeTruthy()
  })
})
