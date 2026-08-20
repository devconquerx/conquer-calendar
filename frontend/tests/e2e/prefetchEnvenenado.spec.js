import { expect, test } from '@playwright/test'
import { enviarLanding, simularBackend, urlEtapa } from './helpers'

/**
 * FUNNELS-47: la precarga de la landing no puede bloquear la navegación.
 *
 * En la landing se adelanta la descarga de las etapas siguientes al primer
 * gesto del usuario. Si esa descarga falla —un móvil que pierde cobertura un
 * segundo— el navegador MEMORIZA el fallo: cualquier import posterior del mismo
 * módulo devuelve el error guardado sin volver a pedirlo a la red. Comprobado:
 * reintentar la misma URL no hace ni una petición; solo funciona cambiándola.
 *
 * Resultado para el visitante: precarga rota = salto a vídeo roto, aunque su
 * conexión ya vaya perfecta. Y le pasa justo a quien tiene mala red, que es a
 * quien la optimización pretendía ayudar.
 *
 * Aquí se corta SOLO la petición de la precarga; a partir de ahí la red va bien.
 */
test.describe('precarga que falla en la landing', () => {
  test('el visitante llega igualmente a la página de vídeo', async ({ page }) => {
    let cortadas = 0
    const peticiones = []

    await simularBackend(page)
    // Registrada después de simularBackend: en Playwright gana la última.
    await page.route('**/assets/VideoPage-*.js', (route) => {
      const esLaPrimera = cortadas === 0
      cortadas += esLaPrimera ? 1 : 0
      peticiones.push(esLaPrimera ? 'precarga: CORTADA' : 'navegación: permitida')
      return esLaPrimera ? route.abort('failed') : route.continue()
    })

    await page.goto(urlEtapa({ video: 1 }))

    // Gesto del usuario: es lo que dispara la precarga.
    await page.mouse.move(200, 300)
    await page.mouse.down()
    await page.mouse.up()
    await page.waitForTimeout(600)
    expect(peticiones[0]).toBe('precarga: CORTADA')

    // La red ya va bien. El visitante rellena la landing y avanza.
    await enviarLanding(page, { nombre: 'QA prefetch', email: 'qa@ejemplo.com' })

    // Debe ver el vídeo, no el plan B del ErrorBoundary.
    await expect(page.locator('#funnel-root video').first()).toBeAttached({ timeout: 10_000 })
    await expect(page.getByRole('alert')).toHaveCount(0)
  })

  test('una precarga fallida no ensucia con errores sin capturar', async ({ page }) => {
    const errores = []
    page.on('pageerror', (e) => errores.push(e.message))

    await simularBackend(page)
    await page.route('**/assets/{VideoPage,Funnel}-*.js', (route) =>
      route.request().url().includes('?') ? route.continue() : route.abort('failed')
    )

    await page.goto(urlEtapa({ video: 1 }))
    await page.mouse.move(200, 300)
    await page.mouse.down()
    await page.mouse.up()
    await page.waitForTimeout(800)

    expect(errores).toEqual([])
  })
})
