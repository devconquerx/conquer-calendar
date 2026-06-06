/** @type {import('tailwindcss').Config} */
export default {
  content: [
    './src/**/*.{js,jsx}',
  ],
  theme: {
    extend: {
      fontFamily: {
        funnel: ['"Funnel Display"', 'Arial', 'sans-serif'],
      },
      colors: {
        // Paleta de la landing de producción (Conquer Blocks)
        cb: {
          bg: '#FAFAFA',     // fondo de página (casi blanco)
          card: '#F6F6F6',   // fondo de tarjetas
          line: '#BBB49B',   // borde arena
          ink: '#0A0A0A',    // texto principal hero
          ink2: '#171717',   // texto instructor/footer
        },
      },
      boxShadow: {
        // Sombra suave en capas de las tarjetas de producción
        'cb-card': '0 1px 0.4px rgba(0,0,0,0.03), 0 2px 0.8px rgba(0,0,0,0.04), 0 3.4px 1.6px rgba(0,0,0,0.043), 0 5.4px 2.9px rgba(0,0,0,0.047), 0 8.9px 5.3px rgba(0,0,0,0.047), 0 15.4px 10.4px rgba(0,0,0,0.05), 0 30.6px 22.8px rgba(0,0,0,0.055)',
      },
      animation: {
        'fade-in': 'fadeIn 0.5s ease-out',
        aurora: 'auroraShadow 6s ease infinite',
      },
      keyframes: {
        fadeIn: {
          '0%': { opacity: '0', transform: 'translateY(10px)' },
          '100%': { opacity: '1', transform: 'translateY(0)' },
        },
        auroraShadow: {
          '0%': { backgroundPosition: '0% 50%' },
          '50%': { backgroundPosition: '100% 50%' },
          '100%': { backgroundPosition: '0% 50%' },
        },
      },
    },
  },
  plugins: [],
}
