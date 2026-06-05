import paperboardTexture from '../assets/img/cb/paperboard-texture.avif'
import ctaButtonBg from '../assets/img/cb/cta-button-bg.png'

const cbShadow =
  '0px 2px 5px rgba(0,0,0,0.1), 0px 9px 9px rgba(0,0,0,0.09), 0px 20px 12px rgba(0,0,0,0.05), 0px 36px 14px rgba(0,0,0,0.01)'

export default {
  id: 'conquerblocks',

  // Applied to the page wrapper (cream paperboard background, fixed)
  page: {
    backgroundColor: '#F5EDE3',
    backgroundImage: `url(${paperboardTexture})`,
    backgroundSize: 'cover',
    backgroundPosition: 'center',
    backgroundAttachment: 'fixed',
  },

  assets: {
    paperboardTexture,
    ctaButtonBg,
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
