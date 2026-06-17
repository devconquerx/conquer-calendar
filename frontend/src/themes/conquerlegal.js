// Tema Conquer Legal — réplica de la landing de producción (conquerlegal.com).
// Mismo sistema de diseño "paperboard" que Conquer Blocks (Webflow) pero con
// acento AZUL en lugar de naranja. Reutiliza la textura/máscara/fondo de tarjeta
// del set `cb/` (son neutros y compartidos) y añade los assets propios de Legal.
import paperboardTexture from '../assets/img/cb/paperboard-texture.avif'
import cardBackground from '../assets/img/cb/card-background.png'
import instructorMask from '../assets/img/cb/instructor-mask-right.svg'
// Activos neutros de la página de vídeo (papel rasgado crema + retícula oscura);
// son monocromos y se comparten con Conquer Blocks.
import tornTransition from '../assets/img/cb/torn-transition.png'
import tornTransition2000 from '../assets/img/cb/torn-transition-2000.png'
import gridBackground from '../assets/img/cb/grid-background.avif'
// Assets propios de la página de confirmación de Legal (descargados de conquerlegal.com).
import confApreton from '../assets/img/legal/confirmation/conquie-apreton.svg'
import confMovil from '../assets/img/legal/confirmation/conquie-movil2.svg'
import confPlay from '../assets/img/legal/confirmation/conquie-play.svg'
import confEmpathy from '../assets/img/legal/confirmation/empathy.avif'
import confThumb from '../assets/img/legal/confirmation/paso3-thumbnail.jpg'
import logo from '../assets/img/legal/logo.png'
import bulletReloj from '../assets/img/legal/conquie-reloj2.svg'
import bulletEscribir from '../assets/img/legal/conquie-escribir.svg'
import bulletDocumento from '../assets/img/legal/conquie-documento1.svg'
import instructorPhoto from '../assets/img/legal/ignacio.avif'
import pixelDeco from '../assets/img/legal/pixel-6x6-2.svg'
import pixelDeco2 from '../assets/img/legal/pixel-5x5-5.svg'

const legalShadow =
  '0px 2px 5px rgba(0,0,0,0.1), 0px 9px 9px rgba(0,0,0,0.09), 0px 20px 12px rgba(0,0,0,0.05), 0px 36px 14px rgba(0,0,0,0.01)'

export default {
  id: 'conquerlegal',
  paperboard: true,

  // Acento de marca (azul). Mismos slots que conquerblocks.
  accent: {
    strongGradient: 'linear-gradient(135deg,#0040FF,#00BFFF)',
    auroraGradient: 'linear-gradient(60deg,#00C0FF,#0040FF,#00C0FF,#0040FF)',
    // Gradiente exacto del botón en producción (3 paradas, periwinkle→navy).
    buttonGradient: 'linear-gradient(90deg, #3E76FF 0%, #1845D6 42%, #031464 100%)',
    buttonWeight: '800',
    linkGradient: 'linear-gradient(to right,#00C0FF,#0040FF)',
    ring: '#0040FF',
  },

  footer: {
    copyrightBrand: 'Conquer Business',
    contactEmail: 'contacto@conquerlegal.com',
    legal: {
      cookies: 'https://www.conquerlegal.com/legal/politica-de-cookies',
      privacy: 'https://www.conquerlegal.com/legal/politica-de-privacidad',
      terms: 'https://www.conquerlegal.com/legal/terminos-y-condiciones',
    },
  },

  // Página de vídeo (VSL paperboard) — misma estructura que Conquer Blocks pero
  // con acento azul y copy de Legal. Los textos pueden venir de config['video'].
  video: {
    subtitle: 'Presentación exclusiva de 10 minutos',
    title:
      'Los <strong>negocios online</strong> no se destruyen por la falta de ventas...<br/>se destruyen porque crecen más rápido que la estructura que los sostiene',
    badgeColor: '#0f172a',
    titleColor: '#0f172a',
    titleSize: 'text-2xl md:text-[30px]',
    // Glow azul (acento Legal) alrededor del reproductor.
    glow: '0 2px 20px 6px rgba(62,118,255,0.30)',
    headerLogoWidth: '125px',
    footerLogoWidth: '240px',
  },

  // Página de confirmación de llamada — réplica de conquerlegal.com/hub/confirmacion.
  // Misma arquitectura paperboard que Conquer Blocks, con acento azul y copy de Legal.
  confirmation: {
    heroIcon: confApreton,
    heroIconSmall: null,
    felicidades: '¡Felicidades!',
    felicidadesGradient: 'linear-gradient(135deg,#0040FF,#00BFFF)',
    heroTitle: 'Tu sesión estratégica ha sido reservada',
    importanteTitle: 'Importante',
    importanteText: 'Sigue los pasos indicados para preparar tu llamada con nuestro equipo experto.',
    boxGradient: 'linear-gradient(120deg,#1FB0FF 0%,#0A82FF 100%)',
    accentGradient: 'linear-gradient(135deg,#0040FF,#00BFFF)',
    badgeBig: false,
    heroWeight: 'font-medium',
    paso1Badge: 'Paso 1 • Mira este vídeo',
    paso1BadgeIcon: null,
    paso1Text: 'Ve este vídeo de 47 segundos para entender cómo prepararte para la sesión y asegurar el diagnóstico de tu empresa.',
    paso1Video:
      'https://iframe.mediadelivery.net/embed/146448/b13e87cd-570a-4f6b-aba2-23f2bbdebd8e?autoplay=false&loop=false&muted=false&preload=true&responsive=true',
    videoFrame: null,
    paso2Badge: 'Paso 2 • Confirma tu cita',
    paso2BadgeIcon: null,
    paso2Image: confEmpathy,
    paso2ImageMode: 'photo',
    paso2HeadingIcon: confMovil,
    paso2Heading: 'Mantente al tanto de tu teléfono',
    paso2Paragraphs: [
      'Un estratega de nuestro equipo te contactará directamente para validar los datos de tu empresa antes de la sesión. Una vez confirmada tu asistencia, te enviaremos el enlace privado de acceso a la videollamada.',
      'Es obligatorio responder a la confirmación. Debido a la alta demanda y al análisis personalizado que realiza nuestro equipo, solo mantenemos la agenda con fundadores comprometidos con la rentabilidad y el crecimiento de su negocio.',
    ],
    paso2Divider: true,
    reminderText: 'Recuerda conectarte puntual, en un espacio privado, tranquilo y si lo necesitas, con la información relevante a la mano.',
    paso3Badge: 'Paso 3 • Perspectivas adicionales',
    paso3BadgeIcon: null,
    paso3TitlePre: 'Descubre cómo reestructurar la legalidad de tu negocio para ',
    paso3TitleAccent: 'escalarlo sin frenos',
    paso3Subtitle: 'Accede a esta presentación exclusiva donde revelamos los errores estructurales más comunes que cometen los fundadores y cómo funciona nuestra metodología de consultoría por dentro.',
    paso3SubtitleAccent: null,
    paso3Thumbnail: confThumb,
    paso3PlayIcon: confPlay,
    paso3Video: 'https://youtu.be/70NzkcJa5oA',
    footerMode: 'minimal',
  },

  // Fondo de página paperboard (usado por el StepForm).
  page: {
    backgroundColor: '#F5EDE3',
    backgroundImage: `url(${paperboardTexture})`,
    backgroundSize: 'cover',
    backgroundPosition: 'center',
    backgroundAttachment: 'fixed',
  },

  assets: {
    logo,
    paperboardTexture,
    cardBackground,
    tornTransition,
    tornTransition2000,
    gridBackground,
    // El badge/sm7/lg8 de la página de vídeo reutilizan los píxeles azules de Legal.
    pixels: { deco: pixelDeco, deco2: pixelDeco2, sm7: pixelDeco, lg8: pixelDeco2 },
    bulletIcons: [bulletReloj, bulletEscribir, bulletDocumento],
    instructorMask,
    instructorPhoto,
  },

  layout: {
    navBg: 'bg-transparent',
    navLogoFilter: '',
    footerBg: 'bg-[#0A0A0A]',
    footerText: 'text-gray-400',
    footerAccent: 'text-blue-400 hover:text-blue-300',
  },

  // Tokens neutros del paperboard (idénticos a conquerblocks: fondo crema,
  // tarjetas grises, borde arena, tinta casi negra). El acento de color va
  // por `accent`, no por estos tokens.
  landing: {
    contentWidth: '1024px',
    logoHeight: '39px',
    // 4 racimos de pixeles (2 izq / 2 der, escalonados) como producción.
    decoPixels: ['top-[-70px] left-[8%]', 'top-[270px] right-[12%]', 'top-[830px] right-[20%]', 'top-[1140px] left-[24%]'],
    bg: 'bg-[#F5EDE3]',
    dotPattern: '',
    ambientGlow: 'hidden',
    logoFilter: '',
    logoFallbackText: 'text-gray-900',
    hero: {
      subtitle: 'bg-gradient-to-r from-[#0040FF] to-[#00BFFF] bg-clip-text text-transparent',
      title: 'text-gray-900',
      description: 'text-gray-600',
    },
    bullets: {
      // Sistema de diseño paperboard (medido en producción): icono 64px,
      // <strong> en 700.
      iconSize: '64px',
      strongWeight: '700',
      checkBg: 'bg-blue-100',
      checkIcon: 'text-blue-500',
      text: 'text-gray-700',
    },
    form: {
      card: 'border-gray-200/50 shadow-lg',
      badge: 'bg-blue-100 text-blue-600',
      badgeDot: 'bg-blue-500',
      title: 'text-gray-900',
      input: 'border-gray-300 bg-white text-gray-900 placeholder:text-gray-400 focus:border-blue-400 focus:ring-1 focus:ring-blue-400/20',
      inputError: 'border-red-400 bg-red-50',
      button: 'bg-gradient-to-r from-[#00C0FF] to-[#0040FF] hover:from-[#33CCFF] hover:to-[#0050FF] shadow-lg shadow-blue-500/20',
      consent: 'text-gray-500',
      consentLink: 'text-blue-500',
      trustText: 'text-gray-400',
      trustDivider: 'bg-gray-300',
    },
    instructor: {
      card: 'border-gray-200/50 shadow-lg',
      ring: 'ring-blue-300',
      name: 'text-blue-500',
      role: 'text-gray-500',
      description: 'text-gray-600 [&_strong]:text-gray-900 [&_strong]:font-semibold',
    },
    footer: {
      text: 'text-gray-700',
      disclaimer: 'text-gray-600',
      accent: 'text-blue-600 font-bold',
      link: 'text-gray-700',
    },
  },

  cssVars: {
    '--theme-page-bg': '#F5EDE3',
    '--theme-accent': '#1845D6',
    '--theme-accent-hover': '#0033CC',
    '--theme-accent-bg': '#EFF4FF',
    '--theme-accent-text': '#ffffff',
    '--theme-accent-ring': 'rgba(62,118,255,0.3)',
    '--theme-form-bg': 'rgba(255, 255, 255, 0.6)',
    '--theme-form-border': '#BBB49B',
    '--theme-form-texture': `url(${paperboardTexture})`,
    // Mismo gradiente azul de producción que los CTA de la landing y el vídeo.
    '--theme-btn-gradient': 'linear-gradient(90deg, #3E76FF 0%, #1845D6 42%, #031464 100%)',
    '--theme-form-shadow': legalShadow,
  },
}
