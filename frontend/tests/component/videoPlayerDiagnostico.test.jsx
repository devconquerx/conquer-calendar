/**
 * Los datos que el reproductor adjunta cuando el vídeo falla.
 *
 * El cubo de errores de la VSL (FUNNELS-77) mezcla dos poblaciones —navegadores
 * reales y rastreadores con user-agent falseado— y no distingue entre las dos
 * explicaciones posibles del SRC_NOT_SUPPORTED: que el navegador rechace la
 * fuente de entrada, o que se pase medio minuto tragando datos hasta rendirse.
 * Estos tres datos son los que permiten separarlo en Sentry.
 */
import { describe, expect, it } from 'vitest'

import {
  idDelVideo, motorDelFallo, segundosBuffereados, tramoDeEspera,
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
