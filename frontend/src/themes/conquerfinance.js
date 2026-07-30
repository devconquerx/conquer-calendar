// Tema Conquer Finance — réplica de las páginas de producción de
// www.conquerfinance.com (Webflow "conversion-flow"): fondo blanco con patrón
// hexagonal, acento azul (#1e4bb4) y tipografías Poppins (cuerpo/títulos),
// Oswald (eyebrows condensados) y Montserrat (CTAs). A diferencia de
// Blocks/Legal (paperboard), Finance usa el sistema de diseño "hexboard":
// los renderers hex de Landing/VideoPage/Confirmation leen estos tokens.
import logo from '../assets/img/finance/logo.svg'
import logoInverted from '../assets/img/finance/logo-inverted.svg'
// Favicon de marca: mismo PNG que sirve conquerfinance.com. FunnelApp lo
// inyecta en <head> en runtime para todas las etapas del funnel de Finance.
import favicon from '../assets/img/finance/favicon.png'
import hexBackground from '../assets/img/finance/hex-bg.svg'
import checkIcon from '../assets/img/finance/check.svg'
// Triángulo gris (Polygon 2.png de producción): muescas entre secciones de la
// confirmación (blanco vía brightness(2) arriba de la sección gris, gris abajo).
import notchTriangle from '../assets/img/finance/notch-triangle.png'
import instructorPhoto from '../assets/img/finance/felix.avif'
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

export default {
  id: 'conquerfinance',
  // Sistema de diseño de Finance: blanco + patrón hexagonal + acento azul.
  hexboard: true,

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
    subtitle: '· VÍDEO DE 15 MINUTOS ·',
    title:
      '<strong>Genera un sueldo mensual</strong> gracias al Trading <strong>en menos de 7 semanas</strong>, sin invertir tu propio capital',
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
