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

const cbShadow =
  '0px 2px 5px rgba(0,0,0,0.1), 0px 9px 9px rgba(0,0,0,0.09), 0px 20px 12px rgba(0,0,0,0.05), 0px 36px 14px rgba(0,0,0,0.01)'

// Sombra suave en capas de las tarjetas de producción (copiada del box-shadow real).
export const CB_CARD_SHADOW =
  '0 1px 0.4px rgba(0,0,0,0.03), 0 2px 0.8px rgba(0,0,0,0.04), 0 3.4px 1.6px rgba(0,0,0,0.043), 0 5.4px 2.9px rgba(0,0,0,0.047), 0 8.9px 5.3px rgba(0,0,0,0.047), 0 15.4px 10.4px rgba(0,0,0,0.05), 0 30.6px 22.8px rgba(0,0,0,0.055)'

export default {
  id: 'conquerblocks',

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
    '--theme-form-bg': 'rgba(255, 255, 255, 0.6)',
    '--theme-form-border': '#BBB49B',
    '--theme-form-texture': `url(${paperboardTexture})`,
    '--theme-btn-gradient': 'linear-gradient(to right, #FFBF00, #FF4000)',
    '--theme-form-shadow': cbShadow,
  },
}
