import { expect } from '@playwright/test'

/** URL de una etapa del funnel en el servidor de pruebas. */
export function urlEtapa({ stage = 'landing', slug = 'blocks-latam', escuela = 'conquer-blocks', region = 'latam', video = 0, query = '' } = {}) {
  const base = `/etapa?slug=${slug}&escuela=${escuela}&region=${region}&video=${video}&stage=${stage}`
  return query ? `${base}&${query}` : base
}

/* Backend simulado. Devuelve un registro de lo que el funnel envía, para poder
   afirmar sobre el payload real (que es donde viven los bugs de integración:
   un campo que no viaja, o que viaja en la entidad equivocada). */
export async function simularBackend(page) {
  const enviado = { leads: [], prellamadas: [] }

  /* Cinturón de seguridad: ninguna petición de un test puede salir de
     localhost. Si un cambio en la resolución de origen volviera a apuntar a
     calendar.conquerx.com, el test falla en vez de escribir en producción. */
  await page.route('**/*', async (route) => {
    const url = new URL(route.request().url())
    if (!['localhost', '127.0.0.1'].includes(url.hostname)) {
      if (route.request().method() !== 'GET') {
        throw new Error(`Un test intentó ${route.request().method()} contra ${url.host}: bloqueado`)
      }
      return route.abort()
    }
    return route.fallback()
  })

  // Orden IMPORTANTE: en Playwright gana la ruta registrada MÁS TARDE, así que
  // las genéricas van primero y las concretas al final. Al revés, el comodín de
  // /f/api/ se tragaría el POST del lead y el test no vería nada.

  // Red de seguridad para lo que no modelamos (progreso de vídeo, slots…).
  await page.route('**/f/api/**', (route) => route.fulfill({ status: 200, contentType: 'application/json', body: '{}' }))
  await page.route('**/*/slots.json*', (route) => route.fulfill({ status: 200, contentType: 'application/json', body: '{"slots":[]}' }))

  await page.route('**/f/api/*/resolver/', async (route) => {
    const cuerpo = JSON.parse(route.request().postData() || '{}')
    enviado.prellamadas.push(cuerpo)
    await route.fulfill({
      status: 200, contentType: 'application/json',
      body: JSON.stringify({ ok: true, prellamada_token: 'tok-test', resultado: 'aceptado', destino: 'calendario' }),
    })
  })

  await page.route('**/f/api/lead/', async (route) => {
    enviado.leads.push(JSON.parse(route.request().postData() || '{}'))
    await route.fulfill({ status: 200, contentType: 'application/json', body: '{"ok":true}' })
  })

  return enviado
}

/** Rellena y envía el formulario de la landing. */
export async function enviarLanding(page, { nombre = 'Andrés QA', email = 'qa@ejemplo.com' } = {}) {
  await page.getByPlaceholder(/nombre/i).fill(nombre)
  await page.getByPlaceholder(/email/i).fill(email)
  await page.getByRole('button', { name: /ver vídeo|ver video|comenzar/i }).click()
}

/** Fuerza una variante A/B antes de que arranque el bundle. */
export async function forzarVariante(page, clave, valor) {
  await page.addInitScript(([k, v]) => window.localStorage.setItem(k, v), [clave, valor])
}

/** Espera a que la SPA haya montado la etapa pedida. */
export async function esperarEtapa(page, texto) {
  await expect(page.getByText(texto, { exact: false }).first()).toBeVisible({ timeout: 10_000 })
}

/* Contesta un paso del StepForm esperando primero a que ESE paso esté montado.
   Las transiciones entre preguntas son animadas: sin la espera, el fill se
   aplica al input del paso anterior y el recorrido se desincroniza. */
export async function responderPaso(page, { etiqueta, valor }) {
  await expect(page.getByText(etiqueta, { exact: false }).first()).toBeVisible({ timeout: 10_000 })
  const campo = page.locator('input:visible').first()
  await expect(campo).toBeVisible()
  await campo.fill(valor)
  await page.getByRole('button', { name: /siguiente|enviar/i }).first().click()
}
