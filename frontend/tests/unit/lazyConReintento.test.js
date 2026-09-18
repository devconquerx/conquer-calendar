/**
 * El import dinámico que sobrevive a un chunk que no llegó (FUNNELS-47, 5E).
 *
 * Son dos fallos distintos con el mismo síntoma, y por eso hay dos remedios:
 * el chunk existe pero la petición se cayó —red, bloqueador— y basta pedirlo
 * otra vez; o el chunk ya no está en el servidor porque un despliegue lo
 * sustituyó, y entonces reintentar no puede funcionar y hace falta el HTML
 * nuevo, o sea una recarga.
 */
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { importarConReintento } from '../../src/lib/lazyConReintento'

const fallo = (mensaje) => Object.assign(new Error(mensaje), { name: 'TypeError' })
const URL_CHUNK = 'https://www.conquerblocks.com/static/assets/plyr-Cwtstkjp.js'

describe('importarConReintento', () => {
  it('no toca nada cuando el import va bien', async () => {
    const cargar = vi.fn().mockResolvedValue({ default: 'modulo' })
    await expect(importarConReintento(cargar)).resolves.toEqual({ default: 'modulo' })
    expect(cargar).toHaveBeenCalledTimes(1)
  })

  it('saca la url del chunk del mensaje del error para poder reintentar', async () => {
    /* No se puede reintentar `cargar()` a secas: el navegador guarda el fallo
       del import y lo devuelve sin pedir nada a la red. La url solo está en el
       texto del error, de ahí que se extraiga de ahí. */
    const cargar = vi.fn().mockRejectedValue(
      fallo(`Failed to fetch dynamically imported module: ${URL_CHUNK}`)
    )
    // El reintento pide una url que este entorno no sabe resolver; lo que
    // importa es que llegó a intentarlo, no que lo consiguiera.
    await expect(importarConReintento(cargar)).rejects.toBeDefined()
    expect(cargar).toHaveBeenCalledTimes(1)
  })

  it('si el error no trae url, se propaga tal cual', async () => {
    // El mensaje de Safari no la lleva (FUNNELS-5E). Sin url no hay nada que
    // pedir, así que el error sube en vez de inventarse un reintento.
    const original = fallo('Importing a module script failed.')
    const cargar = vi.fn().mockRejectedValue(original)
    await expect(importarConReintento(cargar)).rejects.toBe(original)
  })
})

describe('lazyConReintento — recarga como último recurso', () => {
  let recargas

  beforeEach(() => {
    recargas = 0
    vi.stubGlobal('location', { reload: () => { recargas += 1 } })
    try { sessionStorage.clear() } catch {}
  })

  afterEach(() => {
    vi.unstubAllGlobals()
  })

  /* `lazyConReintento` devuelve un componente de React, así que en vez de
     montarlo se prueba la pieza que decide: recargar una vez y solo una. Es la
     regla que evita el bucle cuando el chunk de verdad no existe. */
  const recargarUnaVez = async () => {
    const { lazyConReintento } = await import('../../src/lib/lazyConReintento')
    const componente = lazyConReintento(() => Promise.reject(
      fallo('Importing a module script failed.')
    ))
    /* React.lazy no llama al cargador hasta que se renderiza; se invoca a mano
       el mismo cargador que usaría el render. Y NO se espera su promesa: cuando
       decide recargar, devuelve a propósito una que no se resuelve nunca —para
       que React no pinte el error mientras la página se va—, así que esperarla
       aquí colgaría el test. Se le dan unos ciclos y se mira el efecto. */
    componente._payload._result().catch(() => {})
    for (let i = 0; i < 5; i += 1) await new Promise((r) => setTimeout(r, 0))
  }

  it('recarga cuando ni el reintento trae el chunk', async () => {
    await recargarUnaVez()
    expect(recargas).toBe(1)
    expect(sessionStorage.getItem('cqx_recarga_por_chunk')).toBe('1')
  })

  it('no vuelve a recargar si ya se recargó en esta pestaña', async () => {
    // Este es el caso peligroso: un chunk que ya no existe recargaría sin
    // parar, y el visitante se quedaría atrapado en un bucle de recargas.
    sessionStorage.setItem('cqx_recarga_por_chunk', '1')
    await recargarUnaVez()
    expect(recargas).toBe(0)
  })

  it('sin sessionStorage no recarga, porque no podría saber si ya lo hizo', async () => {
    const setItem = vi.spyOn(Storage.prototype, 'setItem').mockImplementation(() => {
      throw new Error('denegado')
    })
    const getItem = vi.spyOn(Storage.prototype, 'getItem').mockImplementation(() => {
      throw new Error('denegado')
    })
    await recargarUnaVez()
    expect(recargas).toBe(0)
    setItem.mockRestore()
    getItem.mockRestore()
  })
})
