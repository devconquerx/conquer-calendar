import { expect, test } from '@playwright/test'
import { simularBackend, urlEtapa } from './helpers'

/* FUNNELS-CY: el vídeo se quedaba congelado para siempre tras un bache de red.
   259 fallos en siete días y subiendo, casi todos Android en LATAM.

   Un error `fatal` de hls.js no significa "no se puede reproducir": significa
   que la librería ha agotado SUS reintentos (seis por fragmento, con espera
   creciente) y ha llamado a `stopLoad()`. Reanudar tiene que pedirlo quien la
   usa, y nosotros solo lo reportábamos a Sentry. El visitante se quedaba
   mirando un fotograma quieto aunque la cobertura volviera al segundo.

   Aquí se reproduce entero contra el navegador: se corta un fragmento hasta
   que hls.js se rinde, se comprueba que el vídeo se queda clavado, se devuelve
   la red y se comprueba que vuelve a avanzar. Sin el arreglo, la última
   comprobación falla: el tiempo no se mueve nunca más.

   `__CQX_HLS_CONFIG__` baja los reintentos de hls.js. Con los de serie, un
   fallo fatal de verdad tarda 33 segundos en llegar (medido) y este test no lo
   ejecutaría nadie; con esto, medio segundo. Lo que se prueba es lo mismo: qué
   hacemos NOSOTROS cuando la librería se rinde. */
const HLS_IMPACIENTE = {
  fragLoadPolicy: {
    default: {
      maxTimeToFirstByteMs: 1000,
      maxLoadTimeMs: 2000,
      timeoutRetry: { maxNumRetry: 1, retryDelayMs: 0, maxRetryDelayMs: 0 },
      errorRetry: { maxNumRetry: 1, retryDelayMs: 100, maxRetryDelayMs: 200 },
    },
  },
}

/** Segundo de vídeo en el que va el reproductor, o null si ya no está. */
const segundoActual = (page) => page.evaluate(() => {
  const v = document.querySelector('video')
  return v ? v.currentTime : null
})

test.describe('vídeo HLS — recuperación tras un bache de red', () => {
  test('el vídeo revive cuando vuelve la red, en vez de quedarse congelado', async ({ page }) => {
    const fatales = []
    page.on('console', (m) => {
      if (m.text().includes('[VSL] hls.js fatal')) fatales.push(m.text())
    })

    await page.addInitScript(
      (config) => { window.__CQX_HLS_CONFIG__ = config },
      HLS_IMPACIENTE,
    )
    await simularBackend(page)

    /* Se corta el SEGUNDO fragmento, no el primero: así el vídeo llega a
       arrancar —que es el caso de campo— y se puede distinguir "no empezó
       nunca" de "empezó y se quedó tieso". */
    let hayRed = false
    await page.route('**/hls/seg*.ts', (route) => {
      const esElPrimero = route.request().url().endsWith('seg0.ts')
      if (hayRed || esElPrimero) return route.fallback()
      return route.abort('connectionfailed')
    })

    await page.goto(urlEtapa({ stage: 'video', video: 1, query: 'hls=1' }))

    // 1. Arranca con el fragmento que sí llega.
    await expect.poll(() => segundoActual(page), { timeout: 15_000 }).toBeGreaterThan(0)

    // 2. hls.js agota sus reintentos y se declara vencido: aquí empezamos nosotros.
    await expect.poll(() => fatales.length, { timeout: 15_000 }).toBeGreaterThan(0)

    /* 3. Y mientras no hay red, el vídeo se queda clavado. Este es el bug.
       Primero hay que dejar que se agote el buffer que ya tenía descargado: el
       fatal salta mientras todavía quedan segundos por reproducir, así que
       durante un par de segundos el vídeo sigue avanzando con lo que le queda.
       Clavado es donde se detiene DESPUÉS de eso. */
    let clavado = null
    await expect.poll(async () => {
      const antes = await segundoActual(page)
      await page.waitForTimeout(700)
      const despues = await segundoActual(page)
      clavado = despues
      return antes === despues
    }, { timeout: 15_000 }).toBe(true)
    expect(clavado).toBeGreaterThan(0)

    // 4. Vuelve la cobertura. Sin el arreglo, esto no cambia nada: nadie le
    //    pide a hls.js que reanude y el vídeo sigue congelado para siempre.
    hayRed = true

    /* El `null` del final es un aprobado, no un fallo: el vídeo llegó hasta el
       final y el funnel pasó de etapa, así que el <video> ya no está en el DOM.
       Solo se puede llegar ahí reproduciendo. */
    await expect
      .poll(async () => {
        const t = await segundoActual(page)
        return t === null ? Infinity : t
      }, { timeout: 20_000 })
      .toBeGreaterThan(clavado)
  })

  /* Lo anterior demuestra que revive; esto, que revive PRONTO.
     En la primera versión del arreglo las esperas entre reintentos eran de 1, 3
     y 8 segundos, y este mismo montaje enseñó el precio: la red volvía a los 6 s
     y el vídeo no se movía hasta los 13,7 s. Ocho segundos de fotograma quieto
     con la conexión ya perfecta, encima de los 33 que hls.js había tardado en
     rendirse. Ahora el aviso `online` del navegador adelanta el reintento. */
  test('el aviso de que volvió la red adelanta el reintento pendiente', async ({ page }) => {
    await page.addInitScript(
      (config) => { window.__CQX_HLS_CONFIG__ = config },
      HLS_IMPACIENTE,
    )
    await simularBackend(page)

    /* Lo que se mide es CUÁNDO vuelve a pedirse el fragmento, no cuándo se
       nota en `currentTime`: el instante de la petición lo apunta este mismo
       manejador, sin depender de lo cargada que esté la máquina ni de cada
       cuánto sondee Playwright. Un test de reloj tiene que medir donde el
       reloj es fiable. */
    let hayRed = false
    const pedidos = []
    await page.route('**/hls/seg*.ts', (route) => {
      const esElPrimero = route.request().url().endsWith('seg0.ts')
      if (esElPrimero) return route.fallback()
      pedidos.push(Date.now())
      if (hayRed) return route.fallback()
      return route.abort('connectionfailed')
    })

    await page.goto(urlEtapa({ stage: 'video', video: 1, query: 'hls=1' }))

    // Se deja llegar al tercer reintento, el de la espera más larga (4 s): así
    // adelantarlo se nota, y no se confunde con que venciera solo.
    await expect.poll(() => pedidos.length, { timeout: 20_000 }).toBeGreaterThanOrEqual(6)
    const clavado = await segundoActual(page)
    const pedidosAntes = pedidos.length

    // Vuelve la red y el navegador lo anuncia, como al recuperar cobertura.
    hayRed = true
    const desde = Date.now()
    await page.evaluate(() => window.dispatchEvent(new Event('online')))

    await expect.poll(() => pedidos.length, { timeout: 10_000 }).toBeGreaterThan(pedidosAntes)
    // Con la espera a secas habría tardado los 4 s del temporizador pendiente.
    expect(pedidos[pedidosAntes] - desde).toBeLessThan(2000)

    // Y el vídeo efectivamente sigue.
    await expect.poll(async () => {
      const t = await segundoActual(page)
      return t === null ? Infinity : t
    }, { timeout: 15_000 }).toBeGreaterThan(clavado)
  })

  /* FUNNELS-77, la mitad con `motor_video: chromium`: ~59 eventos semanales de
     SRC_NOT_SUPPORTED que parecían un problema del vídeo o del códec y no lo
     eran. Salían de aquí: cuando el chunk de hls.js no llegaba —red mala, un
     bloqueador, un despliegue que se llevó el fichero por delante— el código le
     pasaba el `.m3u8` pelado al navegador, y Chrome no reproduce HLS. El
     fallback fabricaba el error en lugar de evitarlo.

     La primera petición del chunk se tumba y se deja pasar la segunda, que es
     la del reintento. Si el reintento funciona, el vídeo se ve igual. */
  test('el vídeo se ve aunque el chunk de hls.js falle a la primera', async ({ page }) => {
    const avisos = []
    page.on('console', (m) => avisos.push(m.text()))

    await simularBackend(page)

    let caidas = 0
    await page.route('**/assets/hls-*.js*', (route) => {
      // Solo la primera. El reintento pide la misma url con `?reintento=`, que
      // para el navegador es otro recurso: sin eso se quedaría con el fallo
      // guardado y no volvería a pedir nada.
      if (caidas === 0) { caidas += 1; return route.abort('connectionfailed') }
      return route.fallback()
    })

    await page.goto(urlEtapa({ stage: 'video', video: 1, query: 'hls=1' }))

    // Se reproduce: el reintento trajo la librería.
    await expect.poll(() => segundoActual(page), { timeout: 20_000 }).toBeGreaterThan(0)
    // Y llegó ahí por el camino que dice el test, no porque el chunk cargara a
    // la primera (la comprobación va después de reproducir: cuando `goto`
    // devuelve, el reproductor aún no ha pedido la librería).
    expect(caidas).toBe(1)
    // Y el <video> nunca llegó a recibir el .m3u8, que es lo que producía el
    // SRC_NOT_SUPPORTED: su fuente es el blob de MediaSource que pone hls.js.
    const fuente = await page.evaluate(() => document.querySelector('video')?.currentSrc || '')
    expect(fuente.startsWith('blob:')).toBe(true)
    expect(avisos.join(' ')).not.toContain('[VSL] no se pudo cargar hls.js')
  })

  /* El mismo remedio para el import de al lado. `plyr-*.js` es el chunk que más
     falla de todo el funnel —encabeza FUNNELS-47, y FUNNELS-5E es ese mismo
     fallo contado por Safari: ~54 a la semana, todos en páginas de vídeo— y se
     caía a la primera. El chunk existe: el mismo hash se sirve bien desde los
     otros dominios de marca, así que es la petición lo que se pierde. */
  test('el reproductor arranca aunque el chunk de Plyr falle a la primera', async ({ page }) => {
    await simularBackend(page)

    let caidas = 0
    await page.route('**/assets/plyr-*.js*', (route) => {
      if (caidas === 0) { caidas += 1; return route.abort('connectionfailed') }
      return route.fallback()
    })

    await page.goto(urlEtapa({ stage: 'video', video: 1, query: 'hls=1' }))

    await expect.poll(() => segundoActual(page), { timeout: 20_000 }).toBeGreaterThan(0)
    expect(caidas).toBe(1)
    // Plyr envuelve el <video> en su propio contenedor: si está, es que cargó.
    expect(await page.locator('.plyr').count()).toBeGreaterThan(0)
  })
})
