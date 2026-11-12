import { useTheme } from '../../themes'

/* Estilos de los campos del StepForm en el sistema Conquer Lab (Figma:
   Languages · Embudo 1 · Agenda). La respuesta es texto 20/30 sobre una línea
   de 1.5px en tinta; el placeholder en neutral/500. */
export const LAB_INPUT = 'w-full bg-transparent border-b-[1.5px] border-[color:var(--lab-ink)] text-[color:var(--lab-ink)] text-lg leading-7 md:text-xl md:leading-[30px] pt-0 pb-2.5 px-0 outline-none placeholder:text-[color:var(--lab-n500)]'

// true cuando el StepForm se pinta con el Lab (`?diseno=lab`).
export function useIsLab() {
  return useTheme()?.design === 'lab'
}
