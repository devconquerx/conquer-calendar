import { expect, test } from '@playwright/test'
import { forzarVariante, simularBackend, urlEtapa } from './helpers'

/* Las dos variantes de los dos tests en las tres regiones de Conquer Languages,
   en navegador real contra el bundle compilado. */
const REGIONES = [
  { region: 'latam', fondo: 'form_variant_cl_latam', control: '63', blanco: '64', video: 'form_variant_video_cl_latam', vControl: '11', vSin: '12' },
  { region: 'eu', fondo: 'form_variant_cl_eu', control: '65', blanco: '66', video: 'form_variant_video_cl_eu', vControl: '13', vSin: '14' },
  { region: 'us', fondo: 'form_variant_cl_us', control: '67', blanco: '68', video: 'form_variant_video_cl_us', vControl: '15', vSin: '16' },
]

for (const r of REGIONES) {
  const base = { slug: `languages-${r.region}`, escuela: 'conquer-languages', region: r.region }
  const fondo = (page) => page.locator('#funnel-root > div').first()

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
