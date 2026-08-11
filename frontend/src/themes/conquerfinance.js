// Tema Conquer Finance — réplica de las páginas de producción de
// www.conquerfinance.com (Webflow "conversion-flow"): fondo blanco con patrón
// hexagonal, acento azul (#1e4bb4) y tipografías Poppins (cuerpo/títulos),
// Oswald (eyebrows condensados) y Montserrat (CTAs). A diferencia de
// Blocks/Legal (paperboard), Finance usa el sistema de diseño "hexboard":
// los renderers hex de Landing/VideoPage/Confirmation leen estos tokens.
// Logo oficial nuevo de marca (2026-08-11, entregado por el usuario): wordmark
// "CONQUER" negro + "Finance" en estilo pegatina/recortado con borde blanco —
// sustituye al lockup azul anterior en TODAS las etapas/regiones del funnel
// (landing, vídeo, stepform, confirmación comparten este tema).
import logo from '../assets/img/finance/logo-horizontal.png'
// `logoInverted` (blanco, para fondos oscuros) sigue siendo el lockup azul
// viejo: el usuario solo entregó la versión negra. Sin impacto visible hoy —
// las 4 etapas renderizan paperboard (fondos claros); esta variante solo la
// usaría el renderer hexboard (navbar oscura), que es fallback muerto en la
// práctica. Si se reactiva el hexboard, pedir también un logo blanco.
import logoInverted from '../assets/img/finance/logo-inverted.svg'
// Favicon de marca: mismo PNG que sirve conquerfinance.com. FunnelApp lo
// inyecta en <head> en runtime para todas las etapas del funnel de Finance.
import favicon from '../assets/img/finance/favicon.png'
import hexBackground from '../assets/img/finance/hex-bg.svg'
import checkIcon from '../assets/img/finance/check.svg'
// Triángulo gris (Polygon 2.png de producción): muescas entre secciones de la
// confirmación (blanco vía brightness(2) arriba de la sección gris, gris abajo).
import notchTriangle from '../assets/img/finance/notch-triangle.png'
// Foto oficial nueva de Félix (2026-08-11, entregada por el usuario): ya
// compuesta con el fondo verde de marca + icono decorativo — se muestra tal
// cual (cover/center), no necesita el tratamiento de headshot en bruto que
// llevaba la anterior.
import instructorPhoto from '../assets/img/finance/felix-nuevo.avif'
import pressRadio from '../assets/img/finance/press-radiointereconomia.avif'
import pressReferente from '../assets/img/finance/press-elreferente.avif'
import pressBolsamania from '../assets/img/finance/press-bolsamania.avif'
import pressEae from '../assets/img/finance/press-eae.avif'
import pressInvesting from '../assets/img/finance/press-investing.avif'
// Assets propios de la confirmación (descargados de producción y convertidos
// a AVIF ligero con sharp; producción sirve los originales pesados). El thumb
// del PASO 3 ya trae el botón de play incrustado en el JPG original.
import confPhone52 from '../assets/img/finance/confirmation/phone-52.avif'
import confPaso3Thumb from '../assets/img/finance/confirmation/paso3-thumb.avif'
// Fondo hexagonal de página completa de la confirmación (Fondo hexagonos 2.avif
// de producción, background del <body> con size contain).
import confHexFondo from '../assets/img/finance/hex-fondo.avif'
// Frames estáticos de los Lottie de producción (felicidades.json = confeti;
// Animation-1713274047756.json = doble chevron), serializados a SVG con
// lottie-web. Producción los anima; aquí frame fijo + CSS bounce en el chevron.
import confConfetti from '../assets/img/finance/confirmation/confetti.svg'
import confDoubleChevron from '../assets/img/finance/confirmation/double-chevron.svg'
// Rediseño 2026: los funnels de Finance migran página a página al sistema
// "paperboard" de Conquer Legal. Mientras dure la transición se toman prestados
// los tokens/assets de Legal tal cual (colores incluidos); la paleta propia de
// Finance llegará después.
import legal from './conquerlegal'
// Mockup de llamada entrante de la confirmación de Blocks: en el rediseño
// paperboard, Finance lo usa tal cual en su Paso 2 (como los tokens de Legal,
// hasta que exista una versión con la marca Finance).
import confMockupBlocks from '../assets/img/cb/confirmation/conquer-mockup.png'
// Conquie de fiesta (el "emoji de celebración" del hero de Blocks): decisión
// del usuario 2026-08-10 — sustituye al apretón de manos de Legal.
import confFiestaBlocks from '../assets/img/cb/confirmation/conquie-fiesta.svg'
// Píxeles decorativos en verde: los SVG de Legal (gradiente #00C0FF→#0040FF)
// recoloreados con la marca Finance (#AED916→#3AC043).
import pxGreen6 from '../assets/img/finance/pixel-6x6-green.svg'
import pxGreen5 from '../assets/img/finance/pixel-5x5-green.svg'
import pxGreenLg8 from '../assets/img/finance/px-lg-8-green.svg'
import pxGreenSm7 from '../assets/img/finance/px-sm-7-green.svg'

// ── Paleta propia de Finance (2026-08-10, Figma "Gradiente Conquer") ──
// Cartuso #AED916 · Lima #74CD2D · Esmeralda #3AC043. El gradiente de marca va
// de cartuso a esmeralda; en botones se añade lima como parada intermedia.
// OJO: en las clases Tailwind de abajo los hex van LITERALES (el JIT escanea el
// texto del archivo; un template string no generaría la clase).
const FI_GRADIENT = 'linear-gradient(90deg, #AED916 0%, #74CD2D 50%, #3AC043 100%)'
const FI_TEXT_GRADIENT = 'linear-gradient(90deg, #AED916, #3AC043)'

const paperAccent = {
  strongGradient: FI_TEXT_GRADIENT,
  auroraGradient: 'linear-gradient(60deg,#AED916,#3AC043,#AED916,#3AC043)',
  buttonGradient: FI_GRADIENT,
  buttonWeight: '800',
  linkGradient: 'linear-gradient(to right,#AED916,#3AC043)',
  ring: '#74CD2D',
  solid: '#3AC043',
}

// Mismo mapeo que los píxeles de Legal (deco/sm7 = cluster 6x6, deco2/lg8 = 5x5).
const paperPixels = {
  deco: pxGreen6,
  deco2: pxGreen5,
  sm7: pxGreen6,
  lg8: pxGreen5,
  pxLg8: pxGreenLg8,
  pxSm7: pxGreenSm7,
}

// CSS vars del StepForm y del calendario de agendamiento: el paperboard neutro
// (fondo, tarjeta, textura, sombra) se hereda de Legal; el acento pasa a verde.
// funnel.css mapea --bk-accent* ← --theme-accent* → el calendario se tiñe solo.
const paperCssVars = {
  ...legal.cssVars,
  '--theme-accent': '#3AC043',
  '--theme-accent-hover': '#2FA83A',
  '--theme-accent-bg': '#EFF8DC',
  '--theme-accent-ring': 'rgba(116,205,45,0.3)',
  '--theme-btn-gradient': FI_GRADIENT,
}

// Copy por defecto de la página de vídeo (compartido entre el renderer hexboard
// y el override paperboard). En la práctica lo pisa config['video'] de la BD.
const VIDEO_SUBTITLE = '· VÍDEO DE 15 MINUTOS ·'
const VIDEO_TITLE =
  '<strong>Genera un sueldo mensual</strong> gracias al Trading <strong>en menos de 7 semanas</strong>, sin invertir tu propio capital'

export default {
  id: 'conquerfinance',
  // Sistema de diseño de Finance: blanco + patrón hexagonal + acento azul.
  hexboard: true,

  // El contenedor GTM de Finance (heredado de Webflow) dispara el Schedule con
  // el trigger "page load en *confirmacion-llamada*", así que el StepForm debe
  // navegar a la confirmación con recarga real, no pushState. Es un flag de
  // MARCA (no de sistema de diseño): sobrevive a la migración paperboard.
  gtmHardConfirmation: true,

  // Rediseño por página: TODAS las etapas (landing, vídeo, stepform y
  // confirmación) usan ya el sistema paperboard (Legal). El flag `hexboard`
  // sigue arriba solo como fallback si se retira una variante. Landing.jsx
  // fusiona `landingPaper`, VideoPage.jsx `videoPaper`, Funnel.jsx
  // `stepformPaper` y Confirmation.jsx `confirmationPaper` al renderizar.
  landingVariant: 'paperboard',
  landingPaper: {
    accent: paperAccent,
    // Estructura/medidas de Legal + acentos en verde Finance (solo cambian los
    // tokens que llevaban azul).
    landing: {
      ...legal.landing,
      hero: {
        ...legal.landing.hero,
        subtitle: 'bg-gradient-to-r from-[#AED916] to-[#3AC043] bg-clip-text text-transparent',
      },
      bullets: {
        ...legal.landing.bullets,
        checkBg: 'bg-[#EFF8DC]',
        checkIcon: 'text-[#3AC043]',
      },
      form: {
        ...legal.landing.form,
        badge: 'bg-[#EFF8DC] text-[#2FA83A]',
        badgeDot: 'bg-[#74CD2D]',
        input: 'border-gray-300 bg-white text-gray-900 placeholder:text-gray-400 focus:border-[#74CD2D] focus:ring-1 focus:ring-[#74CD2D]/20',
        button: 'bg-gradient-to-r from-[#AED916] to-[#3AC043] hover:from-[#B9E52A] hover:to-[#45CC4F] shadow-lg shadow-[#3AC043]/20',
        consentLink: 'text-[#3AC043]',
      },
      instructor: {
        ...legal.landing.instructor,
        ring: 'ring-[#74CD2D]',
        name: 'text-[#3AC043]',
      },
      footer: {
        ...legal.landing.footer,
        accent: 'text-[#3AC043] font-bold',
      },
    },
    assets: {
      ...legal.assets,
      logo,
      instructorPhoto,
      pixels: paperPixels,
      // La foto ya viene compuesta (fondo + icono decorativo propios): se
      // muestra completa, sin recorte de encuadre tipo headshot.
      instructorBgSize: 'cover',
      instructorBgPosition: 'center',
      instructorBgPositionX: '-22px',
    },
  },

  stepformVariant: 'paperboard',
  stepformPaper: {
    accent: paperAccent,
    // Fondo de página crema + tarjeta con textura/borde arena/sombra de Legal.
    // Al tomar los cssVars completos desaparecen los overrides hex de botón
    // (`--theme-btn-clip: none` / radio 10 negro) → los botones del form
    // recuperan el clip pixelado, ahora con el gradiente verde de Finance.
    // `paperCssVars` también tiñe el calendario de agendamiento (--bk-accent*).
    page: legal.page,
    cssVars: paperCssVars,
    assets: {
      ...legal.assets,
      logo,
      pixels: paperPixels,
    },
  },

  videoVariant: 'paperboard',
  videoPaper: {
    accent: paperAccent,
    video: {
      ...legal.video,
      // El copy sigue siendo el de Finance (config['video'] de la BD lo pisa;
      // esto es solo el fallback). Los tokens visuales quedan los de Legal,
      // con el glow del player en verde de marca.
      subtitle: VIDEO_SUBTITLE,
      title: VIDEO_TITLE,
      glow: '0 2px 20px 6px rgba(116,205,45,0.35)',
      // Finance conserva su arranque de producción: autoplay muted + overlay de
      // "activar sonido" (Legal sí arranca con sonido tras el submit).
      autoplayUnmuted: false,
      // El logo de Finance es horizontal (el de Legal es un lockup vertical):
      // mismos anchos que usaba la navbar hex.
      headerLogoWidth: '180px',
      headerLogoWidthMobile: '140px',
      footerLogoWidth: '240px',
    },
    assets: {
      ...legal.assets,
      logo,
      pixels: paperPixels,
    },
  },

  confirmationVariant: 'paperboard',
  confirmationPaper: {
    accent: paperAccent,
    // Diseño de Legal completo (texturas, rasgados, cajas, ritmo medido 1:1,
    // conquies incluidos por ahora) + CONTENIDO de Finance: los 3 pasos con su
    // vídeo Bunny, su mensaje de teléfono y su entrevista de YouTube. Los
    // acentos de color pasan al verde de marca.
    confirmation: {
      ...legal.confirmation,
      heroIcon: confFiestaBlocks,
      heroTitle: 'Tu llamada ha sido reservada',
      felicidadesGradient: FI_TEXT_GRADIENT,
      accentGradient: FI_TEXT_GRADIENT,
      // Caja "Importante"/recordatorio: el PNG azul de Legal se sustituye por
      // el gradiente de marca (el renderer usa boxGradient si boxImage es null).
      boxImage: null,
      boxGradient: 'linear-gradient(120deg, #AED916 0%, #3AC043 100%)',
      // Marco de los vídeos: sin esto el VideoFrame caería al glow azul por
      // defecto (el borde ya sale de accent.ring = lima).
      videoGlow: '0 0 30px rgba(116,205,45,0.30)',
      heroDecoImg: pxGreen6,
      importanteText: 'Completa estos 3 pasos ahora para poder aprovechar tu llamada al máximo.',
      // El logo de Finance es horizontal (~9.5:1): las alturas de Legal (39/88px,
      // pensadas para su lockup vertical) lo desbordarían. Anchos equivalentes a
      // los de las páginas ya migradas (180px navbar / 240px footer).
      navLogoHeight: 'h-[19px] md:h-[24px] w-auto',
      footerLogoHeight: 'h-[19px] md:h-[25px] w-auto',
      // PASO 1 — el vídeo corto de Finance (Bunny, 56s).
      paso1Text: 'Mira este vídeo de 56 segundos para entender tus siguientes pasos lógicos',
      paso1TextBold: 'Mira este vídeo',
      paso1Video:
        'https://iframe.mediadelivery.net/embed/185796/541cbc1b-c3e8-4081-bb8d-a2a40ce950fe?autoplay=false&loop=false&muted=false&preload=true&responsive=true',
      // PASO 2 — copy de Finance (el renderer paperboard pinta los párrafos como
      // texto plano, así que van sin <strong>; el titular de la tarjeta ya es
      // "Mantente al tanto de tu teléfono", heredado de Legal palabra a palabra).
      // Mockup de llamada entrante de Blocks (decisión del usuario 2026-08-10):
      // a sangre completa con la máscara pixelada, como en la confirmación de
      // conquerblocks.com — sustituye al phone-52 del hex, que recortaba mal.
      paso2Image: confMockupBlocks,
      paso2Paragraphs: [
        'Te contactaremos por llamada para confirmar la cita el día y la hora acordadas. Una vez confirmada la sesión con tu asesor te enviaremos el enlace de la videollamada.',
        'Es importante que contestes confirmando 👍 tu llamada, ya que estamos recibiendo muchísimas solicitudes y queremos hablar con personas que estén comprometidas en ser un caso de éxito.',
      ],
      reminderText: 'Recuerda conectarte puntual y estando en un lugar tranquilo y cómodo.',
      // PASO 3 — la entrevista de cuentas fondeadas (el acento en gradiente lo
      // pone el renderer sobre `paso3TitleAccent`).
      paso3TitlePre: 'Descubre más acerca de la oportunidad de convertirte en ',
      paso3TitleAccent: 'trader de cuentas fondeadas',
      paso3Subtitle:
        'Disfruta de una entrevista donde revelamos más datos, errores comunes y falsas creencias acerca del trading con cuentas fondeadas',
      paso3SubtitleAccent: 'Ver al menos 30 minutos te ayudará a llegar mucho más preparado a la llamada :)',
      paso3Thumbnail: confPaso3Thumb,
      paso3Video: 'https://www.youtube.com/watch?v=8cGtPi7qnkQ',
    },
    assets: {
      ...legal.assets,
      logo,
      pixels: paperPixels,
    },
  },

  favicon,

  // Acento de marca (azul Finance). El CTA sólido de la landing es #1e4bb4;
  // el CTA de la página de vídeo es el gradiente de producción (cf-video.css).
  accent: {
    strongGradient: 'linear-gradient(95deg,#1c48b0,#5e94ff)',
    buttonGradient: 'linear-gradient(95deg, #1c48b0 36%, #5e94ff)',
    buttonWeight: '800',
    linkGradient: 'linear-gradient(to right,#1c48b0,#5e94ff)',
    ring: '#1e4bb4',
    solid: '#1e4bb4',
  },

  footer: {
    copyrightBrand: 'ConquerX',
    contactEmail: 'contacto@conquerfinance.com',
    legal: {
      cookies: 'https://www.conquerfinance.com/politica-de-cookies',
      privacy: 'https://www.conquerfinance.com/politica-de-privacidad',
      terms: 'https://www.conquerfinance.com/terminos-y-condiciones',
    },
  },

  // Landing hex — medidas del CSS de Webflow (conquerfinance.webflow.shared.css):
  //   .cf-time-vsl   → Oswald 300 24px (18px móvil), color #2827d6
  //   .cf-h1-vsl     → Poppins 400 25px lh130%, negro, <strong> en 700
  //   .cf-subtitle-vsl → Poppins 500 17px
  //   bullets        → Poppins 400 17px #000c + Checkbox-fi-line.svg
  //   inputs         → blanco, borde rgba(0,0,0,.27), radio 20px
  //   botón          → #1e4bb4, radio 20px, Montserrat 800, sombra azul
  landing: {
    contentWidth: '1140px',
    logoHeight: '40px',
    eyebrowColor: '#2827d6',
    accentText: '#1c48af',
    inputBorder: 'rgba(0,0,0,0.27)',
    buttonBg: '#1e4bb4',
    buttonHoverBg: '#2c58c2',
    buttonShadow: 'rgba(0,47,255,0.23) -1px 8px 5px -3px',
    privacyLinkColor: '#73bac8',
    pressTitle: 'Nos has visto en...',
    pressLogos: [pressRadio, pressReferente, pressBolsamania, pressEae, pressInvesting],
  },

  // Página de vídeo (VSL) — réplica de /video-clase-latam (cf-video.css):
  // body #333, navbar transparente con borde inferior #4f4f4f y logo invertido,
  // kicker Oswald #345bb8, H1 Montserrat 300 30px blanca, player con glow azul
  // y CTA en gradiente pill (85px). El copy puede sobreescribirse por
  // config['video'] (subtitle/title).
  video: {
    subtitle: VIDEO_SUBTITLE,
    title: VIDEO_TITLE,
    pageBg: '#333333',
    navBorder: '#4f4f4f',
    kickerColor: '#345bb8',
    glow: '0 2px 20px 6px rgba(127,193,255,0.28)',
    headerLogoWidth: '180px',
    headerLogoWidthMobile: '140px',
    // Igual que producción: el vídeo arranca con autoplay muted + overlay de
    // "activar sonido" (Finance NO usa autoplayUnmuted como Legal).
  },

  // Confirmación — réplica 1:1 de /confirmacion-llamada (medida en prod):
  //   navbar 70px (75 móvil) + confeti Lottie + ¡Felicidades! Ms Madi 73px
  //   (66 móvil) + "Tu llamada..." Poppins 900 30px (26 móvil); banner
  //   gradiente (90deg,#1c48af 14%,#2e6cff) con "Importante:" en #f65252;
  //   pasos Poppins 900 30px (20 móvil) — el 1 y el 3 en #1c48b0, el 2 en
  //   #345bb8; muescas triangulares entre secciones. Producción NO tiene
  //   PASO 4 ni footer: la página termina tras el vídeo del PASO 3.
  confirmation: {
    felicidades: '¡Felicidades!',
    heroTitle: 'Tu llamada ha sido reservada',
    importanteLabel: 'Importante:',
    importanteLabelColor: '#f65252',
    importanteText: 'completa estos 3 pasos ahora para poder aprovechar tu llamada al máximo',
    importanteTextBold: '3 pasos',
    bannerGradient: 'linear-gradient(90deg, #1c48af 14%, #2e6cff)',
    stepColor: '#1c48b0',
    step2Color: '#345bb8',
    paso1Badge: 'PASO 1 · Mira este vídeo',
    paso1Text: 'Mira este vídeo de 56 segundos para entender tus siguientes pasos lógicos',
    paso1TextBold: 'Mira este vídeo',
    paso1Video:
      'https://iframe.mediadelivery.net/embed/185796/541cbc1b-c3e8-4081-bb8d-a2a40ce950fe?autoplay=false&loop=false&muted=false&preload=true&responsive=true',
    paso2Badge: 'PASO 2 · Confirma tu cita',
    paso2Image: confPhone52,
    paso2Paragraphs: [
      '<strong>Mantente al tanto de tu teléfono</strong> porque te contactaremos por llamada para confirmar la cita el día y la hora acordadas, una vez confirmada la sesión con tu asesor <strong>te enviaremos el enlace de la videollamada</strong>.',
      'Es importante que <strong>contestes confirmando 👍</strong> tu llamada, ya que estamos recibiendo muchísimas solicitudes y queremos hablar con personas que estén comprometidas en ser un caso de éxito.',
    ],
    reminderText: 'Recuerda conectarte puntual y estando en un lugar tranquilo y cómodo.',
    reminderTextBold: 'puntual',
    paso3Badge: 'PASO 3 · Descubre más acerca de la oportunidad de convertirte en trader de cuentas fondeadas',
    paso3Subtitle:
      'Disfruta de una entrevista donde revelamos más datos, errores comunes y falsas creencias acerca del trading con cuentas fondeadas',
    paso3Note: 'Ver al menos 30 minutos te ayudará a llegar mucho más preparado a la llamada :)',
    paso3Thumbnail: confPaso3Thumb,
    paso3Video: 'https://www.youtube.com/watch?v=8cGtPi7qnkQ',
  },

  // Fondo del StepForm (QuillForms): blanco, como el form de prellamada de
  // producción (los tokens del form viven en FunnelForm.config.theme).
  page: {
    backgroundColor: '#ffffff',
  },

  assets: {
    logo,
    logoInverted,
    hexBackground,
    checkIcon,
    notchTriangle,
    instructorPhoto,
    confetti: confConfetti,
    doubleChevron: confDoubleChevron,
    confHexFondo,
  },

  layout: {
    navBg: 'bg-white border-b border-gray-200',
    navLogoFilter: '',
    footerBg: 'bg-gray-50 border-t border-gray-200',
    footerText: 'text-gray-500',
    footerAccent: 'text-blue-600 hover:text-blue-800',
  },

  cssVars: {
    '--theme-page-bg': '#ffffff',
    '--theme-accent': '#1e4bb4',
    '--theme-accent-hover': '#2c58c2',
    '--theme-accent-bg': '#f4f7fe',
    '--theme-accent-text': '#ffffff',
    '--theme-accent-ring': 'rgba(118,157,255,0.28)',
    // Botones del StepForm: negro redondeado (tema QuillForms de producción,
    // buttonsBgColor #000 radio 10), sin el clip pixelado de Blocks/Legal.
    '--theme-btn-gradient': '#000000',
    '--theme-btn-clip': 'none',
    '--theme-btn-radius': '10px',
  },
}
