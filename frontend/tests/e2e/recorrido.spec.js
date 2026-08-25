import { expect, test } from '@playwright/test'
import { enviarLanding, esperarEtapa, forzarVariante, responderPaso, simularBackend, urlEtapa } from './helpers'

/* Recorrido completo en navegador real. Aquí es donde se detectan los fallos
   que ni el build ni los tests de componente ven: navegación entre etapas,
   estado que viaja por la URL y payloads que salen a la red. */

test.describe('landing → StepForm', () => {
  test('el StepForm llega pre-rellenado con lo que el visitante escribió en la landing', async ({ page }) => {
    await simularBackend(page)
    // Con UTMs en la URL de entrada: así llega el tráfico de campañas, y era el
    // caso que rompía el prefill (se arrastraba el query del arranque).
    await page.goto(urlEtapa({ query: 'utm_source=meta&utm_campaign=agosto' }))
    await enviarLanding(page, { nombre: 'Andrés QA', email: 'qa@ejemplo.com' })

    await esperarEtapa(page, 'Bienvenido')
    await expect(page).toHaveURL(/name=Andr/)
    await page.getByRole('button', { name: /comenzar/i }).click()

    await expect(page.getByRole('textbox').first()).toHaveValue('Andrés QA')
    await page.getByRole('button', { name: /siguiente/i }).first().click()
    await expect(page.getByRole('textbox').first()).toHaveValue('qa@ejemplo.com')
  })

  test('el lead sale con los datos del formulario y la variante de la landing', async ({ page }) => {
    const enviado = await simularBackend(page)
    await forzarVariante(page, 'form_variant_cb_latam', '58')
    await page.goto(urlEtapa({ query: 'utm_source=meta&gclid=G1' }))
    await enviarLanding(page)

    await expect.poll(() => enviado.leads.length).toBe(1)
    expect(enviado.leads[0]).toMatchObject({
      name: 'Andrés QA', email: 'qa@ejemplo.com',
      escuela: 'conquer-blocks', funnel: 'blocks-latam',
      utm_source: 'meta', gclid: 'G1', utm_form_variant: '58',
    })
  })

  test('los UTMs de la campaña sobreviven al salto de etapa', async ({ page }) => {
    await simularBackend(page)
    await page.goto(urlEtapa({ query: 'utm_source=meta&utm_campaign=agosto&gclid=G1' }))
    await enviarLanding(page)
    await esperarEtapa(page, 'Bienvenido')
    await expect(page).toHaveURL(/utm_source=meta/)
    await expect(page).toHaveURL(/gclid=G1/)
  })
})

test.describe('A/B de fondo blanco (landing)', () => {
  const fondo = (page) => page.locator('#funnel-root > div').first()

  test('la variante 58 pinta la landing en blanco, sin textura', async ({ page }) => {
    await forzarVariante(page, 'form_variant_cb_latam', '58')
    await page.goto(urlEtapa())
    await expect(fondo(page)).toHaveCSS('background-color', 'rgb(255, 255, 255)')
    await expect(fondo(page)).toHaveCSS('background-image', 'none')
  })

  test('la variante 57 conserva el papel', async ({ page }) => {
    await forzarVariante(page, 'form_variant_cb_latam', '57')
    await page.goto(urlEtapa())
    await expect(fondo(page)).toHaveCSS('background-color', 'rgb(250, 250, 250)')
    await expect(fondo(page)).not.toHaveCSS('background-image', 'none')
  })

  test('Finance LATAM comparte el mecanismo aunque su tema sea otro', async ({ page }) => {
    await forzarVariante(page, 'form_variant_cf_latam', '62')
    await page.goto(urlEtapa({ slug: 'finance-latam', escuela: 'conquer-finance' }))
    await expect(fondo(page)).toHaveCSS('background-color', 'rgb(255, 255, 255)')
  })

  test('el ?force_form_variant de QA fuerza la variante y se limpia de la URL', async ({ page }) => {
    await page.goto(urlEtapa({ query: 'force_form_variant=58&utm_source=meta' }))
    await expect(page).not.toHaveURL(/force_form_variant/)
    await expect(page).toHaveURL(/utm_source=meta/)
    await expect(fondo(page)).toHaveCSS('background-color', 'rgb(255, 255, 255)')
  })

  /* El fondo blanco cubre el funnel ENTERO, así que hay que comprobarlo etapa
     por etapa: cada una resuelve su propio tema y la que se olvide de aplicar
     la variante deja al visitante viendo papel en mitad del recorrido. Corren
     en escritorio y en móvil, que es donde se vería un escalón de color. */
  test('la página de vídeo también va en blanco, sin escalón en el rasgado', async ({ page }) => {
    await forzarVariante(page, 'form_variant_cb_latam', '58')
    await page.goto(urlEtapa({ stage: 'video' }))
    const cabecera = page.locator('header').first()
    await expect(cabecera).toHaveCSS('background-color', 'rgb(255, 255, 255)')
    await expect(cabecera).toHaveCSS('background-image', 'none')
    // El rasgado es papel crema: sin aclararlo se ve el corte contra el blanco.
    const rasgado = page.locator('img[src*="torn"]').first()
    await expect(rasgado).toHaveCSS('filter', 'brightness(1.25)')
  })

  test('la página de vídeo de control conserva su papel', async ({ page }) => {
    await forzarVariante(page, 'form_variant_cb_latam', '57')
    await page.goto(urlEtapa({ stage: 'video' }))
    const cabecera = page.locator('header').first()
    await expect(cabecera).not.toHaveCSS('background-image', 'none')
    await expect(page.locator('img[src*="torn"]').first()).toHaveCSS('filter', 'none')
  })

  test('el stepform va en blanco y sin textura de papel', async ({ page }) => {
    await forzarVariante(page, 'form_variant_cb_latam', '58')
    await page.goto(urlEtapa({ stage: 'stepform' }))
    const wrap = page.locator('.funnel-wrap')
    await expect(wrap).toHaveCSS('background-color', 'rgb(255, 255, 255)')
    await expect(wrap).toHaveCSS('background-image', 'none')
  })

  test('el stepform de control conserva el papel', async ({ page }) => {
    await forzarVariante(page, 'form_variant_cb_latam', '57')
    await page.goto(urlEtapa({ stage: 'stepform' }))
    await expect(page.locator('.funnel-wrap')).not.toHaveCSS('background-image', 'none')
  })

  test('la confirmación va en blanco', async ({ page }) => {
    await forzarVariante(page, 'form_variant_cb_latam', '58')
    await page.goto(urlEtapa({ stage: 'confirmation' }))
    const seccion = page.locator('section').first()
    await expect(seccion).toHaveCSS('background-color', 'rgb(255, 255, 255)')
    await expect(seccion).toHaveCSS('background-image', 'none')
  })

  test('la confirmación de control conserva su papel', async ({ page }) => {
    // Blocks pinta el color por estilo (#FAFAFA tileado), no con la clase
    // crema, así que lo que distingue a la rama de control es la textura.
    await forzarVariante(page, 'form_variant_cb_latam', '57')
    await page.goto(urlEtapa({ stage: 'confirmation' }))
    await expect(page.locator('section').first()).not.toHaveCSS('background-image', 'none')
  })
})

test.describe('A/B del footer (página de vídeo)', () => {
  // :visible descarta el logo del otro breakpoint (móvil/escritorio se
  // conmutan por clases, así que ambos están en el DOM).
  const logosDelFooter = (page) => page.locator('footer img:not([aria-hidden="true"]):visible')

  test('la variante de control muestra el logo', async ({ page }) => {
    await simularBackend(page)
    await forzarVariante(page, 'form_variant_video_cb_latam', '3')
    await page.goto(urlEtapa({ stage: 'video', video: 1 }))
    await expect(logosDelFooter(page).first()).toBeVisible()
  })

  test('la variante de test quita el footer entero: el negro llega al final', async ({ page }) => {
    await simularBackend(page)
    await forzarVariante(page, 'form_variant_video_cb_latam', '4')
    await page.goto(urlEtapa({ stage: 'video', video: 1 }))
    await expect(page.locator('footer')).toHaveCount(0)
    // Lo último de la página es la zona oscura del vídeo.
    const fondoFinal = await page.evaluate(() => {
      const raiz = document.querySelector('#funnel-root > div')
      const ultimo = raiz.lastElementChild
      return getComputedStyle(ultimo).backgroundColor
    })
    expect(fondoFinal).toBe('rgb(0, 0, 0)')
  })

  test('quien no pasa por el vídeo no entra en el experimento', async ({ page }) => {
    await simularBackend(page)
    await page.goto(urlEtapa({ stage: 'stepform' }))
    await esperarEtapa(page, 'Bienvenido')
    const claves = await page.evaluate(() => Object.keys(localStorage).filter((k) => k.startsWith('form_variant_video')))
    expect(claves).toHaveLength(0)
  })

  test('quien sí pasa recibe variante y viaja en la prellamada, no en el lead', async ({ page }) => {
    const enviado = await simularBackend(page)
    await forzarVariante(page, 'form_variant_video_cb_latam', '4')
    await page.goto(urlEtapa({ stage: 'stepform' }))
    await esperarEtapa(page, 'Bienvenido')

    await page.getByRole('button', { name: /comenzar/i }).click()
    await responderPaso(page, { etiqueta: 'Nombre', valor: 'Andrés QA' })
    await responderPaso(page, { etiqueta: 'Tu mejor correo', valor: 'qa@ejemplo.com' })
    // Al pasar del teléfono, el StepForm crea la Prellamada (pre-schedule
    // progresivo): es el primer momento en que la variante del vídeo viaja.
    await responderPaso(page, { etiqueta: 'Número de teléfono', valor: '600123456' })

    await expect.poll(() => enviado.prellamadas.length, { timeout: 10_000 }).toBeGreaterThan(0)
    expect(enviado.prellamadas.at(-1).tracking.utm_form_variant).toBe('4')
    expect(enviado.leads).toHaveLength(0)
  })
})
