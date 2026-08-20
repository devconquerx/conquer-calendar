import { lazy } from 'react'

/**
 * `React.lazy` que sobrevive a un chunk que no llegó.
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
export function lazyConReintento(cargar) {
  return lazy(() =>
    cargar().catch((error) => {
      const url = /(https?:\/\/[^\s'"]+?\.js)/.exec(String(error && error.message))?.[1]
      if (!url) throw error
      return import(/* @vite-ignore */ `${url}?reintento=${Date.now()}`)
    })
  )
}
