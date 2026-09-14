import { expect, test } from '@playwright/test'
import { forzarVariante, simularBackend, urlEtapa } from './helpers'

/* Las dos variantes de cada test en las tres regiones de Conquer Languages, en
   navegador real contra el bundle compilado. US ya no corre el de fondo: lo
   cerró el 14/09/2026 con el papel como ganador y pasó al de teléfono. */
const REGIONES = [
  { region: 'latam', fondo: 'form_variant_cl_latam', control: '63', blanco: '64', video: 'form_variant_video_cl_latam', vControl: '11', vSin: '12' },
  { region: 'eu', fondo: 'form_variant_cl_eu', control: '65', blanco: '66', video: 'form_variant_video_cl_eu', vControl: '13', vSin: '14' },
  { region: 'us', video: 'form_variant_video_cl_us', vControl: '15', vSin: '16', telefono: 'form_variant_cl_us_tel', sinTelefono: '75', conCheckbox: '76' },
]

for (const r of REGIONES) {
  const base = { slug: `languages-${r.region}`, escuela: 'conquer-languages', region: r.region }
  const fondo = (page) => page.locator('#funnel-root > div').first()

  if (r.fondo) {
    test(`Languages ${r.region.toUpperCase()} · landing en blanco (${r.blanco})`, async ({ page }) => {
      await forzarVariante(page, r.fondo, r.blanco)
      await page.goto(urlEtapa(base))
      await expect(fondo(page)).toHaveCSS('background-color', 'rgb(255, 255, 255)')
      await expect(fondo(page)).toHaveCSS('background-image', 'none')
    })

    test(`Languages ${r.region.toUpperCase()} · landing de control conserva el papel (${r.control})`, async ({ page }) => {
      await forzarVariante(page, r.fondo, r.control)
      await page.goto(urlEtapa(base))
      await expect(fondo(page)).toHaveCSS('background-color', 'rgb(250, 250, 250)')
      await expect(fondo(page)).not.toHaveCSS('background-image', 'none')
    })
  }

  if (r.telefono) {
    test(`Languages ${r.region.toUpperCase()} · el checkbox de WhatsApp sale en la rama ${r.conCheckbox}`, async ({ page }) => {
      await forzarVariante(page, r.telefono, r.conCheckbox)
      await page.goto(urlEtapa(base))
      await expect(page.locator('input[type="checkbox"]').first()).toBeVisible()
    })

    test(`Languages ${r.region.toUpperCase()} · el control (${r.sinTelefono}) no pide el teléfono`, async ({ page }) => {
      await forzarVariante(page, r.telefono, r.sinTelefono)
      await page.goto(urlEtapa(base))
      await expect(page.locator('input[type="checkbox"]')).toHaveCount(0)
      // El honeypot es un input[type=tel] escondido a -10000px dentro de un
      // contenedor aria-hidden; para Playwright «existe», así que se cuentan
      // solo los que están fuera de esa caja.
      const pedidos = await page.evaluate(() => [...document.querySelectorAll('input[type="tel"]')]
        .filter((i) => !i.closest('[aria-hidden="true"]')).length)
      expect(pedidos).toBe(0)
    })

    test(`Languages ${r.region.toUpperCase()} · la landing se queda en papel en las dos ramas`, async ({ page }) => {
      for (const v of [r.sinTelefono, r.conCheckbox]) {
        await forzarVariante(page, r.telefono, v)
        await page.goto(urlEtapa(base))
        await expect(fondo(page)).toHaveCSS('background-color', 'rgb(250, 250, 250)')
      }
    })
  }

  test(`Languages ${r.region.toUpperCase()} · vídeo sin footer (${r.vSin})`, async ({ page }) => {
    await simularBackend(page)
    await forzarVariante(page, r.video, r.vSin)
    await page.goto(urlEtapa({ ...base, stage: 'video', video: 1 }))
    await expect(page.locator('footer')).toHaveCount(0)
    const ultimo = await page.evaluate(() => {
      const raiz = document.querySelector('#funnel-root > div')
      return getComputedStyle(raiz.lastElementChild).backgroundColor
    })
    expect(ultimo).toBe('rgb(0, 0, 0)')
  })

  test(`Languages ${r.region.toUpperCase()} · vídeo de control mantiene footer con logo (${r.vControl})`, async ({ page }) => {
    await simularBackend(page)
    await forzarVariante(page, r.video, r.vControl)
    await page.goto(urlEtapa({ ...base, stage: 'video', video: 1 }))
    await expect(page.locator('footer')).toBeVisible()
    await expect(page.locator('footer img:not([aria-hidden="true"]):visible').first()).toBeVisible()
  })
}
