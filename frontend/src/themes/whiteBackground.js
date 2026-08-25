/* Variante de fondo blanco del A/B de diseño (Blocks LATAM/US, Languages y
   Finance LATAM). Devuelve una copia del tema en la que el fondo de papel
   (paperboard) pasa a blanco liso en TODAS las etapas del funnel: landing,
   vídeo, stepform, calendario/reserva y confirmación. Es un test de fondo, no
   de layout: no toca acentos, bordes, sombras ni tipografía, solo el papel.

   El papel se pinta desde cuatro sitios distintos y hay que apagar los cuatro:

   1. `assets.paperboardTexture`, con un `? :` alrededor en casi todos los
      consumidores, así que ponerlo a null basta para que caigan al fondo liso.
   2. `page` y las CSS vars `--theme-page-bg` / `--theme-form-bg` /
      `--theme-form-texture`, que visten el wrapper y la tarjeta del StepForm y,
      vía funnel.css, la pantalla de rechazo.
   3. `confirmation.texture`, que en Blocks es una textura propia (más clara que
      la del StepForm) y por eso NO cae al anular la del tema.
   4. Colores de papel escritos literales en el JSX o el CSS: los conmutan
      Landing, BulletPoints, VideoPage, Confirmation y MultipleChoice mirando la
      bandera `whiteBackground`, y el calendario reutilizando su clase
      `bk-wrapper--plain`, la misma que ya usaba Finance. */

const WHITE = '#FFFFFF'

export function toWhiteBackground(theme) {
  if (!theme) return theme
  return {
    ...theme,
    whiteBackground: true,
    // Sin textura, todos los `assets?.paperboardTexture ? ... : undefined` de la
    // landing y del vídeo caen solos al fondo liso.
    assets: { ...(theme.assets || {}), paperboardTexture: null },
    landing: { ...(theme.landing || {}), bg: 'bg-white' },
    // Wrapper del StepForm: color liso, sin la imagen de papel.
    page: { backgroundColor: WHITE },
    cssVars: {
      ...(theme.cssVars || {}),
      '--theme-page-bg': WHITE,
      // La tarjeta del formulario es un velo blanco translúcido SOBRE el papel;
      // sin papel debajo, se deja opaca para que no se vea gris.
      '--theme-form-bg': WHITE,
      '--theme-form-texture': 'none',
    },
    ...(theme.confirmation
      ? { confirmation: { ...theme.confirmation, texture: null } }
      : {}),
  }
}
