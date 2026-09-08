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

const STORAGE_KEY = 'vsl_progress'
const LEGACY_STORAGE_KEY = 'videolitics'

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
    const ruta = new URL(url, 'https://x.invalid').pathname
    return decodeURIComponent(ruta.split('/').pop() || 'sin-video').slice(0, 80)
  } catch {
    return 'ilegible'
  }
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

export default function VideoPlayer({ videoUrls, buttonPercent = 75, onAgendarClick, onShowButton, onProgress, theme }) {
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
    videoRef.current.src = videoUrl
    videoRef.current.muted = true

    // Modo debug (?debug=1): controles completos del reproductor (barra de
    // progreso/seek, tiempos, etc.) para poder navegar el vídeo durante pruebas.
    const isDebug = new URLSearchParams(window.location.search).get('debug') === '1'

    // Plyr toca `document` al importarse, así que lo cargamos dinámicamente (solo
    // en cliente, dentro del efecto) para que este módulo sea SSR-safe. El setup
    // síncrono de arriba (overlays, src) ya corrió; solo se difiere el reproductor.
    let player = null
    let cancelled = false

    import('plyr').then(({ default: Plyr }) => {
      if (cancelled || !videoRef.current) return

      player = new Plyr(videoRef.current, {
        hideControls: false,
        autoplay: true,
        muted: true,
        iconUrl: spriteDeIconos,
        controls: isDebug
          ? ['play-large', 'restart', 'rewind', 'play', 'fast-forward', 'progress', 'current-time', 'duration', 'mute', 'volume', 'settings', 'fullscreen']
          : ['play', 'mute', 'volume', 'fullscreen'],
      })

      playerRef.current = player

      // Ensure muted state after Plyr wraps the element
      player.muted = true

      player.on('timeupdate', () => {
        if (!player.duration) return
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

      /* Errores del reproductor.
         Plyr los emite como un CustomEvent 'error' que burbujea hasta window, y
         ahí el manejador global del navegador lo recoge: en Sentry llegaban como
         "<unknown>", sin mensaje ni forma de saber qué había pasado (FUNNELS-69,
         ~100 al día, el 80% desde el navegador de TikTok en iPhone).
         Se captura aquí, con el estado real del <video> —que es donde vive el
         motivo—, y se corta la propagación para que deje de reportarse a ciegas. */
      player.on('error', (evento) => {
        evento?.stopPropagation?.()
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

    return () => {
      cancelled = true
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
