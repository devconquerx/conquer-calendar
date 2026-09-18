import { useEffect, useRef, useState, useCallback } from 'react'
import 'plyr/dist/plyr.css'
// El sprite de iconos del reproductor, servido por nosotros. Por defecto Plyr
// se lo pide por XHR a cdn.plyr.io en CADA carga de la página de vídeo: cuando
// esa petición se bloquea —bloqueadores, navegadores embebidos de las apps, red
// mala— lanza un error crudo ("Error: 0" en Sentry) y los controles se quedan
// sin iconos. Vite lo copia a /static/assets con su hash.
// (copiado de plyr/dist/plyr.svg — al subir de versión de Plyr, refréscalo)
import spriteDeIconos from '../../assets/vendor/plyr-3.8.4.svg?url'
import UnmuteOverlay from './UnmuteOverlay'
import ReturningOverlay from './ReturningOverlay'
import { useRouter } from '../../lib/router'
import { importarConReintento } from '../../lib/lazyConReintento'

const STORAGE_KEY = 'vsl_progress'
const LEGACY_STORAGE_KEY = 'videolitics'

/* Qué fracción de las reproducciones correctas se reporta a Sentry.
   Los fallos se mandan todos —son pocos y cada uno importa— pero los aciertos
   son ~4.500 al día si esto acaba en todos los funnels, y Sentry cobra por
   evento. Con una de cada cuatro sobra para calcular tasas por navegador, que
   es para lo único que sirve el dato. Subir a 1 mientras el piloto esté en un
   solo funnel es perfectamente asumible. */
const MUESTREO_ARRANQUE = 0.25

/* Qué motor de medios reportó el fallo, deducido del texto del MediaError.
   Hace falta porque el cubo de errores mezcla dos poblaciones distintas y en
   Sentry no había forma de separarlas: los mensajes con forma de Chromium
   ("PipelineStatus::…", "MEDIA_ELEMENT_ERROR: …", "DEMUXER_ERROR_…") aparecen
   incluso en eventos que dicen venir de un iPhone —user-agent falseado, casi
   siempre rastreadores desde centros de datos—, mientras que WebKit de verdad
   deja el mensaje vacío. Va como etiqueta, no como dato suelto, para poder
   filtrarlo y contarlo. */
export function motorDelFallo(detalle) {
  if (!detalle) return 'webkit-o-sin-mensaje'
  if (/PipelineStatus|DEMUXER_ERROR|MEDIA_ELEMENT_ERROR|FFmpeg/i.test(detalle)) return 'chromium'
  return 'otro'
}

/* Cuánto aguantó antes de fallar, en tramos.
   Es la medida que distingue las dos explicaciones posibles del
   SRC_NOT_SUPPORTED, y la única que funciona en todos los navegadores: el
   `transferSize` del Resource Timing vendría a 0 porque el CDN sirve el vídeo
   sin cabecera `Timing-Allow-Origin`.

   Fallar en el primer segundo significa que el navegador rechazó la fuente sin
   llegar a descargar vídeo (códec no admitido). Fallar al cabo de decenas de
   segundos significa lo contrario: estuvo tragando datos hasta rendirse, que es
   lo que se sospecha del navegador embebido de TikTok, del que se dice que no
   respeta las peticiones por rangos y se descarga el fichero entero antes de
   empezar. Con un vídeo de 400 MB eso no termina nunca. */
export function tramoDeEspera(ms) {
  if (ms == null) return 'desconocido'
  if (ms < 1000) return '<1s'
  if (ms < 5000) return '1-5s'
  if (ms < 15000) return '5-15s'
  if (ms < 45000) return '15-45s'
  return '>45s'
}

/* Nombre del fichero de vídeo, para poder contar fallos POR VÍDEO.
   Sentry agrupa estos errores por su mensaje, así que los siete vídeos de las
   distintas marcas y regiones caen en el mismo cubo; y el `transaction` no vale
   para separarlos porque la misma página llega con y sin barra final y con o
   sin prefijo de marca, repartiendo un mismo vídeo en cuatro filas. Con el
   nombre del fichero como etiqueta se puede preguntar lo que hasta ahora no se
   podía: si el máster de 1,88 GB falla más que los de 350 MB.
   Se descodifica el %20 porque alguno lleva espacios en el nombre. */
export function idDelVideo(url) {
  if (!url) return 'sin-video'
  try {
    const partes = new URL(url, 'https://x.invalid').pathname.split('/').filter(Boolean)
    const nombre = decodeURIComponent(partes.pop() || '')
    // En HLS el fichero SIEMPRE se llama `playlist.m3u8`, así que el nombre no
    // distingue un vídeo de otro: los ocho darían la misma etiqueta y la
    // comparación por vídeo —el motivo de existir de esto— se perdería justo en
    // el formato que queremos medir. Ahí identifica la carpeta, que es el id
    // del vídeo en Bunny.
    if (/\.m3u8$/i.test(nombre)) {
      const carpeta = decodeURIComponent(partes.pop() || '')
      return (carpeta || nombre || 'sin-video').slice(0, 80)
    }
    return (nombre || 'sin-video').slice(0, 80)
  } catch {
    return 'ilegible'
  }
}

/* Cuántas veces se intenta resucitar a hls.js y cuánto se espera entre intentos.
   La espera crece para no machacar una red que sigue sin estar, pero es corta a
   propósito: cuando llegamos aquí el visitante YA lleva medio minuto esperando
   —hls.js reintenta el fragmento seis veces con espera creciente antes de darlo
   por fatal, 33 segundos medidos en el e2e— y sumarle otros ocho es perderlo.
   Las esperas largas de la primera versión se cambiaron al ver en el e2e que la
   red volvía a los 6 s y el vídeo no revivía hasta los 13,7 s: siete segundos
   de fotograma congelado con la conexión ya buena. Por eso, además, el evento
   `online` adelanta el reintento pendiente en vez de esperar a que venza. */
const ESPERAS_DE_RED_MS = [1000, 2000, 4000]
const MAX_REINTENTOS_DE_MEDIA = 2

/* Qué hacer cuando hls.js se declara vencido.

   El detalle que hace falta conocer: los errores `fatal` de hls.js NO son el
   final del camino, son la librería avisando de que ha agotado SUS reintentos
   internos (cuatro por timeout de fragmento) y ha llamado a `stopLoad()`. La
   reanudación tiene que pedirla quien la usa. Sin eso, un `fragLoadTimeOut` en
   una red móvil mala deja el vídeo congelado para siempre aunque la cobertura
   vuelva un segundo después: era el 100% de FUNNELS-CY, 259 fallos en siete
   días y subiendo, casi todos Android en LATAM.

   Los `tipo` son las cadenas de `Hls.ErrorTypes`, comparadas por valor para que
   esto sea una función pura y no haya que cargar la librería para probarla.
   Las acciones son las del patrón que documenta el propio hls.js: reanudar la
   carga en los fallos de red, recuperar el buffer en los de medios —la segunda
   vez cambiando el códec de audio, que es su receta para los MP4 con la pista
   separada— y rendirse en lo demás, que no tiene recuperación conocida. */
export function planDeRecuperacionHls(tipo, intentos = {}) {
  const red = intentos.red || 0
  const media = intentos.media || 0
  if (tipo === 'networkError') {
    if (red >= ESPERAS_DE_RED_MS.length) return { accion: 'rendirse', motivo: 'reintentos agotados' }
    return { accion: 'reanudar-carga', esperaMs: ESPERAS_DE_RED_MS[red] }
  }
  if (tipo === 'mediaError') {
    if (media >= MAX_REINTENTOS_DE_MEDIA) return { accion: 'rendirse', motivo: 'reintentos agotados' }
    return { accion: 'recuperar-media', cambiarCodecDeAudio: media >= 1 }
  }
  return { accion: 'rendirse', motivo: 'irrecuperable' }
}

/* Segundos de vídeo que llegaron a bufferearse. Complementa lo anterior: si el
   fallo llega tarde PERO con el buffer vacío, no estaba descargando vídeo útil. */
export function segundosBuffereados(media) {
  try {
    const b = media?.buffered
    if (!b || !b.length) return 0
    let total = 0
    for (let i = 0; i < b.length; i += 1) total += b.end(i) - b.start(i)
    return Math.round(total * 10) / 10
  } catch {
    return null
  }
}

function readStoredState(storageKey, videoUrl) {
  try {
    const data = JSON.parse(localStorage.getItem(storageKey) || '{}')
    if (data.video_url === videoUrl) return data
  } catch {}
  return null
}

function getStoredProgress(videoUrl) {
  const current = readStoredState(STORAGE_KEY, videoUrl)
  if (current) return current

  const legacy = readStoredState(LEGACY_STORAGE_KEY, videoUrl)
  if (legacy) {
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(legacy))
    } catch {}
    return legacy
  }

  return null
}

function storeProgress(videoUrl, updates) {
  try {
    const current = getStoredProgress(videoUrl) || {
      time: 0,
      progress_percent: 0,
      visit_number: 0,
      unmuted: false,
      is_returning: false,
      progress_latest_visit: 0,
      video_url: videoUrl,
    }
    const nextValue = { ...current, ...updates, video_url: videoUrl }
    localStorage.setItem(STORAGE_KEY, JSON.stringify(nextValue))
    localStorage.setItem(LEGACY_STORAGE_KEY, JSON.stringify(nextValue))
  } catch {}
}

export default function VideoPlayer({ videoUrls, buttonPercent = 75, showControls = false, onAgendarClick, onShowButton, onProgress, theme }) {
  const videoRef = useRef(null)
  const playerRef = useRef(null)
  const [showUnmute, setShowUnmute] = useState(false)
  const [showReturning, setShowReturning] = useState(false)
  const [storedData, setStoredData] = useState(null)
  const buttonShownRef = useRef(false)
  const milestonesReportedRef = useRef(new Set())
  // Momento en que se le da la fuente al <video>, para medir cuánto tardó en
  // fallar. Ver `tramoDeEspera`.
  const inicioCargaRef = useRef(null)
  // El evento de arranque se manda una sola vez por montaje: `playing` se
  // dispara también al reanudar tras una pausa o un seek.
  const arranqueReportadoRef = useRef(false)
  // Cortes (buffering) durante el primer minuto. Ver `reportarCortes`.
  const cortesRef = useRef(0)
  const esperaCortesRef = useRef(0)
  const inicioCorteRef = useRef(null)
  const resumenCortesRef = useRef(false)

  // Se evalúa UNA vez, al montar, y de ahí que viva en un ref: lo que importa es
  // cómo se llegó a esta página, no lo que pase después. `useRouter()` devuelve
  // null fuera de la SPA (navegación con recarga completa), que es justo el caso
  // en el que tampoco hay activación de usuario.
  const router = useRouter()
  const vinoDeNavegacionRef = useRef(!!router?.hasNavigated?.())

  const videoUrl = videoUrls?.[0] || ''

  useEffect(() => {
    if (!videoRef.current || !videoUrl) return

    const stored = getStoredProgress(videoUrl)
    const isReturning = stored && stored.progress_percent > 0

    // Arrancar CON sonido solo si se llegó aquí navegando dentro de la SPA (el
    // submit de la landing): esa navegación no recarga el documento, así que el
    // navegador conserva la activación de usuario y permite el audio. Si se entró
    // directo o se recargó no la hay, y hay que pedir el clic con el overlay.
    // Y solo para visitantes nuevos: si hay progreso manda el overlay de reanudar.
    const tryUnmuted = vinoDeNavegacionRef.current && !isReturning

    if (isReturning) {
      setStoredData(stored)
      setShowReturning(true)
      storeProgress(videoUrl, {
        visit_number: (stored.visit_number || 0) + 1,
        is_returning: true,
      })

      // Show button for ALL returning users (same as original)
      buttonShownRef.current = true
      if (onShowButton) onShowButton()
    } else {
      storeProgress(videoUrl, { visit_number: 1 })
      // Con autoplay con sonido no mostramos el overlay de unmute; solo cae a él
      // si el navegador acaba bloqueando la reproducción con audio (más abajo).
      if (!tryUnmuted) setShowUnmute(true)
    }

    // Asignar `src` arranca ya la carga del recurso, así que este es el momento
    // desde el que se cuenta lo que tarde en fallar.
    inicioCargaRef.current = performance.now()
    const esHls = /\.m3u8(\?|$)/i.test(videoUrl)
    /* ¿Reproduce este navegador el HLS con hls.js o se lo dejamos a él?

       NO se puede preguntar con `canPlayType('application/vnd.apple.mpegurl')`,
       que es lo que se hacía antes: Chrome devuelve 'maybe' a casi cualquier
       cosa que le preguntes —también a `video/mp4` pelado—, así que ese check
       daba SIEMPRE positivo y hls.js no llegaba a cargarse nunca fuera de
       Firefox. Chrome se quedaba con el `.m3u8` en las manos, y que funcionara
       o no dependía de hasta dónde llegue su HLS nativo, que es incompleto: con
       las VSL viejas colaba (Bunny las codificó con el audio dentro de cada
       calidad), pero en cuanto una trae el audio como pista aparte
       —`EXT-X-MEDIA:TYPE=AUDIO`, que es lo que genera Bunny ahora— el vídeo se
       queda en negro cargando para siempre, sin lanzar ni un error.

       Se mira si hay MediaSource, que es lo que de verdad necesita hls.js
       (`Hls.isSupported()` comprueba justo esto). Donde no lo hay —Safari de
       iPhone y iPad— se cae al reproductor del sistema, que es además el mejor
       ahí: HLS es de Apple y lo entiende entero. */
    const MSE = typeof window !== 'undefined'
      && (window.MediaSource || window.ManagedMediaSource)
    const usaHlsJs = esHls && !!MSE && typeof MSE.isTypeSupported === 'function'
      && MSE.isTypeSupported('video/mp4; codecs="avc1.42E01E,mp4a.40.2"')
    /* El `src` NO se asigna cuando va a encargarse hls.js.
       Antes se asignaba siempre, y en los navegadores sin HLS nativo el <video>
       lanzaba un SRC_NOT_SUPPORTED en cuanto lo intentaba, justo antes de que
       hls.js tomara el control. El vídeo acababa reproduciéndose —de ahí los
       "se recuperó tras el error" que llegaban de Firefox y Edge— pero cada
       visita dejaba un fallo falso en Sentry, contaminando exactamente la
       métrica que este piloto quiere medir. */
    if (!usaHlsJs) videoRef.current.src = videoUrl
    videoRef.current.muted = true

    /* La carga de hls.js va diferida por dos razones: este módulo también se
       compila para el SSR, donde no debe entrar; y quien no reproduzca HLS
       (todas las VSL en MP4) no se descarga una librería que no va a usar.
       Mismo criterio que Plyr, aquí abajo.

       Si el import falla o la librería se declara no soportada, se le pasa el
       `.m3u8` al navegador: es peor que hls.js, pero es mejor que un vídeo que
       no arranca. */
    let hls = null
    // Los intentos se cuentan por montaje del reproductor, no por fallo: tres
    // baches de red seguidos en la misma reproducción son la señal de que esa
    // conexión no da para el vídeo, y seguir reintentando solo alarga la espera.
    const intentosDeHls = { red: 0, media: 0 }
    // Deshace el reintento pendiente (temporizador + escucha de `online`).
    let cancelarReintento = null
    if (usaHlsJs) {
      importarConReintento(() => import('hls.js')).then(({ default: Hls }) => {
        if (!videoRef.current) return
        // Se descarta a mano para que caiga en el `.catch()` de abajo: la
        // librería cargó pero se declara inservible, y acaba igual que si no
        // hubiera cargado. Mismo desenlace, mismo informe.
        if (!Hls.isSupported()) throw new Error('Hls.isSupported() === false')
        /* `__CQX_HLS_CONFIG__` es un resquicio para las pruebas, y no lo define
           nadie en producción. Existe porque hls.js reintenta un fragmento seis
           veces con espera creciente antes de rendirse: provocar un fallo fatal
           de verdad cuesta 33 segundos, y un e2e que tarde eso no lo ejecuta
           nadie. El test baja los reintentos y el mismo fallo llega en medio
           segundo. La alternativa era no probar la recuperación en navegador. */
        hls = new Hls({ enableWorker: true, ...(window.__CQX_HLS_CONFIG__ || {}) })
        hls.loadSource(videoUrl)
        hls.attachMedia(videoRef.current)
        // Los fallos de hls.js NO llegan al `error` del <video>, así que sin
        // esto Firefox fallaría sin dejar rastro en Sentry. De los transitorios
        // se recupera la librería sola; de los fatales, no: los da por perdidos
        // y deja de cargar, y de ahí en adelante mandamos nosotros. Ver
        // `planDeRecuperacionHls`.
        hls.on(Hls.Events.ERROR, (_evt, data) => {
          if (!data?.fatal) return
          const plan = planDeRecuperacionHls(data.type, intentosDeHls)

          if (plan.accion === 'reanudar-carga') {
            intentosDeHls.red += 1
            console.warn('[VSL] hls.js fatal, reanudando carga', data.details, plan)
            /* La espera es un tope, no una cita: si el navegador avisa de que ha
               vuelto la red antes de que venza, se reanuda ya. El caso típico
               —salir del metro— devuelve la conexión de golpe, y sin esto el
               vídeo seguiría congelado hasta agotar el temporizador.
               `cancelarReintento` se guarda para poder deshacer las dos cosas al
               desmontar: si no, el `startLoad()` caería sobre una instancia ya
               destruida y el listener quedaría suelto. */
            const reanudar = () => {
              cancelarReintento?.()
              try { hls?.startLoad() } catch { /* instancia ya destruida */ }
            }
            const temporizador = setTimeout(reanudar, plan.esperaMs)
            window.addEventListener('online', reanudar)
            cancelarReintento = () => {
              clearTimeout(temporizador)
              window.removeEventListener('online', reanudar)
              cancelarReintento = null
            }
            return
          }

          if (plan.accion === 'recuperar-media') {
            intentosDeHls.media += 1
            console.warn('[VSL] hls.js fatal, recuperando el buffer', data.details, plan)
            try {
              if (plan.cambiarCodecDeAudio) hls.swapAudioCodec()
              hls.recoverMediaError()
            } catch { /* instancia ya destruida */ }
            return
          }

          /* Aquí sí se acabó. Solo este caso llega a Sentry: reportar también
             los fatales de los que nos recuperamos devolvería el ruido que
             motivó esto —259 eventos que en su mayoría eran baches de red de
             dos segundos— y taparía justo lo que queremos contar, que es la
             gente que se quedó sin vídeo. Los intentos van en el contexto para
             saber si nos rendimos pronto o después de pelearlo. */
          import('@sentry/react')
            .then(({ captureMessage }) => {
              captureMessage(`[VSL] hls.js falló: ${data.type}`, {
                level: 'error',
                tags: {
                  motivo_video: `hls-${data.type}`,
                  motor_video: 'hls.js',
                  id_video: idDelVideo(videoUrl),
                  espera_video: tramoDeEspera(
                    inicioCargaRef.current == null
                      ? null
                      : Math.round(performance.now() - inicioCargaRef.current)
                  ),
                },
                extra: {
                  tipo: data.type,
                  detalle: data.details,
                  codigoHttp: data.response?.code ?? null,
                  url: (data.url || '').slice(-60),
                  motivoDeRendirse: plan.motivo,
                  intentosDeRed: intentosDeHls.red,
                  intentosDeMedia: intentosDeHls.media,
                  // Con qué calidad se estaba peleando. Si los `fragLoadTimeOut`
                  // se concentran en los niveles altos, el arreglo siguiente es
                  // capar la calidad en redes lentas, no reintentar más.
                  nivel: hls.currentLevel,
                  niveles: hls.levels?.length ?? null,
                },
              })
            })
            .catch(() => {})
        })
      }).catch((error) => {
        /* Ni con el reintento se pudo bajar hls.js (red, bloqueador, chunk que
           ya no existe tras un despliegue…). Se le pasa el `.m3u8` al navegador
           porque es lo único que queda por probar, pero sin hacerse ilusiones:
           aquí estamos en la rama con MediaSource, o sea Chrome, Firefox o Edge,
           y ninguno reproduce HLS.

           Lo que cambia es el informe. Antes esto se manifestaba como un
           SRC_NOT_SUPPORTED del <video> —el grueso de FUNNELS-77: ~59 eventos
           semanales con `motor_video: chromium`, achacados al vídeo o al códec
           cuando el vídeo estaba perfectamente— y la causa de verdad, que la
           librería no llegó a cargarse, no aparecía por ningún lado. Se reporta
           aquí, con su motivo, y el error del <video> que venga después ya es
           una consecuencia conocida. */
        if (videoRef.current) videoRef.current.src = videoUrl
        import('@sentry/react')
          .then(({ captureMessage }) => {
            captureMessage('[VSL] no se pudo cargar hls.js', {
              level: 'error',
              tags: {
                motivo_video: 'hls-no-cargado',
                motor_video: 'sin-hls-js',
                id_video: idDelVideo(videoUrl),
                espera_video: tramoDeEspera(
                  inicioCargaRef.current == null
                    ? null
                    : Math.round(performance.now() - inicioCargaRef.current)
                ),
              },
              extra: { detalle: String(error?.message || error).slice(0, 300) },
            })
          })
          .catch(() => {})
      })
    }

    /* Errores del reproductor.

       Vive aquí, y no dentro del `.then()` de Plyr, porque el <video> falla
       ANTES de que Plyr llegue: el manejador se registraba al montar el
       reproductor y para entonces el evento ya había pasado, sin nadie
       escuchando. Comprobado: retrasando su chunk tres segundos, el fallo no se
       reporta NUNCA. Y eso sesga justo lo que se quiere medir, porque Plyr
       tarda más precisamente en los móviles lentos y las redes malas, que es
       donde el vídeo falla. Se veía como un e2e que fallaba de vez en cuando.

       Plyr emite además su propio CustomEvent 'error', que burbujea hasta
       window y acababa en Sentry como "<unknown>", sin mensaje ni forma de
       saber qué pasó (FUNNELS-69, ~100 al día, el 80% desde el navegador de
       TikTok en iPhone). Ese se sigue atajando abajo, para cortarle la
       propagación; el informe con el motivo lo hace esta función. */
    let falloYaReportado = false
    const reportarFallo = () => {
      // Un mismo fallo llega por dos vías —el <video> y el CustomEvent de
      // Plyr— y es un solo suceso: se cuenta una vez por montaje.
      if (falloYaReportado) return
      falloYaReportado = true
      const media = videoRef.current
      const fallo = media?.error
      const MOTIVOS = { 1: 'ABORTED', 2: 'NETWORK', 3: 'DECODE', 4: 'SRC_NOT_SUPPORTED' }
      const detalle = fallo?.message || ''
      const esperaMs = inicioCargaRef.current == null
        ? null
        : Math.round(performance.now() - inicioCargaRef.current)
      const contexto = {
        motivo: MOTIVOS[fallo?.code] || 'sin MediaError',
        codigo: fallo?.code ?? null,
        detalle,
        silenciado: !!media?.muted,
        pausado: !!media?.paused,
        segundo: Math.round(media?.currentTime || 0),
        readyState: media?.readyState ?? null,
        networkState: media?.networkState ?? null,
        pantallaCompleta: !!(document.fullscreenElement || document.webkitFullscreenElement || media?.webkitDisplayingFullscreen),
        fuente: (media?.currentSrc || '').slice(-60),
        esperaMs,
        segundosBuffereados: segundosBuffereados(media),
        // Sólo lo tiene WebKit, que es justo el motor bajo sospecha. Cuando
        // está, dice los bytes que llegó a decodificar de verdad.
        bytesDecodificados: media?.webkitVideoDecodedByteCount ?? null,
      }

      /* Historial de este visitante con este vídeo. Si los fallos se
         concentran en los mismos dispositivos el problema es del dispositivo;
         si están repartidos, es del fichero. El contador se guarda junto al
         progreso, que ya vive en localStorage. */
      const previo = getStoredProgress(videoUrl) || {}
      const fallosPrevios = previo.fallos || 0
      contexto.falloNumero = fallosPrevios + 1
      contexto.visitaNumero = previo.visit_number || 1
      contexto.esRecurrente = !!previo.is_returning
      storeProgress(videoUrl, { fallos: contexto.falloNumero })
      console.warn('[VSL] error del reproductor', contexto)
      // Import perezoso: este módulo también se compila para el SSR, donde
      // @sentry/react no debe cargarse.
      import('@sentry/react')
        .then(({ captureMessage }) => {
          captureMessage(`[VSL] error del reproductor: ${contexto.motivo}`, {
            level: 'error',
            // Como etiquetas y no sólo como datos sueltos: `extra` no se puede
            // agregar en Sentry, y la pregunta que hay que responder ("¿falla
            // al instante o después de tragar datos?") es precisamente un
            // recuento por tramos.
            tags: {
              motivo_video: contexto.motivo,
              motor_video: motorDelFallo(detalle),
              espera_video: tramoDeEspera(esperaMs),
              id_video: idDelVideo(videoUrl),
            },
            extra: contexto,
          })
        })
        .catch(() => {})

      /* ¿Se recupera solo? Un rectángulo negro definitivo y uno que arranca
         tres segundos tarde cuentan hoy exactamente igual, y el daño real es
         muy distinto. Si el vídeo acaba reproduciéndose se manda un segundo
         aviso —sólo en ese caso, que es el minoritario— con lo que tardó en
         recuperarse. Errores partido por recuperaciones da la proporción de
         fallos que de verdad dejan al visitante sin vídeo.
         `once` para no encadenar avisos si el vídeo va y viene. */
      media?.addEventListener?.('playing', () => {
        const tardanza = esperaMs == null
          ? null
          : Math.round(performance.now() - inicioCargaRef.current)
        import('@sentry/react')
          .then(({ captureMessage }) => {
            captureMessage('[VSL] el reproductor se recuperó tras el error', {
              level: 'info',
              tags: {
                motivo_video: contexto.motivo,
                id_video: idDelVideo(videoUrl),
                espera_video: tramoDeEspera(tardanza),
              },
              extra: { ...contexto, recuperadoEnMs: tardanza },
            })
          })
          .catch(() => {})
      }, { once: true })
    }

    // El <video> existe desde el primer render, así que a partir de aquí ya no
    // hay ventana ciega: falle cuando falle, hay alguien escuchando.
    videoRef.current.addEventListener('error', reportarFallo)

    // Modo debug (?debug=1): controles completos del reproductor (barra de
    // progreso/seek, tiempos, etc.) para poder navegar el vídeo durante pruebas.
    const isDebug = new URLSearchParams(window.location.search).get('debug') === '1'

    /* Barra completa para quien la pida por configuración (`video.showControls`).
       Una VSL de 15 minutos la esconde a propósito: sin barra de progreso nadie
       adelanta, y el CTA aparece cuando toca. Pero hay vídeos que no son una VSL
       —la masterclass de Conquer AI dura tres horas— y ahí quitarle a la gente el
       poder pausar o ver cuánto queda es hostil, no persuasivo. OJO: con barra de
       progreso el visitante puede arrastrar hasta el final y hacer aparecer el
       CTA sin ver el vídeo.

       Sin los saltos de ±10s: con la barra de progreso delante son redundantes,
       y en un vídeo de tres horas saltar de diez en diez no lleva a ninguna
       parte. En depuración sí se dejan, que ahí el objetivo es justo moverse por
       el vídeo a mano. */
    const controles = isDebug
      ? ['play-large', 'restart', 'rewind', 'play', 'fast-forward', 'progress',
         'current-time', 'duration', 'mute', 'volume', 'settings', 'fullscreen']
      : showControls
        ? ['play-large', 'restart', 'play', 'progress', 'current-time',
           'duration', 'mute', 'volume', 'settings', 'fullscreen']
        : ['play', 'mute', 'volume', 'fullscreen']

    // Plyr toca `document` al importarse, así que lo cargamos dinámicamente (solo
    // en cliente, dentro del efecto) para que este módulo sea SSR-safe. El setup
    // síncrono de arriba (overlays, src) ya corrió; solo se difiere el reproductor.
    let player = null
    let cancelled = false

    /* Con reintento, igual que hls.js: este import es el que más falla de todo
       el funnel —`plyr-*.js` encabeza FUNNELS-47, y FUNNELS-5E es el mismo
       fallo contado por Safari, otros ~54 semanales, todos en páginas de
       vídeo— y se caía a la primera porque el navegador memoriza el fallo del
       import y no vuelve a pedir nada. El chunk existe: lo delata que el mismo
       hash se sirva bien desde los otros dominios. Es red, no despliegue. */
    importarConReintento(() => import('plyr')).then(({ default: Plyr }) => {
      if (cancelled || !videoRef.current) return

      player = new Plyr(videoRef.current, {
        hideControls: false,
        autoplay: true,
        muted: true,
        iconUrl: spriteDeIconos,
        controls: controles,
      })

      playerRef.current = player

      // Ensure muted state after Plyr wraps the element
      player.muted = true

      /* Cortes durante la reproducción.
         Es la medida que dice si HLS mejora la EXPERIENCIA, no solo si el vídeo
         arranca: un MP4 en conexión mala arranca igual, pero luego se para cada
         pocos segundos. Se cuentan los `waiting` y se acumula cuánto tiempo pasó
         el visitante esperando; el resumen se manda una sola vez, al primer
         minuto reproducido.
         Al minuto y no al final porque casi nadie llega al final de una VSL de
         16 minutos: si se esperara al `ended`, el dato se perdería justo para
         quien peor lo pasó. */
      const media = videoRef.current
      media?.addEventListener?.('waiting', () => {
        cortesRef.current += 1
        if (inicioCorteRef.current == null) inicioCorteRef.current = performance.now()
      })
      media?.addEventListener?.('playing', () => {
        if (inicioCorteRef.current != null) {
          esperaCortesRef.current += performance.now() - inicioCorteRef.current
          inicioCorteRef.current = null
        }
      })

      const reportarCortes = () => {
        if (resumenCortesRef.current) return
        resumenCortesRef.current = true
        if (Math.random() > MUESTREO_ARRANQUE) return
        const cortes = cortesRef.current
        const esperaS = Math.round(esperaCortesRef.current / 100) / 10
        import('@sentry/react')
          .then(({ captureMessage }) => {
            captureMessage('[VSL] primer minuto reproducido', {
              level: 'info',
              tags: {
                id_video: idDelVideo(videoUrl),
                entrega_video: esHls ? (usaHlsJs ? 'hls-js' : 'hls-nativo') : 'mp4',
                // En tramos porque lo que importa es "¿se le cortó mucho?",
                // no el número exacto.
                cortes_video: cortes === 0 ? 'ninguno' : cortes <= 2 ? '1-2' : cortes <= 5 ? '3-5' : '6+',
              },
              extra: {
                cortes,
                segundosEsperando: esperaS,
                resolucion: media?.videoHeight ? `${media.videoHeight}p` : null,
                muestreo: MUESTREO_ARRANQUE,
              },
            })
          })
          .catch(() => {})
      }

      player.on('timeupdate', () => {
        if (!player.duration) return
        if (player.currentTime >= 60) reportarCortes()
        const percent = (player.currentTime / player.duration) * 100

        // Only update progress_percent if higher (never decrease on replay/reload)
        const current = getStoredProgress(videoUrl)
        const maxPercent = current && current.progress_percent > percent
          ? current.progress_percent
          : percent

        const updates = {
          time: player.currentTime,
          progress_percent: maxPercent,
          unmuted: !player.muted,
        }

        // Only track progress_latest_visit when unmuted (user is actively watching)
        if (!player.muted) {
          updates.progress_latest_visit = player.currentTime
        }

        storeProgress(videoUrl, updates)

        if (percent >= buttonPercent && !buttonShownRef.current) {
          buttonShownRef.current = true
          if (onShowButton) onShowButton()
        }

        // Report progress every 10% (for ActiveCampaign / lead tracking)
        if (onProgress) {
          for (const p of [10, 20, 30, 40, 50, 60, 70, 80, 90, 100]) {
            if (maxPercent >= p && !milestonesReportedRef.current.has(`p${p}`)) {
              milestonesReportedRef.current.add(`p${p}`)
              onProgress(p)
            }
          }
        }

      })

      player.on('ended', () => {
        if (onAgendarClick) onAgendarClick()
      })

      /* Reproducciones que SÍ arrancan.
         Hasta ahora solo se registraban los fallos, así que se contaban sin
         denominador: "150 errores al día" no dice nada si no se sabe sobre
         cuántas reproducciones. Con este evento se puede calcular la tasa real
         por navegador, por dispositivo y por vídeo —Sentry ya adjunta navegador,
         sistema y modelo por su cuenta—, que es lo único que dirá si servir HLS
         mejora o empeora.
         Se manda una sola vez por montaje, en el primer `playing`. */
      const reportarArranque = () => {
        if (arranqueReportadoRef.current) return
        arranqueReportadoRef.current = true
        if (Math.random() > MUESTREO_ARRANQUE) return
        const media = videoRef.current
        const ms = inicioCargaRef.current == null
          ? null
          : Math.round(performance.now() - inicioCargaRef.current)
        import('@sentry/react')
          .then(({ captureMessage }) => {
            captureMessage('[VSL] reproducción iniciada', {
              level: 'info',
              tags: {
                id_video: idDelVideo(videoUrl),
                entrega_video: esHls ? (usaHlsJs ? 'hls-js' : 'hls-nativo') : 'mp4',
                espera_video: tramoDeEspera(ms),
                resolucion_inicial: media?.videoHeight ? `${media.videoHeight}p` : 'desconocida',
              },
              extra: {
                arranqueMs: ms,
                ancho: media?.videoWidth ?? null,
                alto: media?.videoHeight ?? null,
                anchoElemento: Math.round(media?.getBoundingClientRect?.().width || 0),
                dpr: window.devicePixelRatio || 1,
                muestreo: MUESTREO_ARRANQUE,
              },
            })
          })
          .catch(() => {})
      }
      player.on('playing', reportarArranque)

      /* El CustomEvent de Plyr: se le corta la propagación para que el
         manejador global del navegador deje de reportarlo a ciegas, y se
         delega en el informe de arriba, que ya habrá salido si el <video>
         falló antes. */
      player.on('error', (evento) => {
        evento?.stopPropagation?.()
        reportarFallo()
      })

      if (tryUnmuted) {
        // Intento de autoplay CON sonido. Si el navegador lo bloquea (p.ej. carga
        // directa de la URL, sin gesto previo) volvemos al autoplay muted + overlay.
        player.muted = false
        const played = player.play()
        if (played && played.catch) {
          played.catch(() => {
            player.muted = true
            player.play()?.catch(() => {})
            setShowUnmute(true)
          })
        }
      } else {
        // Always autoplay muted — even with returning overlay showing
        player.play()?.catch(() => {})
      }
    })

    const video = videoRef.current

    return () => {
      cancelled = true
      // El <video> puede sobrevivir al efecto si cambia `videoUrl` sin
      // desmontar: sin esto se acumularía un manejador por cada pasada y el
      // mismo fallo se reportaría tantas veces como pasadas hubiera.
      video?.removeEventListener('error', reportarFallo)
      // Antes de destruir hls.js: un reintento pendiente llamaría a `startLoad()`
      // sobre la instancia ya destruida, y dejaría su listener puesto.
      cancelarReintento?.()
      // Antes que Plyr: hls.js mantiene sus propias peticiones y un worker, y si
      // no se destruye sigue bajando trozos de un vídeo que ya nadie mira.
      if (hls) hls.destroy()
      if (player) player.destroy()
    }
  }, [videoUrl])

  const handleUnmute = useCallback(() => {
    setShowUnmute(false)
    if (playerRef.current) {
      playerRef.current.muted = false
      playerRef.current.restart()
    }
  }, [])

  const handleContinue = useCallback(() => {
    setShowReturning(false)
    if (playerRef.current && storedData) {
      playerRef.current.muted = false
      playerRef.current.currentTime = storedData.progress_latest_visit || storedData.time
      playerRef.current.play()?.catch(() => {})
    }
  }, [storedData])

  const handleRestart = useCallback(() => {
    setShowReturning(false)
    if (playerRef.current) {
      playerRef.current.restart()
      playerRef.current.play()?.catch(() => {})
      playerRef.current.muted = false
    }
  }, [])

  if (!videoUrl) return null

  return (
    // Finance (hexboard): el player de producción no lleva esquinas redondeadas.
    <div className={`relative aspect-video bg-black overflow-hidden ${theme?.hexboard ? '' : 'rounded-lg'}`}>
      <video
        ref={videoRef}
        playsInline
        preload="auto"
        muted
        autoPlay
        className="w-full h-full"
      />

      {showUnmute && <UnmuteOverlay onUnmute={handleUnmute} theme={theme} />}
      {showReturning && (
        <ReturningOverlay onContinue={handleContinue} onRestart={handleRestart} theme={theme} />
      )}
    </div>
  )
}
