/* Variante de fondo blanco (A/B de Conquer Blocks LATAM, variante 58).
   Devuelve una copia del tema en la que el fondo de papel (paperboard) de la
   LANDING pasa a blanco liso. Solo afecta a la landing: el resto de etapas del
   funnel (vídeo, stepform, calendario y confirmación) conservan su papel, así
   que este tema no se aplica ahí.

   Quitar la textura basta para casi todo, porque los fondos de la landing salen
   de `assets.paperboardTexture` con un `? :` alrededor; los dos colores de papel
   escritos literales en el JSX (página #FAFAFA vía `bg-cb-bg` y tarjetas
   #F6F6F6) los conmutan Landing y BulletPoints mirando la bandera
   `whiteBackground`. No toca acentos, bordes, sombras ni tipografía: solo el
   papel. */

const WHITE = '#FFFFFF'

export function toWhiteBackground(theme) {
  if (!theme) return theme
  return {
    ...theme,
    whiteBackground: true,
    // Sin textura, todos los `assets?.paperboardTexture ? ... : undefined` de la
    // landing caen solos al fondo liso.
    assets: { ...(theme.assets || {}), paperboardTexture: null },
    landing: { ...(theme.landing || {}), bg: 'bg-white' },
  }
}
