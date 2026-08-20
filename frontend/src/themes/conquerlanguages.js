// Tema Conquer Languages — mismo sistema de diseño "paperboard" que Conquer
// Blocks y Conquer Legal, con el acento TEAL de la marca (#70B3C4, el color del
// CTA y del footer en conquerlanguages.com) y el dorado (#E0A52E) que la landing
// vieja usaba en los checks. Reutiliza la textura/máscaras/rasgados del set
// `cb/` (son neutros y compartidos, igual que hace Legal) y añade los assets
// propios de Languages.
import defaultTheme from './default'
import paperboardTexture from '../assets/img/cb/paperboard-texture.avif'
import instructorMask from '../assets/img/cb/instructor-mask-right.svg'
import instructorMaskBottom from '../assets/img/cb/instructor-mask-bottom.svg'
// Activos neutros de la página de vídeo (papel rasgado crema + retícula oscura),
// monocromos y compartidos con Blocks y Legal.
import tornTransition from '../assets/img/cb/torn-transition.png'
import tornTransition2000 from '../assets/img/cb/torn-transition-2000.png'
import gridBackground from '../assets/img/cb/grid-background.avif'
// Assets de la página de confirmación. Son los mismos del set cb/: la textura,
// el rasgado, la máscara y los "conquie" son monocromos y ya se comparten entre
// marcas (Legal hace lo mismo). Lo único propio de Languages es el acento y el
// contenido.
import confPaperboard from '../assets/img/cb/confirmation/paperboard-texture.avif'
import confTorn from '../assets/img/cb/confirmation/torn-transition.png'
import confMaskBottom from '../assets/img/cb/confirmation/instructor-mask-bottom.svg'
import confFiesta from '../assets/img/cb/confirmation/conquie-fiesta.svg'
import confRayo from '../assets/img/cb/confirmation/conquie-rayo.svg'
import confMovil from '../assets/img/cb/confirmation/conquie-movil2.svg'
import confPlay from '../assets/img/cb/confirmation/conquie-play.svg'
// Mockup del Paso 2 en la versión de Languages (móvil con su logo sobre el teal
// de marca). El de Blocks lleva su naranja quemado en la imagen.
import confMockup from '../assets/img/languages/confirmation/conquer-mockup.webp'
// Portada del vídeo del Paso 3 (16:9), la misma que sirve producción.
import confStep3Thumb from '../assets/img/languages/confirmation/paso3-thumbnail.webp'
// Iconos de los bullets: los mismos "conquie" del set cb/ que usa Conquer
// Blocks. Son monocromos y no llevan color de marca, así que se comparten tal
// cual; el orden aquí sigue el de los bullets de Languages (dinero → confianza
// → método), no el de Blocks.
import bulletIcon1 from '../assets/img/cb/conquie-dinero2.svg'
import bulletIcon2 from '../assets/img/cb/conquie-cool2.svg'
import bulletIcon3 from '../assets/img/cb/conquie-escribir.svg'
// Assets propios de la marca, descargados de conquerlanguages.com.
import logo from '../assets/img/languages/logo.svg'
import instructorPhoto from '../assets/img/languages/andy.webp'
// Racimos de píxeles decorativos: misma forma que los de Legal (neutra) pero
// con el degradado teal de Languages en vez del azul.
import pixelDeco from '../assets/img/languages/pixel-6x6-2.svg'
import pixelDeco2 from '../assets/img/languages/pixel-5x5-5.svg'

// Teal de marca. El CTA de producción es plano (#70B3C4); aquí se degrada a
// tres paradas como en Blocks/Legal para que el botón encaje en la línea
// paperboard, manteniendo el color de marca en la parada central.
const CL_TEAL = '#70B3C4'
const CL_TEAL_LIGHT = '#8FD4E3'
const CL_TEAL_DARK = '#3E7F92'
const CL_GRADIENT = `linear-gradient(90deg, ${CL_TEAL_LIGHT} 0%, ${CL_TEAL} 42%, ${CL_TEAL_DARK} 100%)`
const CL_TEXT_GRADIENT = `linear-gradient(135deg,${CL_TEAL_DARK},${CL_TEAL_LIGHT})`

// Sombra en capas de las tarjetas, idéntica a la de Legal (es neutra).
const clShadow =
  '0px 2px 5px rgba(0,0,0,0.1), 0px 9px 9px rgba(0,0,0,0.09), 0px 20px 12px rgba(0,0,0,0.05), 0px 36px 14px rgba(0,0,0,0.01)'

export default {
  ...defaultTheme,
  id: 'conquerlanguages',
  paperboard: true,

  // El contenedor GTM de Languages (heredado de Webflow) dispara el Schedule
  // con el trigger "page load en *confirmacion-llamada*", así que el StepForm
  // debe navegar a la confirmación con recarga real, no pushState — mismo fix
  // que Finance/Blocks. Flag de MARCA: no toca el GTM en vivo, solo cambia cómo
  // conquer-calendar navega en su propio flujo. Sobrevive a esta migración.
  gtmHardConfirmation: true,

  // Acento de marca (teal). Mismos slots que conquerblocks/conquerlegal.
  accent: {
    strongGradient: CL_TEXT_GRADIENT,
    auroraGradient: `linear-gradient(60deg,${CL_TEAL_LIGHT},${CL_TEAL_DARK},${CL_TEAL_LIGHT},${CL_TEAL_DARK})`,
    buttonGradient: CL_GRADIENT,
    buttonWeight: '800',
    linkGradient: `linear-gradient(to right,${CL_TEAL_LIGHT},${CL_TEAL_DARK})`,
    ring: CL_TEAL,
    solid: CL_TEAL,
  },

  footer: {
    copyrightBrand: 'Conquer Languages',
    contactEmail: 'contacto@conquerlanguages.com',
    legal: {
      cookies: 'https://www.conquerlanguages.com/politica-de-cookies',
      privacy: 'https://www.conquerlanguages.com/politica-de-privacidad',
      terms: 'https://www.conquerlanguages.com/aviso-legal',
    },
  },

  // Página de vídeo (VSL paperboard) — misma estructura que Blocks y Legal con
  // el copy de Languages. Los textos pueden venir de config['video'] en BD.
  video: {
    subtitle: 'Vídeo gratis de 15 minutos',
    title:
      'Aprende a <strong>hablar inglés fluido</strong> y a entender a los nativos estés donde estés, con un método dinámico que te <strong>garantiza un nivel B2</strong> en 90 días',
    badgeColor: '#0f172a',
    titleColor: '#0f172a',
    titleSize: 'text-2xl md:text-[30px]',
    // Glow teal (acento Languages) alrededor del reproductor.
    glow: '0 2px 20px 6px rgba(112,179,196,0.30)',
    headerLogoWidth: '150px',
    footerLogoWidth: '240px',
  },

  // Página de confirmación de llamada — misma arquitectura paperboard que
  // Conquer Blocks (mismos tokens de espaciado, medidos en su producción), con
  // el acento teal de Languages y el copy de la marca.
  confirmation: {
    heroIcon: confFiesta,
    heroIconSmall: confRayo,
    felicidades: '¡Felicidades!',
    felicidadesGradient: CL_TEXT_GRADIENT,
    heroTitle: 'Tu llamada ha sido reservada',
    importanteTitle: 'Importante',
    importanteText: 'completa estos 3 pasos ahora para poder aprovechar tu llamada al máximo',
    // El PNG de Blocks (cardBackground) es naranja: aquí se usa un degradado
    // teal por CSS en vez de una imagen de otra marca.
    boxImage: null,
    boxGradient: `linear-gradient(120deg, ${CL_TEAL_LIGHT} 0%, ${CL_TEAL} 45%, ${CL_TEAL_DARK} 100%)`,
    accentGradient: CL_TEXT_GRADIENT,
    navbarLogoOnly: true,
    texture: confPaperboard,
    torn: confTorn,
    paperboardTiled: true,
    heroSectionPad: 'pt-4 pb-8',
    navbarMb: 'mb-0',
    heroIconMb: 'mb-10',
    heroTitleMb: 'mb-10',
    boxPadY: 'py-10 md:py-12',
    importanteTitleMb: 'mb-4',
    heroDecos: ['top-[60px] left-0 w-[150px]', 'top-[239px] right-0 w-[150px]'],
    heroIconSize: 'w-32 h-32',
    heroMaxWidth: '740px',
    boxMaxWidth: '740px',
    badgeText: 'text-lg md:text-xl',

    paso1Badge: 'Paso 1 • Mira este vídeo',
    paso1BadgeIcon: null,
    paso1Text: 'Mira este vídeo de 47 segundos para entender tus siguientes pasos lógicos',
    paso1TextBold: '47 segundos',
    paso1SectionPad: 'pt-12 pb-20',
    paso1BadgeMb: 'mb-10',
    paso1TextClass: 'font-light text-base leading-[1.25]',
    paso1TextMb: 'mb-10',
    paso1Video:
      'https://iframe.mediadelivery.net/embed/348662/8536ee79-a3ef-4714-9e2a-514e574f98bb'
      + '?autoplay=false&loop=false&muted=false&preload=true&responsive=true',
    videoFrame: null,
    videoBorderColor: CL_TEAL,
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
    paso2SectionPad: 'py-12 lg:py-20',
    paso2BadgeMb: 'mb-5',
    paso2CardMax: 'max-w-[1024px] mx-auto',
    paso2ImgWidth: 'lg:w-[511px]',
    paso2MinHeight: '511px',
    paso2MobileBox: 'aspect-square lg:aspect-auto',
    paso2MaskMobile: confMaskBottom,
    paso2HeadingClass: 'text-[32px] md:text-[40px] font-medium leading-[1.1]',
    paso2IconClass: 'w-[93px] h-auto hidden lg:block',
    paso2IconMobileFloat: true,
    paso2ContentPad: 'p-6 lg:p-12',
    paso2HeadingMb: 'mb-7',
    paso2ParagraphClass: 'text-sm md:text-base text-[#171717] leading-[1.25] font-light space-y-5',
    paso2ReminderMt: 'mt-7 lg:mt-5',
    reminderPad: 'px-6 md:px-12 py-6',
    reminderText: 'Recuerda conectarte puntual y estando en un lugar tranquilo y cómodo.',
    reminderTextClass: 'text-center font-medium text-xl md:text-[24px] leading-[1.1]',

    paso3Badge: 'Paso 3 • Descubre',
    paso3BadgeIcon: null,
    paso3TitlePre: 'Descubre más acerca de la oportunidad de ',
    paso3TitleAccent: 'hablar inglés con fluidez',
    paso3Subtitle:
      'Disfruta de este vídeo donde revelamos más datos, errores comunes y falsas creencias acerca del aprendizaje del inglés.',
    paso3SubtitleAccent: 'Además te enseñaremos nuestra academia por dentro',
    paso3Thumbnail: confStep3Thumb,
    paso3PlayIcon: confPlay,
    paso3Video: 'https://youtu.be/Z45XDlhS_Is',
    paso3SectionPad: 'pt-6 pb-12',
    paso3BadgeMb: 'mb-5',
    paso3TitleSize: 'text-3xl md:text-[48px]',
    paso3TitleLeading: 'leading-[1.1]',
    paso3TitleMb: 'mb-5',
    paso3TitleMaxW: 'max-w-[768px]',
    paso3SubtitleMaxW: 'max-w-[560px]',
    paso3SubtitleClass: 'text-white text-base font-light leading-[1.25]',
    paso3SubtitleAccentClass: 'text-base font-light leading-[1.25] inline-block',
    paso3SubtitleMb: 'mb-5',
    paso3SubtitleBlockMb: 'mb-5',
    paso3PlayClass: 'w-8 h-8 md:w-16 md:h-16 lg:w-[102px] lg:h-[102px]',
    paso3ThumbFilter: 'brightness(0.65) blur(3px)',

    footerMode: 'minimal',
    footerPadY: 'py-8',
    footerLogoHeight: 'h-[37px] md:h-[106px] w-auto',
    footer: {
      contactPhone: '+971 58 848 2637',
      contactEmail: 'admisiones@conquerx.com',
      copyrightBrand: 'Conquer Languages',
    },
  },

  // Fondo de página paperboard (usado por el StepForm), igual que Blocks/Legal.
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
    gridBackground,
    pixels: { deco: pixelDeco, deco2: pixelDeco2, sm7: pixelDeco, lg8: pixelDeco2 },
    bulletIcons: [bulletIcon1, bulletIcon2, bulletIcon3],
    instructorMask,
    instructorMaskBottom, // borde pixelado abajo (móvil); el derecho es desktop
    instructorPhoto,
    // La foto de Andy es cuadrada (700×700) y viene "alejada", igual que la de
    // Legal: se pinta como background del cuadro con zoom y punto focal.
    instructorBgSize: '135%',
    instructorBgPosition: '50% 15%',
  },

  layout: {
    navBg: 'bg-transparent',
    navLogoFilter: '',
    footerBg: 'bg-[#0A0A0A]',
    footerText: 'text-gray-400',
    footerAccent: 'text-cyan-400 hover:text-cyan-300',
  },

  // Tokens neutros del paperboard (idénticos a conquerblocks/conquerlegal:
  // fondo crema, tarjetas grises, borde arena, tinta casi negra). El color de
  // marca va por `accent`, no por estos tokens — salvo el dorado de los checks,
  // que es propio de Languages.
  landing: {
    contentWidth: '1024px',
    logoHeight: '39px',
    // 4 racimos de píxeles (2 izq / 2 der, escalonados) como Blocks y Legal.
    decoPixels: ['top-[-70px] left-[8%]', 'top-[270px] right-[12%]', 'top-[830px] right-[20%]', 'top-[1140px] left-[24%]'],
    bg: 'bg-[#F5EDE3]',
    dotPattern: '',
    ambientGlow: 'hidden',
    logoFilter: '',
    logoFallbackText: 'text-gray-900',
    hero: {
      // Literal a propósito: Tailwind genera las clases escaneando el código en
      // build time, así que un `from-[${VAR}]` interpolado no produciría ningún
      // CSS. Los hex son los mismos que CL_TEAL_DARK / CL_TEAL_LIGHT.
      subtitle: 'bg-gradient-to-r from-[#3E7F92] to-[#8FD4E3] bg-clip-text text-transparent',
      title: 'text-gray-900',
      description: 'text-gray-600',
    },
    bullets: {
      // Sistema paperboard: icono 48px como Conquer Blocks (Legal lo sube a 64),
      // <strong> en 700. El check dorado (#E0A52E) es el de la landing vieja de
      // Languages y solo se usa en el renderer no-paperboard.
      iconSize: '48px',
      strongWeight: '700',
      checkBg: 'bg-amber-100',
      checkIcon: 'text-[#E0A52E]',
      text: 'text-gray-700',
    },
    form: {
      card: 'border-gray-200/50 shadow-lg',
      badge: 'bg-cyan-100 text-cyan-700',
      badgeDot: 'bg-[#70B3C4]',
      title: 'text-gray-900',
      input: 'border-gray-300 bg-white text-gray-900 placeholder:text-gray-400 focus:border-[#70B3C4] focus:ring-1 focus:ring-[#70B3C4]/20',
      inputError: 'border-red-400 bg-red-50',
      button: 'shadow-lg shadow-cyan-500/20',
      consent: 'text-gray-500',
      consentLink: 'text-[#4A96AA]',
      trustText: 'text-gray-400',
      trustDivider: 'bg-gray-300',
    },
    instructor: {
      card: 'border-gray-200/50 shadow-lg',
      ring: 'ring-cyan-300',
      name: 'text-[#4A96AA]',
      role: 'text-gray-500',
      description: 'text-gray-600 [&_strong]:text-gray-900 [&_strong]:font-semibold',
    },
    footer: {
      text: 'text-gray-700',
      disclaimer: 'text-gray-600',
      accent: 'text-[#4A96AA] font-bold',
      link: 'text-gray-700',
    },
  },

  cssVars: {
    '--theme-page-bg': '#F5EDE3',
    '--theme-accent': CL_TEAL,
    '--theme-accent-hover': CL_TEAL_DARK,
    '--theme-accent-bg': '#EFF8FA',
    '--theme-accent-text': '#ffffff',
    '--theme-accent-ring': 'rgba(112,179,196,0.3)',
    '--theme-form-bg': 'rgba(255, 255, 255, 0.6)',
    '--theme-form-border': '#BBB49B',
    '--theme-form-texture': `url(${paperboardTexture})`,
    '--theme-btn-gradient': CL_GRADIENT,
    '--theme-form-shadow': clShadow,
  },
}
