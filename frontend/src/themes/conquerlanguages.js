import defaultTheme from './default'

// Languages no tiene sistema de diseño propio todavía: hereda el tema neutro
// (`default`) tal cual. Este archivo existe solo para poder colgarle flags de
// MARCA sin tocar `default.js` (que además comparten otras marcas futuras).
export default {
  ...defaultTheme,
  id: 'conquerlanguages',

  // El contenedor GTM de Languages (heredado de Webflow) dispara el Schedule
  // con el trigger "page load en *confirmacion-llamada*", así que el
  // StepForm debe navegar a la confirmación con recarga real, no pushState —
  // mismo fix que Finance/Blocks (ver conquerfinance.js). Flag de MARCA: no
  // toca el GTM en vivo, solo cambia cómo conquer-calendar navega en su
  // propio flujo.
  gtmHardConfirmation: true,
}
