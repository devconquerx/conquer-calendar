import paperboardTexture from '../assets/img/cb/paperboard-texture.avif'
import ctaButtonBg from '../assets/img/cb/cta-button-bg.png'
import logo from '../assets/img/cb/logo-vert-cent-negro.png'
import tornTransition from '../assets/img/cb/torn-transition.png'
import tornTransition2000 from '../assets/img/cb/torn-transition-2000.png'
import cardBackground from '../assets/img/cb/card-background.png'
import conquista from '../assets/img/cb/conquista.svg'
import heroThumbnail from '../assets/img/cb/hero-thumbnail.png'
import tape1 from '../assets/img/cb/tape1.avif'
import tape2 from '../assets/img/cb/tape2.avif'
import pxLg1 from '../assets/img/cb/px-lg-1.svg'
import pxLg5 from '../assets/img/cb/px-lg-5.svg'
import pxLg6 from '../assets/img/cb/px-lg-6.svg'
import pxLg8 from '../assets/img/cb/px-lg-8.svg'
import pxSm4 from '../assets/img/cb/px-sm-4.svg'
import pxSm8 from '../assets/img/cb/px-sm-8.svg'
import pixelDeco from '../assets/img/cb/pixel-6x6.svg'
import pixelDeco2 from '../assets/img/cb/pixel-6x6-2.svg'
import pxSm7 from '../assets/img/cb/px-sm-7.svg'
import gridBackground from '../assets/img/cb/grid-background.avif'
import iconReloj from '../assets/img/cb/icon-reloj.svg'
import iconBandera from '../assets/img/cb/icon-bandera.svg'
import iconRayo from '../assets/img/cb/icon-rayo.svg'
import iconAgenda from '../assets/img/cb/icon-agenda.svg'
import iconFuego from '../assets/img/cb/icon-fuego.svg'
import bulletIcon1 from '../assets/img/cb/conquie-cool2.svg'
import bulletIcon2 from '../assets/img/cb/conquie-escribir.svg'
import bulletIcon3 from '../assets/img/cb/conquie-dinero2.svg'
import footerLogo from '../assets/img/cb/footer-logo.png'
import instructorMask from '../assets/img/cb/instructor-mask-right.svg'
import pixelCardTop from '../assets/img/cb/pixel-card-top.svg'
import pixelCardBottom from '../assets/img/cb/pixel-card-bottom.png'
import instructorPhoto from '../assets/img/cb/bienvenido-saez-2.avif'
// Assets de la página de confirmación — réplica 1:1 de producción
// (conquerblocks.com/conquer-blocks/confirmacion-llamada).
import confFiesta from '../assets/img/cb/confirmation/conquie-fiesta.svg'
import confRayo from '../assets/img/cb/confirmation/conquie-rayo.svg'
import confMovil from '../assets/img/cb/confirmation/conquie-movil2.svg'
import confPlay from '../assets/img/cb/confirmation/conquie-play.svg'
import confMockup from '../assets/img/cb/confirmation/conquer-mockup.png'
import confStep3Thumb from '../assets/img/cb/confirmation/conquer-blocks-video-thumbnail.jpg'
import confPaperboard from '../assets/img/cb/confirmation/paperboard-texture.avif'
import confTorn from '../assets/img/cb/confirmation/torn-transition.png'

const cbShadow =
  '0px 2px 5px rgba(0,0,0,0.1), 0px 9px 9px rgba(0,0,0,0.09), 0px 20px 12px rgba(0,0,0,0.05), 0px 36px 14px rgba(0,0,0,0.01)'

// Sombra suave en capas de las tarjetas de producción (copiada del box-shadow real).
export const CB_CARD_SHADOW =
  '0 1px 0.4px rgba(0,0,0,0.03), 0 2px 0.8px rgba(0,0,0,0.04), 0 3.4px 1.6px rgba(0,0,0,0.043), 0 5.4px 2.9px rgba(0,0,0,0.047), 0 8.9px 5.3px rgba(0,0,0,0.047), 0 15.4px 10.4px rgba(0,0,0,0.05), 0 30.6px 22.8px rgba(0,0,0,0.055)'

export default {
  id: 'conquerblocks',
  // Marca con landing "paperboard" (réplica Webflow). El renderer compartido
  // (Landing/HeroSection/BulletPoints/LandingForm) se activa con esta bandera.
  paperboard: true,

  // Acento de marca (naranja). Los degradados se inyectan por estilo inline /
  // CSS vars para que Tailwind no tenga que generarlos en build time.
  accent: {
    strongGradient: 'linear-gradient(135deg,#FF4000,#FF9800)',
    auroraGradient: 'linear-gradient(60deg,#FFBF00,#FF4000,#FFBF00,#FF4000)',
    buttonGradient: 'linear-gradient(90deg,#FFBF00,#FF4000)',
    buttonWeight: '400',
    linkGradient: 'linear-gradient(to right,#FFBF00,#FF4000)',
    ring: '#FB923C', // orange-400
  },

  // Datos del footer de la landing (marca, contacto y enlaces legales).
  footer: {
    copyrightBrand: 'Conquer Blocks',
    contactEmail: 'contacto@conquerblocks.com',
    legal: {
      cookies: 'https://www.conquerblocks.com/legal/politica-de-cookies',
      privacy: 'https://www.conquerblocks.com/legal/politica-de-privacidad',
      terms: 'https://www.conquerblocks.com/legal/terminos-y-condiciones',
    },
  },

  // Página de vídeo (VSL paperboard). Tokens medidos en producción; los textos
  // pueden sobreescribirse desde FunnelForm.config['video'].
  video: {
    subtitle: 'Vídeo de 15 minutos',
    title:
      'Descubre una nueva profesión con la que asegurar tu futuro económico, tener siempre trabajo, un muy buen salario y no tener un techo en tu carrera profesional',
    badgeColor: '#0f172a', // borde y texto del badge sobre la cabecera crema
    titleColor: '#0f172a',
    titleSize: 'text-2xl md:text-[32px]',
    // Glow azul suave alrededor del reproductor (idéntico a producción).
    glow: '0 2px 20px 6px rgba(127,193,255,0.28)',
    headerLogoWidth: '125px',
    footerLogoWidth: '280px',
  },

  // Página de confirmación de llamada (paperboard). Contenido + assets de la
  // marca; el renderer compartido (PaperboardConfirmation) los consume.
  confirmation: {
    heroIcon: confFiesta,
    heroIconSmall: confRayo,
    felicidades: '¡Felicidades!',
    // Degradado de texto "conquer-gradient" medido en producción.
    felicidadesGradient: 'linear-gradient(135deg,#FF4000,#FF9800)',
    heroTitle: 'Tu llamada ha sido reservada',
    importanteTitle: 'Importante',
    importanteText: 'completa estos 3 pasos ahora para poder aprovechar tu llamada al máximo',
    // Caja "Importante" / recordatorio: fondo de imagen (card-background.png),
    // igual que producción. El rayo se desborda por la esquina inferior derecha.
    boxImage: cardBackground,
    accentGradient: 'linear-gradient(135deg,#FF4000,#FF9800)',
    // Navbar: solo el logo centrado, sin tarjeta/borde (como producción).
    navbarLogoOnly: true,
    // Fondo paperboard de la página de confirmación: textura propia (más clara y
    // fina que la del StepForm) tileada al 50% con velo blanco 0.4 sobre #FAFAFA,
    // exactamente como producción.
    texture: confPaperboard,
    // Rasgado hecho con la MISMA textura paperboard de producción, para que el
    // crema del borde combine con el fondo de las secciones (el antiguo era de
    // otra textura y se veía más tenue/desentonado).
    torn: confTorn,
    paperboardTiled: true,
    // Espaciado del hero medido en producción (logo 32px desde arriba; 16px
    // logo→icono; 40px icono→título; 40px título→caja; 32px caja→fin).
    heroSectionPad: 'pt-4 pb-8',
    navbarMb: 'mb-0',
    heroIconMb: 'mb-10',
    heroTitleMb: 'mb-10',
    boxPadY: 'py-10 md:py-12', // caja Importante: padding 48px como producción
    importanteTitleMb: 'mb-4',
    // Píxeles decorativos: 150px, opacidad plena, pegados a los bordes (izq
    // arriba, dcha más abajo) — idéntico a producción.
    heroDecos: ['top-[60px] left-0 w-[150px]', 'top-[239px] right-0 w-[150px]'],
    heroIconSize: 'w-32 h-32',
    heroMaxWidth: '740px',
    boxMaxWidth: '740px',
    // Paso 2 — tarjeta 1024px (2 columnas de 511px), mockup 511×511 cuadrado,
    // título 40px/500, icono móvil 93×132, párrafos 16px/300 #171717, y espacios
    // medidos en producción (20px badge→tarjeta, 28px título→párrafos, 20px
    // tarjeta→recordatorio).
    paso2BadgeMb: 'mb-5',
    paso2CardMax: 'max-w-[1024px] mx-auto',
    paso2ImgWidth: 'lg:w-[511px]',
    paso2MinHeight: '511px',
    paso2HeadingClass: 'text-3xl md:text-[40px] font-medium leading-[1.1]',
    paso2IconClass: 'w-[93px] h-auto',
    paso2HeadingMb: 'mb-7',
    paso2ParagraphClass: 'text-base text-[#171717] leading-[1.25] font-light space-y-5',
    paso2ReminderMt: 'mt-5',
    // Paso 3 — sección con padding 24px/16px; título 48px/600 interlineado 1.1
    // (maxW 768); subtítulo y acento 16px/300; play 102px; todos los gaps 20px.
    paso3SectionPad: 'pt-6 pb-12',
    paso3BadgeMb: 'mb-5',
    paso3TitleSize: 'text-3xl md:text-[48px]',
    paso3TitleLeading: 'leading-[1.1]',
    paso3TitleMb: 'mb-5',
    paso3TitleMaxW: 'max-w-[768px]',
    paso3SubtitleMaxW: 'max-w-[560px]',
    paso3SubtitleClass: 'text-white text-base font-light leading-[1.25]',
    // inline-block para que el gradiente abarque exactamente el texto (gradiente
    // completo y vivo en toda la frase, no repartido por todo el ancho del div).
    paso3SubtitleAccentClass: 'text-base font-light leading-[1.25] inline-block',
    paso3SubtitleMb: 'mb-5',
    paso3SubtitleBlockMb: 'mb-5',
    paso3PlayClass: 'w-[102px] h-[102px]',
    // El thumbnail va oscurecido y desenfocado (el play queda nítido encima).
    paso3ThumbFilter: 'brightness(0.65) blur(3px)',
    // Footer minimal: padding 32px, logo ~106px, y dos píxeles decorativos
    // (derecha px-lg-8 opacidad 0.85; izquierda px-sm-7 asomando arriba).
    footerPadY: 'py-8',
    footerLogoHeight: 'h-[106px]',
    footerDecos: [
      { img: 'lg8', cls: 'top-4 right-5 w-[100px] opacity-[0.85]' },
      { img: 'sm7', cls: 'top-0 left-[10%] w-[150px] opacity-100 -translate-y-[88%]' },
    ],
    // Tamaños de texto medidos en producción (Funnel Display).
    importanteTextSize: 'text-base md:text-lg', // 18px
    reminderTextClass: 'font-medium text-lg md:text-[24px] leading-[1.15]', // 24px/500
    badgeBig: false,
    heroWeight: 'font-medium',
    // Badges (Paso 1/2/3): 20px, peso 500, padding 4px 16px, pill completo —
    // medido en producción.
    badgePad: 'px-4 py-1 rounded-full',
    badgeText: 'text-lg md:text-xl',
    badgeWeight: 'font-medium',
    paso1Badge: 'Paso 1 • Mira este vídeo',
    paso1BadgeIcon: null,
    paso1Text: 'Mira este vídeo de 47 segundos para entender tus siguientes pasos lógicos',
    // Sección del vídeo: padding 48px arriba / 80px abajo; 40px badge→texto y
    // texto→vídeo; texto 16px peso 300 con "47 segundos" en negrita.
    paso1SectionPad: 'pt-12 pb-20',
    paso1BadgeMb: 'mb-10',
    paso1TextClass: 'font-light text-base leading-[1.25]',
    paso1TextMb: 'mb-10',
    paso1TextBold: '47 segundos',
    paso1Video:
      'https://iframe.mediadelivery.net/embed/146448/b13e87cd-570a-4f6b-aba2-23f2bbdebd8e?autoplay=false&loop=false&muted=false&preload=true&responsive=true',
    // Sin marco pixelado: marco de vídeo = borde naranja 2px, sin glow.
    videoFrame: null,
    videoBorderColor: '#FF7700',
    videoGlow: 'none',
    paso2Badge: 'Paso 2 • Confirma tu cita',
    paso2BadgeIcon: null,
    paso2Image: confMockup,
    paso2ImageMode: 'photo',
    paso2HeadingIcon: confMovil,
    paso2Heading: 'Mantente al tanto de tu teléfono',
    paso2Paragraphs: [
      'te contactaremos por llamada para confirmar la cita el día y la hora acordadas, una vez confirmada la sesión con tu asesor, te enviaremos el enlace de la videollamada.',
      'Es importante que contestes confirmando 👍 tu llamada, ya que estamos recibiendo muchísimas solicitudes y queremos hablar con personas que estén comprometidas en ser un caso de éxito.',
    ],
    paso2Divider: false,
    reminderText: 'Recuerda conectarte puntual y estando en un lugar tranquilo y cómodo.',
    paso3Badge: 'Paso 3 • Descubre',
    paso3BadgeIcon: null,
    paso3TitlePre: 'Descubre más acerca de la oportunidad de convertirte en ',
    paso3TitleAccent: 'Desarrollador Full-Stack',
    paso3Subtitle:
      'Disfruta de este video donde revelamos más datos, errores comunes y falsas creencias acerca del Desarrollo Full-Stack.',
    paso3SubtitleAccent: 'Además te enseñaremos nuestra academia por dentro',
    paso3Thumbnail: confStep3Thumb,
    paso3PlayIcon: confPlay,
    paso3Video: 'https://youtu.be/70NzkcJa5oA',
    footerMode: 'minimal',
    footer: {
      contactPhone: '+971 58 848 2637',
      contactEmail: 'admisiones@conquerx.com',
      copyrightBrand: 'Conquer Blocks',
    },
  },

  // Applied to the page wrapper (cream paperboard background, fixed) — usado por el StepForm
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
    tornTransition,
    tornTransition2000,
    cardBackground,
    conquista,
    heroThumbnail,
    tape1,
    tape2,
    pixels: { lg1: pxLg1, lg5: pxLg5, lg6: pxLg6, lg8: pxLg8, sm4: pxSm4, sm7: pxSm7, sm8: pxSm8, deco: pixelDeco, deco2: pixelDeco2 },
    gridBackground,
    icons: { reloj: iconReloj, bandera: iconBandera, rayo: iconRayo, agenda: iconAgenda, fuego: iconFuego },
    bulletIcons: [bulletIcon1, bulletIcon2, bulletIcon3],
    footerLogo,
    instructorMask,
    pixelCardTop,
    pixelCardBottom,
    instructorPhoto,
    ctaButtonBg,
  },

  layout: {
    navBg: 'bg-transparent',
    navLogoFilter: '',
    footerBg: 'bg-[#0A0A0A]',
    footerText: 'text-gray-400',
    footerAccent: 'text-orange-400 hover:text-orange-300',
  },

  landing: {
    contentWidth: '1064px',
    logoHeight: '36px',
    decoPixels: ['top-0 left-[6%]', 'top-[280px] right-[2%]', 'bottom-[120px] right-[8%]'],
    bg: 'bg-[#F5EDE3]',
    dotPattern: '',
    ambientGlow: 'hidden',
    logoFilter: '',
    logoFallbackText: 'text-gray-900',
    hero: {
      subtitle: 'bg-gradient-to-r from-[#FF4000] to-[#FFBF00] bg-clip-text text-transparent',
      title: 'text-gray-900 [&_strong]:font-extrabold [&_strong]:bg-gradient-to-r [&_strong]:from-[#FF4000] [&_strong]:to-[#ff9700] [&_strong]:bg-clip-text [&_strong]:text-transparent',
      description: 'text-gray-600',
    },
    bullets: {
      iconSize: '48px',
      strongWeight: '600',
      checkBg: 'bg-orange-100',
      checkIcon: 'text-orange-500',
      text: 'text-gray-700',
    },
    form: {
      card: 'border-gray-200/50 shadow-lg',
      badge: 'bg-orange-100 text-orange-600',
      badgeDot: 'bg-orange-500',
      title: 'text-gray-900',
      input: 'border-gray-300 bg-white text-gray-900 placeholder:text-gray-400 focus:border-orange-400 focus:ring-1 focus:ring-orange-400/20',
      inputError: 'border-red-400 bg-red-50',
      button: 'bg-gradient-to-r from-[#FFBF00] to-[#FF4000] hover:from-[#FFD000] hover:to-[#FF5500] shadow-lg shadow-orange-500/20',
      consent: 'text-gray-500',
      consentLink: 'text-orange-500',
      trustText: 'text-gray-400',
      trustDivider: 'bg-gray-300',
    },
    instructor: {
      card: 'border-gray-200/50 shadow-lg',
      ring: 'ring-orange-300',
      name: 'text-orange-500',
      role: 'text-gray-500',
      description: 'text-gray-600 [&_strong]:text-gray-900 [&_strong]:font-semibold',
    },
    footer: {
      text: 'text-gray-700',
      disclaimer: 'text-gray-600',
      accent: 'text-orange-600 font-bold',
      link: 'text-gray-700',
    },
  },

  cssVars: {
    '--theme-accent': '#F97316',
    '--theme-accent-hover': '#EA580C',
    '--theme-accent-bg': '#FFF7ED',
    '--theme-accent-text': '#ffffff',
    '--theme-accent-ring': 'rgba(249,115,22,0.3)',
    '--theme-form-bg': 'rgba(255, 255, 255, 0.6)',
    '--theme-form-border': '#BBB49B',
    '--theme-form-texture': `url(${paperboardTexture})`,
    '--theme-btn-gradient': 'linear-gradient(to right, #FFBF00, #FF4000)',
    '--theme-form-shadow': cbShadow,
  },
}
