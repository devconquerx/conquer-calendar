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
    // El presupuesto por defecto son 30 s, menos que la espera de abajo.
    test.slow()
    const avisos = []
    const erroresDePagina = []
    page.on('console', (m) => m.type() === 'warning' && avisos.push(m.text()))
    page.on('pageerror', (e) => erroresDePagina.push(e.message))

    await simularBackend(page)
    await page.goto(urlEtapa({ stage: 'video', video: 1 }))

    /* Se espera a que el aviso aparezca, no una cantidad fija de tiempo.
       Con `waitForTimeout(2500)` el test pasaba suelto y fallaba dentro de
       `check.sh`, donde compite con la suite de Django y la de vitest: cuánto
       tarda el navegador en rendirse con el mp4 que no existe depende de lo
       ocupada que esté la máquina, y 2,5 s no siempre bastan. El margen es
       generoso a propósito —se vio agotar uno de 15 s con la suite entera en
       marcha— porque aquí esperar de más no cuesta nada: en cuanto el aviso
       aparece, el test sigue. */
    const delReproductor = () => avisos.filter((t) => t.includes('[VSL] error del reproductor'))
    await expect.poll(() => delReproductor().length, { timeout: 45_000 }).toBeGreaterThan(0)
    // El motivo concreto es lo que faltaba para poder diagnosticar.
    expect(delReproductor().join(' ')).toMatch(/ABORTED|NETWORK|DECODE|SRC_NOT_SUPPORTED|sin MediaError/)
    expect(erroresDePagina).toEqual([])
  })

  /* La causa de que este fichero fallara de vez en cuando, que resultó no ser
     cosa del test: el manejador de errores se registraba al montar Plyr, y el
     <video> falla antes de que Plyr llegue. Con el chunk retrasado tres
     segundos el fallo no se reportaba NUNCA.

     En producción no es un detalle: Plyr tarda más justamente en los móviles
     lentos y las redes malas, que es donde el vídeo falla, así que a Sentry le
     faltaban precisamente los peores casos. Ahora el manejador va en el
     <video>, que existe desde el primer render. */
  test('el fallo se reporta aunque Plyr llegue tarde', async ({ page }) => {
    const avisos = []
    page.on('console', (m) => m.type() === 'warning' && avisos.push(m.text()))

    await simularBackend(page)
    await page.route('**/assets/plyr-*.js*', async (route) => {
      await new Promise((r) => setTimeout(r, 3000))
      return route.fallback()
    })
    await page.goto(urlEtapa({ stage: 'video', video: 1 }))

    const delReproductor = () => avisos.filter((t) => t.includes('[VSL] error del reproductor'))
    await expect.poll(() => delReproductor().length, { timeout: 30_000 }).toBeGreaterThan(0)
    // Y una sola vez: el mismo fallo llega por el <video> y por el evento de Plyr.
    expect(delReproductor()).toHaveLength(1)
  })
})
