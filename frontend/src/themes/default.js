// Neutral fallback theme — usado por marcas sin tema propio (languages/finance).
// Mantiene `page` (fondo blanco) para el StepForm y añade los tokens `landing`
// (tema oscuro teal de funnels) para la landing de registro de lead.
export default {
  id: 'default',

  page: {
    backgroundColor: '#ffffff',
  },

  assets: {},

  layout: {
    navBg: 'bg-white border-b border-gray-200',
    navLogoFilter: '',
    footerBg: 'bg-gray-50 border-t border-gray-200',
    footerText: 'text-gray-500',
    footerAccent: 'text-gray-500 hover:text-gray-800',
  },

  landing: {
    bg: 'bg-gradient-to-br from-slate-950 via-slate-900 to-slate-950',
    dotPattern: 'bg-[radial-gradient(circle_at_1px_1px,rgba(255,255,255,0.04)_1px,transparent_0)] bg-[size:32px_32px]',
    ambientGlow: 'bg-teal-500/[0.07]',
    logoFilter: 'brightness-0 invert',
    logoFallbackText: 'text-white',
    hero: {
      subtitle: 'bg-gradient-to-r from-cyan-400 via-teal-300 to-emerald-400 bg-clip-text text-transparent',
      title: 'text-white [&_strong]:text-teal-400',
      description: 'text-slate-400',
    },
    bullets: {
      checkBg: 'bg-teal-500/20',
      checkIcon: 'text-teal-400',
      text: 'text-slate-300',
    },
    form: {
      card: 'bg-white/[0.07] backdrop-blur-xl border-white/[0.12] shadow-2xl shadow-black/20',
      badge: 'bg-teal-500/15 text-teal-300',
      badgeDot: 'bg-teal-400',
      title: 'text-white',
      input: 'border-white/15 bg-white/[0.07] text-white placeholder:text-slate-400 focus:border-teal-400/60 focus:bg-white/10',
      inputError: 'border-red-400/60 bg-red-500/10',
      button: 'bg-gradient-to-r from-teal-500 to-emerald-500 hover:from-teal-400 hover:to-emerald-400 shadow-lg shadow-teal-500/30',
      consent: 'text-slate-500',
      consentLink: 'text-teal-400',
      trustText: 'text-slate-500',
      trustDivider: 'bg-slate-700',
    },
    instructor: {
      card: 'bg-white/[0.06] backdrop-blur-sm border-white/10',
      ring: 'ring-teal-500/30',
      name: 'text-teal-400',
      role: 'text-slate-400',
      description: 'text-slate-300 [&_strong]:text-white [&_strong]:font-semibold',
    },
    footer: {
      text: 'text-slate-600',
      disclaimer: 'text-slate-500',
      accent: 'text-teal-500',
      link: 'text-slate-500',
    },
  },

  cssVars: {},
}
