import { lazy } from 'react'

/**
 * Import dinámico que sobrevive a un chunk que no llegó.
 *
 * El detalle que hace falta conocer: cuando un `import()` dinámico falla, el
 * navegador MEMORIZA el fallo. Cualquier import posterior del mismo módulo
 * devuelve el error guardado sin volver a pedirlo a la red — comprobado en
 * Chrome: el segundo intento no genera ni una petición. Reintentar la misma
 * URL, por tanto, no sirve de nada.
 *
 * La única salida es pedir una URL distinta, y por eso se le añade un
 * parámetro. Los imports internos del chunk se resuelven contra la ruta (sin
 * query), así que siguen apuntando a los módulos ya cargados: no se duplica
 * React ni ninguna dependencia compartida.
 *
 * Esto importa porque la landing precarga las etapas siguientes al primer gesto
 * del visitante. Si esa precarga se cae —un móvil que pierde cobertura un
 * segundo—, sin este reintento el salto a vídeo o al formulario queda roto para
 * siempre, aunque la conexión ya vaya perfecta.
 */
export function importarConReintento(cargar) {
  return cargar().catch((error) => {
    const url = /(https?:\/\/[^\s'"]+?\.js)/.exec(String(error && error.message))?.[1]
    if (!url) throw error
    return import(/* @vite-ignore */ `${url}?reintento=${Date.now()}`)
  })
}

/* Marca en la pestaña que ya se recargó por un chunk que no llegó. Sin esto, un
   chunk que de verdad no existe recargaría en bucle. Va en `sessionStorage`
   —no en memoria— justamente porque tiene que sobrevivir a la recarga, y en
   try/catch porque hay navegadores que deniegan el almacenamiento. */
const CLAVE_RECARGA = 'cqx_recarga_por_chunk'

function yaSeRecargo() {
  try {
    return sessionStorage.getItem(CLAVE_RECARGA) === '1'
  } catch {
    // Sin almacenamiento no hay forma de saberlo, y recargar a ciegas puede
    // ser un bucle. Se prefiere no recargar.
    return true
  }
}

function anotarRecarga() {
  try {
    sessionStorage.setItem(CLAVE_RECARGA, '1')
    return true
  } catch {
    return false
  }
}

/**
 * `React.lazy` con reintento y, como último recurso, una recarga.
 *
 * Cuando ni el reintento sirve, el chunk no está en el servidor: es HTML viejo
 * —cacheado, o una pestaña abierta desde antes— pidiendo ficheros de un build
 * que el despliegue azul/verde ya sustituyó. Ahí no hay nada que reintentar,
 * porque el fichero no existe; lo que hace falta es el HTML nuevo, y eso es
 * una recarga (FUNNELS-47, los eventos que llegan con `?reintento=` en la url:
 * el reintento corrió y también falló).
 *
 * La recarga es SOLO para las etapas del funnel. `importarConReintento` a secas
 * —el que usa el reproductor para hls.js y Plyr— no recarga: ahí un fallo puede
 * pillar al visitante con el vídeo ya en marcha, y recargarle la página encima
 * sería peor que el fallo que intenta arreglar.
 */
export function lazyConReintento(cargar) {
  return lazy(() => importarConReintento(cargar).catch((error) => {
    if (yaSeRecargo() || !anotarRecarga()) throw error
    window.location.reload()
    // La recarga no es instantánea: sin esto React pintaría el error justo
    // antes de que la página se vaya. Esta promesa no se resuelve nunca a
    // propósito, así que el visitante se queda en el último fotograma bueno.
    return new Promise(() => {})
  }))
}
