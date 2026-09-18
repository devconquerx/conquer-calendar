/**
 * Los datos que el reproductor adjunta cuando el vídeo falla.
 *
 * El cubo de errores de la VSL (FUNNELS-77) mezcla dos poblaciones —navegadores
 * reales y rastreadores con user-agent falseado— y no distingue entre las dos
 * explicaciones posibles del SRC_NOT_SUPPORTED: que el navegador rechace la
 * fuente de entrada, o que se pase medio minuto tragando datos hasta rendirse.
 * Estos tres datos son los que permiten separarlo en Sentry.
 */
import Hls from 'hls.js'
import { describe, expect, it } from 'vitest'

import {
  idDelVideo, motorDelFallo, planDeRecuperacionHls, segundosBuffereados, tramoDeEspera,
} from '../../src/components/vsl/VideoPlayer'

describe('motorDelFallo', () => {
  it('reconoce los mensajes de Chromium por su forma', () => {
    // Los tres textos son literales vistos en eventos reales de Sentry.
    expect(motorDelFallo(
      'PipelineStatus::DEMUXER_ERROR_NO_SUPPORTED_STREAMS: FFmpegDemuxer: no supported streams'
    )).toBe('chromium')
    expect(motorDelFallo('MEDIA_ELEMENT_ERROR: Format error')).toBe('chromium')
  })

  it('un mensaje vacío es WebKit, que no rellena MediaError.message', () => {
    expect(motorDelFallo('')).toBe('webkit-o-sin-mensaje')
    expect(motorDelFallo(undefined)).toBe('webkit-o-sin-mensaje')
  })

  it('delata al rastreador que dice ser un iPhone', () => {
    // Este es el caso que motivó la etiqueta: el evento llega con user-agent de
    // Mobile Safari, pero el texto del error solo lo produce Blink.
    expect(motorDelFallo('MEDIA_ELEMENT_ERROR: Format error')).not.toBe('webkit-o-sin-mensaje')
  })
})

describe('tramoDeEspera', () => {
  it('separa el rechazo inmediato de la agonía larga', () => {
    expect(tramoDeEspera(120)).toBe('<1s')
    expect(tramoDeEspera(3000)).toBe('1-5s')
    expect(tramoDeEspera(9000)).toBe('5-15s')
    expect(tramoDeEspera(30000)).toBe('15-45s')
    expect(tramoDeEspera(90000)).toBe('>45s')
  })

  it('sin medida no inventa un tramo', () => {
    expect(tramoDeEspera(null)).toBe('desconocido')
  })
})

describe('idDelVideo', () => {
  it('saca el nombre del fichero de las URL reales de las siete VSL', () => {
    expect(idDelVideo('https://vslconquerx.b-cdn.net/conquerblocks/conquerblocks-latam-2025.mp4'))
      .toBe('conquerblocks-latam-2025.mp4')
    expect(idDelVideo('https://vslconquerx.b-cdn.net/fi/VSL%20LATAM%20Tests/Nueva-VSL-CF-Latam-B-Sinparrafo.mp4'))
      .toBe('Nueva-VSL-CF-Latam-B-Sinparrafo.mp4')
  })

  it('descodifica los espacios del máster de 1,88 GB', () => {
    // Este es el vídeo cuya tasa de fallo hay que poder comparar contra el resto.
    expect(idDelVideo('https://vslconquerx.b-cdn.net/conquerblocks/VSL%20Corta%20Conquer%20Blocks%20-%20H264.mp4'))
      .toBe('VSL Corta Conquer Blocks - H264.mp4')
  })

  it('distingue dos vídeos distintos, que es para lo que existe', () => {
    const a = idDelVideo('https://cdn.test/a/conquerblocks-latam-2025.mp4')
    const b = idDelVideo('https://cdn.test/b/conquerblocks-spain-2025-compress.mp4')
    expect(a).not.toBe(b)
  })

  it('en HLS identifica por la carpeta, no por el nombre', () => {
    // Todas las URLs de Bunny Stream acaban en `playlist.m3u8`: si se usara el
    // nombre, los ocho vídeos compartirían etiqueta y no se podrían comparar.
    const languages = idDelVideo('https://vz-fc5a9efc-2a2.b-cdn.net/a05bea53-6612-4e70-97b1-6fb909a74738/playlist.m3u8')
    const finance = idDelVideo('https://vz-fc5a9efc-2a2.b-cdn.net/95f8113a-6260-4dae-982d-2cf3188c2b44/playlist.m3u8')
    expect(languages).toBe('a05bea53-6612-4e70-97b1-6fb909a74738')
    expect(finance).not.toBe(languages)
  })

  it('los MP4 por resolución de Stream sí se distinguen por el nombre', () => {
    expect(idDelVideo('https://vz-fc5a9efc-2a2.b-cdn.net/95f8113a/play_720p.mp4')).toBe('play_720p.mp4')
  })

  it('no revienta sin URL', () => {
    expect(idDelVideo('')).toBe('sin-video')
    expect(idDelVideo(undefined)).toBe('sin-video')
  })
})

describe('segundosBuffereados', () => {
  const rangos = (pares) => ({
    length: pares.length,
    start: (i) => pares[i][0],
    end: (i) => pares[i][1],
  })

  it('suma todos los tramos bufferizados', () => {
    expect(segundosBuffereados({ buffered: rangos([[0, 12.5]]) })).toBe(12.5)
    expect(segundosBuffereados({ buffered: rangos([[0, 5], [20, 26]]) })).toBe(11)
  })

  it('sin buffer devuelve cero, que es el dato revelador', () => {
    // Un fallo tardío CON el buffer a cero significa que no estaba bajando
    // vídeo útil, por mucho que tardara.
    expect(segundosBuffereados({ buffered: rangos([]) })).toBe(0)
    expect(segundosBuffereados({})).toBe(0)
  })

  it('no revienta si el navegador prohíbe leer buffered', () => {
    const hostil = { get buffered() { throw new Error('InvalidStateError') } }
    expect(segundosBuffereados(hostil)).toBeNull()
  })
})

describe('planDeRecuperacionHls', () => {
  it('reanuda la carga tras un fallo de red, esperando cada vez más', () => {
    /* Las esperas son cortas a propósito: para cuando hls.js declara el fatal,
       el visitante ya lleva medio minuto mirando un fotograma quieto. */
    // El caso de FUNNELS-CY: `fragLoadTimeOut` en Android, red que se va y
    // vuelve. hls.js ya se rindió; reanudar es cosa nuestra.
    expect(planDeRecuperacionHls('networkError', { red: 0 }))
      .toEqual({ accion: 'reanudar-carga', esperaMs: 1000 })
    expect(planDeRecuperacionHls('networkError', { red: 1 }))
      .toEqual({ accion: 'reanudar-carga', esperaMs: 2000 })
    expect(planDeRecuperacionHls('networkError', { red: 2 }))
      .toEqual({ accion: 'reanudar-carga', esperaMs: 4000 })
  })

  it('al cuarto fallo de red se rinde, en vez de alargar la espera', () => {
    const plan = planDeRecuperacionHls('networkError', { red: 3 })
    expect(plan.accion).toBe('rendirse')
    expect(plan.motivo).toBe('reintentos agotados')
  })

  it('en el segundo fallo de medios cambia el códec de audio', () => {
    // Receta del propio hls.js para los MP4 con la pista de audio separada,
    // que es justo lo que genera Bunny ahora.
    expect(planDeRecuperacionHls('mediaError', { media: 0 }))
      .toEqual({ accion: 'recuperar-media', cambiarCodecDeAudio: false })
    expect(planDeRecuperacionHls('mediaError', { media: 1 }))
      .toEqual({ accion: 'recuperar-media', cambiarCodecDeAudio: true })
    expect(planDeRecuperacionHls('mediaError', { media: 2 }).accion).toBe('rendirse')
  })

  it('los fallos sin recuperación conocida no se reintentan', () => {
    expect(planDeRecuperacionHls('otherError')).toEqual({
      accion: 'rendirse', motivo: 'irrecuperable',
    })
    expect(planDeRecuperacionHls('keySystemError').accion).toBe('rendirse')
  })

  it('cuenta la red y los medios por separado', () => {
    // Agotar los reintentos de red no puede dejar sin recuperación a un fallo
    // de medios posterior, que se arregla de otra manera.
    expect(planDeRecuperacionHls('mediaError', { red: 3, media: 0 }).accion)
      .toBe('recuperar-media')
  })
})

/* Contrato con hls.js. `planDeRecuperacionHls` compara `data.type` con cadenas
   literales para poder ser una función pura; eso solo vale mientras esas cadenas
   sigan siendo las de la librería. Si una subida de versión las cambia, el
   reproductor dejaría de recuperarse en silencio —los fatales caerían todos en
   'irrecuperable'— y nadie se enteraría hasta ver el pico en Sentry. Aquí sí se
   carga la librería de verdad, para que ese día falle el test y no la VSL. */
describe('planDeRecuperacionHls — contrato con hls.js', () => {
  it('las cadenas de ErrorTypes son las que el plan reconoce', () => {
    expect(Hls.ErrorTypes.NETWORK_ERROR).toBe('networkError')
    expect(Hls.ErrorTypes.MEDIA_ERROR).toBe('mediaError')
    expect(planDeRecuperacionHls(Hls.ErrorTypes.NETWORK_ERROR, { red: 0 }).accion)
      .toBe('reanudar-carga')
    expect(planDeRecuperacionHls(Hls.ErrorTypes.MEDIA_ERROR, { media: 0 }).accion)
      .toBe('recuperar-media')
  })

  it('los métodos de recuperación que invocamos siguen existiendo', () => {
    for (const metodo of ['startLoad', 'recoverMediaError', 'swapAudioCodec']) {
      expect(typeof Hls.prototype[metodo]).toBe('function')
    }
  })
})
