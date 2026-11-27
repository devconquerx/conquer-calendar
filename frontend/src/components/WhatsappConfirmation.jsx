import logoBlocks from '../assets/img/cb/logo-horizontal-negro.png'
import logoFinance from '../assets/img/finance/logo.svg'
import logoLanguages from '../assets/img/languages/logo.svg'

// Página de confirmación para los leads de un closer sin setter (LATAM): en vez
// de la confirmación de siempre se les pide confirmar la llamada por WhatsApp.
// El backend lo decide al reservar (funnels/autosetter.py) y Funnel.jsx lo pasa
// a esta etapa con `?confirmar=whatsapp`.

// Canal de WhatsApp de Respond.io, el mismo para todas las formaciones.
export const WHATSAPP_URL = 'https://wa.me/34602407862'

const MARCAS = {
  conquerblocks: {
    nombre: 'Conquer Blocks',
    logo: logoBlocks,
    fuente: "'Termina', sans-serif",
    pesoTitulo: 700,
    pesoTexto: 500,
    fondo: { background: '#F3F1EC' },
    regalo: { color: '#FF7A00' },
    boton: { background: '#FF7A00', borderRadius: 12 },
  },
  conquerfinance: {
    nombre: 'Conquer Finance',
    logo: logoFinance,
    fuente: "'Termina', sans-serif",
    pesoTitulo: 700,
    pesoTexto: 500,
    fondo: {
      backgroundColor: '#F2F1EC',
      backgroundImage:
        'linear-gradient(rgba(0,0,0,0.045) 1px, transparent 1px), linear-gradient(90deg, rgba(0,0,0,0.045) 1px, transparent 1px)',
      backgroundSize: '24px 24px',
    },
    regalo: {
      background: 'linear-gradient(90deg,#AED916,#3AC043)',
      WebkitBackgroundClip: 'text',
      backgroundClip: 'text',
      color: 'transparent',
    },
    boton: { background: 'linear-gradient(90deg,#AED916,#3AC043)', borderRadius: 12 },
  },
  conquerlanguages: {
    nombre: 'Conquer Languages',
    logo: logoLanguages,
    fuente: 'Inter, sans-serif',
    pesoTitulo: 800,
    pesoTexto: 400,
    fondo: {
      backgroundColor: '#FFFFFF',
      backgroundImage:
        'radial-gradient(circle at 100% 0%, rgba(112,179,196,0.16), transparent 32%), radial-gradient(circle at 0% 100%, rgba(112,179,196,0.20), transparent 30%), radial-gradient(circle at 15% 25%, rgba(112,179,196,0.07), transparent 35%)',
    },
    regalo: { color: '#4A86A0' },
    boton: { background: '#5A92AC', borderRadius: 999 },
  },
}

export function whatsappBrand(themeId) {
  return MARCAS[themeId] || null
}

export function isWhatsappRequested(search) {
  return new URLSearchParams(search || '').get('confirmar') === 'whatsapp'
}

// `?vista_previa=1`: la página se puede ver sin disparar el evento Schedule.
export function isVistaPrevia(search) {
  return new URLSearchParams(search || '').get('vista_previa') === '1'
}

const TAMANO = 'clamp(19px, 5.4vw, 58px)'

export default function WhatsappConfirmation({ theme }) {
  const m = MARCAS[theme?.id]
  if (!m) return null
  // Píxeles decorativos: los mismos de la landing de la marca (posiciones y SVG
  // del tema). Solo Blocks los tiene; Finance y Languages no llevan.
  const pixels = theme.assets?.pixels
  const decos = pixels?.deco ? theme.landing?.decoPixels || [] : []
  const decosMovil = pixels ? theme.landing?.decoPixelsMobile || [] : []
  return (
    <main
      style={{
        position: 'relative',
        overflow: 'hidden',
        minHeight: '100vh',
        boxSizing: 'border-box',
        padding: '40px 16px',
        fontFamily: m.fuente,
        color: '#141414',
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        ...m.fondo,
      }}
    >
      {decos.map((pos, i) => (
        <img
          key={i}
          src={i % 2 && pixels.deco2 ? pixels.deco2 : pixels.deco}
          alt=""
          aria-hidden="true"
          className={`hidden lg:block absolute w-[150px] opacity-20 pointer-events-none select-none ${pos}`}
        />
      ))}
      {decosMovil.map((p, i) => (
        <img
          key={`m${i}`}
          src={pixels[p.img]}
          alt=""
          aria-hidden="true"
          className={`lg:hidden absolute z-0 opacity-20 pointer-events-none select-none ${p.cls}`}
        />
      ))}

      <div
        style={{
          position: 'relative',
          width: '100%',
          maxWidth: 1100,
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          textAlign: 'center',
        }}
      >
        <img src={m.logo} alt={m.nombre} style={{ width: 'clamp(150px, 20vw, 280px)', height: 'auto' }} />
        <h1
          style={{
            margin: 'clamp(28px, 4vw, 52px) 0 0',
            fontWeight: m.pesoTitulo,
            fontSize: TAMANO,
            lineHeight: 1.12,
            letterSpacing: '-0.01em',
          }}
        >
          Tu llamada está agendada.
        </h1>
        <p
          style={{
            margin: '2px 0 0',
            fontWeight: m.pesoTexto,
            fontSize: TAMANO,
            lineHeight: 1.18,
            letterSpacing: '-0.01em',
          }}
        >
          <span style={{ whiteSpace: 'nowrap' }}>Confirma por WhatsApp y</span>
          <br />
          <span style={{ whiteSpace: 'nowrap' }}>
            recibe tu <b style={{ fontWeight: m.pesoTitulo, ...m.regalo }}>REGALO</b> 🎁
          </span>
        </p>

        <a
          href={WHATSAPP_URL}
          target="_blank"
          rel="noopener noreferrer"
          style={{
            marginTop: 'clamp(26px, 3.5vw, 48px)',
            width: '100%',
            maxWidth: 520,
            minHeight: 'clamp(52px, 6vw, 84px)',
            padding: '0 24px',
            boxSizing: 'border-box',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            gap: 14,
            color: '#FFFFFF',
            textDecoration: 'none',
            fontWeight: 700,
            fontSize: 'clamp(16px, 1.9vw, 24px)',
            ...m.boton,
          }}
        >
          <svg
            width="1.25em"
            height="1.25em"
            viewBox="0 0 24 24"
            fill="none"
            stroke="#FFFFFF"
            strokeWidth="2"
            strokeLinecap="round"
            strokeLinejoin="round"
            aria-hidden="true"
          >
            <path d="M3.5 20.5l1.3-4.2A8.5 8.5 0 1 1 8 19.4z" />
          </svg>
          Confirmar por WhatsApp
        </a>
      </div>
    </main>
  )
}
