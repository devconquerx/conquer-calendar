// Tema Conquer Legal — réplica de la landing de producción (conquerlegal.com).
// Mismo sistema de diseño "paperboard" que Conquer Blocks (Webflow) pero con
// acento AZUL en lugar de naranja. Reutiliza la textura/máscara/fondo de tarjeta
// del set `cb/` (son neutros y compartidos) y añade los assets propios de Legal.
import paperboardTexture from '../assets/img/cb/paperboard-texture.avif'
import cardBackground from '../assets/img/cb/card-background.png'
import instructorMask from '../assets/img/cb/instructor-mask-right.svg'
import instructorMaskBottom from '../assets/img/cb/instructor-mask-bottom.svg'
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
// Imagen de degradado azul de la caja "Importante"/recordatorio (PNG real de
// producción, conquer-blocks-gradient.png pero en azul para Legal).
import confBoxGradient from '../assets/img/legal/confirmation/box-gradient.png'
// Textura paperboard de la confirmación: byte-idéntica a la de Conquer Blocks
// (neutra/monocroma, compartida), tileada al 50% como en producción.
import confPaperboard from '../assets/img/cb/confirmation/paperboard-texture.avif'
// Rasgado (torn) exacto de producción (descargado de conquerlegal.com): es el que
// combina con el paperboard; difiere del torn genérico de cb/.
import confTorn from '../assets/img/legal/confirmation/torn-transition.png'
// Máscara pixelada inferior para la foto del Paso 2 en móvil (borde abajo en vez
// de a la derecha, como producción). Forma neutra compartida con Conquer Blocks.
import confMaskBottom from '../assets/img/cb/confirmation/instructor-mask-bottom.svg'
import logo from '../assets/img/legal/logo.png'
// Favicon de marca: mismo PNG que sirve conquerlegal.com ("Favicon - Conquer
// Business"). Se inyecta en <head> en runtime para todas las etapas del funnel
// de Legal (landing, vídeo, stepform, confirmación).
import favicon from '../assets/img/legal/favicon.png'
import bulletReloj from '../assets/img/legal/conquie-reloj2.svg'
import bulletEscribir from '../assets/img/legal/conquie-escribir.svg'
import bulletDocumento from '../assets/img/legal/conquie-documento1.svg'
import instructorPhoto from '../assets/img/legal/ignacio.avif'
import pixelDeco from '../assets/img/legal/pixel-6x6-2.svg'
import pixelDeco2 from '../assets/img/legal/pixel-5x5-5.svg'
// Píxeles del footer (descargados de conquerlegal.com): cluster grande a la
// derecha (px-lg-8) y cluster pequeño a la izquierda asomando arriba (px-sm-7).
import pxLg8 from '../assets/img/legal/px-lg-8.svg'
import pxSm7 from '../assets/img/legal/px-sm-7.svg'

const legalShadow =
  '0px 2px 5px rgba(0,0,0,0.1), 0px 9px 9px rgba(0,0,0,0.09), 0px 20px 12px rgba(0,0,0,0.05), 0px 36px 14px rgba(0,0,0,0.01)'

export default {
  id: 'conquerlegal',
  paperboard: true,

  // Favicon de marca (mismo PNG que conquerlegal.com). FunnelApp lo inyecta en
  // <head> en runtime para todas las etapas del funnel de Legal. Las demás
  // escuelas no definen `favicon`, así que conservan el favicon por defecto.
  favicon,

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
    // Al venir del submit de la landing (navegación SPA), arrancar el vídeo con
    // sonido automáticamente, sin overlay de "activar sonido". Si el navegador
    // bloquea el audio (carga directa sin gesto), cae al autoplay muted + overlay.
    autoplayUnmuted: true,
  },

  // Página de confirmación de llamada — réplica de conquerlegal.com/hub/confirmacion.
  // Misma arquitectura paperboard que Conquer Blocks, con acento azul y copy de Legal.
  confirmation: {
    heroIcon: confApreton,
    heroIconSmall: null,
    felicidades: '¡Felicidades!',
    // Degradado de texto "conquer-gradient" medido en producción (azul Legal).
    felicidadesGradient: 'linear-gradient(135deg,#0040FF,#00BFFF)',
    heroTitle: 'Tu sesión estratégica ha sido reservada',
    importanteTitle: 'Importante',
    importanteText: 'Sigue los pasos indicados para preparar tu llamada con nuestro equipo experto.',
    // Caja "Importante"/recordatorio: imagen de degradado azul (PNG de producción),
    // sin sombra (en Webflow el box-shadow es none). boxGradient queda de respaldo.
    boxImage: confBoxGradient,
    boxGradient: 'linear-gradient(120deg,#1FB0FF 0%,#0A82FF 100%)',
    boxShadowClass: '',
    accentGradient: 'linear-gradient(135deg,#0040FF,#00BFFF)',
    badgeBig: false,
    heroWeight: 'font-medium',
    // ── Hero (sección 1) medido 1:1 en conquerlegal.webflow.io/hub/confirmacion ──
    // Fondo paperboard tileado al 50% con velo blanco 0.4 sobre #FAFAFA.
    texture: confPaperboard,
    paperboardTiled: true,
    // Rasgado exacto de producción (en vez del torn genérico de cb/).
    torn: confTorn,
    // Navbar: solo el logo centrado (125×39), sin tarjeta. Logo a 32px del borde,
    // sin margen hasta el contenido (el icono abre el bloque a 87px).
    navbarLogoOnly: true,
    // Logo: móvil 100×31 (h31) / desktop 125×39 (h39).
    navLogoHeight: 'h-[31px] md:h-[39px] w-auto',
    heroSectionPad: 'pt-4 pb-8',
    navbarMb: 'mb-0',
    heroMaxWidth: '1024px',
    // Ritmo vertical: icono móvil 72px / desktop 128px; gap móvil 18px / desktop
    // 40px (icono→título y título→caja); título móvil 32px / desktop 40px, 500,
    // lh1.1; caja padding móvil 16px / desktop 48px, radio 12px, gap 16px.
    heroIconSize: 'w-[72px] h-[72px] md:w-32 md:h-32',
    heroIconMb: 'mb-[18px] md:mb-10',
    heroTitleSize: 'text-[32px] md:text-[40px]',
    felicidadesSize: 'text-[32px] md:text-[40px]',
    heroTitleLeading: 'leading-[1.1]',
    heroTitleMb: 'mb-[18px] md:mb-10',
    boxMaxWidth: '780px',
    boxPadX: 'px-4 md:px-12',
    boxPadY: 'py-4 md:py-12',
    importanteTitleMb: 'mb-4',
    importanteTextSize: 'text-[18px]', // 18px móvil y desktop
    // Píxeles decorativos del hero: 150px, opacidad 0.2, pegados a los bordes
    // (izq top 58px / dcha top 117px), patrón pixel-6x6-2 azul.
    heroDecoImg: pixelDeco,
    heroDecos: ['top-[58px] left-0 w-[150px] opacity-20', 'top-[117px] right-0 w-[150px] opacity-20'],
    // Badges de los pasos (1/2/3): móvil 16px / desktop 20px, peso 500, pill,
    // padding 4px 16px (medido en producción).
    badgePad: 'px-4 py-1 rounded-full',
    badgeText: 'text-[16px] md:text-[20px]',
    badgeWeight: 'font-medium',
    // Permite que el badge largo (Paso 3) envuelva a 2 líneas en móvil, como producción.
    badgeWrap: true,
    paso1Badge: 'Paso 1 • Mira este vídeo',
    paso1BadgeIcon: null,
    paso1Text: 'Ve este vídeo de 47 segundos para entender cómo prepararte para la sesión y asegurar el diagnóstico de tu empresa.',
    // Texto del paso 1: móvil 14px / desktop 16px, peso 300, "47 segundos" en negrita.
    paso1TextClass: 'font-light text-[14px] md:text-[16px] leading-[1.25]',
    paso1TextBold: '47 segundos',
    // Ritmo móvil medido en Webflow: rasgado→badge ~24px, badge→texto 28px,
    // texto→vídeo 62px, vídeo→rasgado ~72px. Desktop sin cambios (md:/lg:).
    paso1SectionPad: 'pt-6 pb-[72px] md:py-20 lg:py-28',
    paso1BadgeMb: 'mb-7 md:mb-8',
    paso1TextMb: 'mb-[62px] md:mb-12',
    paso1Video:
      'https://iframe.mediadelivery.net/embed/201501/eacf29dd-eb00-4494-9bc4-650beb5a9cab?autoplay=false&loop=false&muted=false&preload=true&responsive=true',
    videoFrame: null,
    paso2Badge: 'Paso 2 • Confirma tu cita',
    paso2BadgeIcon: null,
    // Card + caja recordatorio a 1024px centrado (como producción); sin esto el
    // contenido se explayaba hasta los ~1280px del contenedor.
    paso2CardMax: 'max-w-[1024px] mx-auto',
    // Sección Paso 2: padding móvil ~16px / desktop 80px; badge→card 28px móvil;
    // card→recordatorio 28px móvil. En móvil la tarjeta se apila (foto cuadrada
    // arriba), el padding interno baja a 24px y el icono del teléfono se oculta.
    paso2SectionPad: 'py-4 md:py-20',
    paso2BadgeMb: 'mb-7 md:mb-16',
    paso2ReminderMt: 'mt-7 md:mt-12',
    paso2MobileBox: 'aspect-square lg:aspect-auto',
    paso2MaskMobile: confMaskBottom,
    paso2ContentPad: 'p-6 lg:p-12',
    paso2Image: confEmpathy,
    paso2ImageMode: 'photo',
    paso2HeadingIcon: confMovil,
    paso2Heading: 'Mantente al tanto de tu teléfono',
    // Tipografía del card medida en producción (en local salía más grande/pesada):
    // título móvil 32px / desktop 40px /500 lh1.1; icono teléfono 93×132 (oculto en
    // móvil, como producción); párrafos móvil 14px / desktop 16px /300 lh1.25 #171717.
    paso2HeadingClass: 'text-[32px] md:text-[40px] font-medium leading-[1.1]',
    paso2IconClass: 'w-[93px] h-auto hidden lg:block',
    paso2ParagraphClass: 'text-[14px] md:text-[16px] text-[#171717] leading-[1.25] font-light space-y-5',
    paso2Paragraphs: [
      'Un estratega de nuestro equipo te contactará directamente para validar los datos de tu empresa antes de la sesión. Una vez confirmada tu asistencia, te enviaremos el enlace privado de acceso a la videollamada.',
      'Es obligatorio responder a la confirmación. Debido a la alta demanda y al análisis personalizado que realiza nuestro equipo, solo mantenemos la agenda con fundadores comprometidos con la rentabilidad y el crecimiento de su negocio.',
    ],
    paso2Divider: true,
    reminderText: 'Recuerda conectarte puntual, en un espacio privado, tranquilo y si lo necesitas, con la información relevante a la mano.',
    // Recordatorio: móvil 20px / desktop 24px /500 lh1.1 centrado; padding 24px móvil.
    reminderTextClass: 'text-center font-medium text-xl md:text-[24px] leading-[1.1]',
    reminderPad: 'px-6 md:px-12 py-6',
    paso3Badge: 'Paso 3 • Perspectivas adicionales',
    paso3BadgeIcon: null,
    paso3TitlePre: 'Descubre cómo reestructurar la legalidad de tu negocio para ',
    paso3TitleAccent: 'escalarlo sin frenos',
    paso3Subtitle: 'Accede a esta presentación exclusiva donde revelamos los errores estructurales más comunes que cometen los fundadores y cómo funciona nuestra metodología de consultoría por dentro.',
    paso3SubtitleAccent: null,
    // Móvil medido en Webflow: título 36px/600 lh1.1; subtítulo 14px/300; sección
    // padding ~56px; gaps badge→título / título→sub / sub→thumb = 28px. Desktop md:.
    paso3TitleSize: 'text-[36px] md:text-[40px]',
    paso3TitleLeading: 'leading-[1.1]',
    paso3SubtitleClass: 'text-white font-light text-[14px] md:text-[16px] leading-[1.25]',
    paso3SectionPad: 'py-14 md:py-20 lg:py-28',
    paso3BadgeMb: 'mb-7 md:mb-8',
    paso3TitleMb: 'mb-7 md:mb-6',
    paso3SubtitleBlockMb: 'mb-7 md:mb-12',
    paso3Thumbnail: confThumb,
    paso3PlayIcon: confPlay,
    paso3Video: 'https://youtu.be/70NzkcJa5oA',
    // Footer: logo CONQUER Legal centrado, móvil 125×39 (h39) / desktop 280×88 (h88),
    // padding 32px arriba/abajo, sobre paperboard tileado. Dos píxeles: cluster a la
    // derecha (px-lg-8, móvil 75px / desktop 100px, opacidad 0.2) y pequeño a la
    // izquierda asomando por arriba (px-sm-7, móvil 100px / desktop 150px).
    footerMode: 'minimal',
    footerPadY: 'py-8',
    footerLogoHeight: 'h-[39px] md:h-[88px] w-auto',
    footerDecos: [
      { img: 'pxLg8', cls: 'top-[9px] right-[30px] w-[75px] md:right-[15px] md:w-[100px] opacity-20' },
      { img: 'pxSm7', cls: 'top-0 left-[31px] w-[100px] -translate-y-[80%] md:left-[150px] md:w-[150px]' },
    ],
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
    pixels: { deco: pixelDeco, deco2: pixelDeco2, sm7: pixelDeco, lg8: pixelDeco2, pxLg8, pxSm7 },
    bulletIcons: [bulletReloj, bulletEscribir, bulletDocumento],
    instructorMask,
    instructorMaskBottom, // borde pixelado abajo (móvil); el derecho es para desktop
    instructorPhoto,
    // La foto de Legal se pinta como background del cuadro: bgSize = zoom (la foto
    // es cuadrada y "alejada"), bgPosition = punto focal (centra a Ignacio sin
    // recortar la cabeza ni dejar huecos). Valores afinados en vivo.
    instructorBgSize: '140%',
    instructorBgPosition: '70% 18%',
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
