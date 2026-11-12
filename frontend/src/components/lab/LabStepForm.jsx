import { LAB_CARD, LabPage, LabLogoBar, LabFooter } from './LabParts'

/* ═══ StepForm "Conquer Lab" ═══
   Réplica de Figma (Languages · Embudo 1 · Agenda): barra con logo sobre papel,
   una tarjeta blanca de 1140 con el paso actual (padding 160/72; la bienvenida
   112 en vertical) y el footer de siempre. El progreso y las flechas van DENTRO
   de la tarjeta, alineados a la derecha, en vez de la barra fija inferior.
   La lógica (pasos, validación, envío) es la de Funnel.jsx; esto solo envuelve. */
export function LabStepFormShell({ lab, footer, isWelcome, children }) {
  const brand = footer?.copyrightBrand || 'Conquer'
  return (
    <LabPage lab={lab}>
      <header className="w-full px-4 md:px-16 pt-4 md:pt-[28px] pb-6 md:pb-16">
        <LabLogoBar lab={lab} brand={brand} />
      </header>
      <section className="w-full px-4 md:px-16 pt-2 md:pt-8 pb-16 md:pb-28 flex justify-center">
        <div className={`${LAB_CARD} w-full max-w-[1140px] px-5 md:px-16 lg:px-[160px] ${isWelcome ? 'py-12 md:py-28' : 'py-8 md:py-[72px]'}`}>
          {children}
        </div>
      </section>
      <LabFooter lab={lab} footer={footer} />
    </LabPage>
  )
}

// Progreso: "NN% completado" sobre una pista de 220×6 con el degradado de
// marca, y las flechas ↑ ↓ en cajas de 40px.
export function LabProgress({ progress, onUp, onDown, canGoUp, canGoDown }) {
  const arrow = 'w-10 h-10 rounded-[10px] bg-white border border-[color:var(--lab-n300)] flex items-center justify-center font-semibold text-base leading-6 text-[color:var(--lab-ink)] transition-opacity disabled:opacity-30 disabled:cursor-default'
  return (
    <div className="flex items-center justify-end gap-3 pt-4 mt-7">
      <div className="flex flex-col gap-2">
        <span className="text-sm leading-[21px] font-semibold text-[color:var(--lab-ink)]">{progress}% completado</span>
        <div className="w-[160px] md:w-[220px] h-1.5 rounded-[3px] bg-[#F2F2F2] overflow-hidden">
          <div className="h-full rounded-[3px] transition-all duration-500 ease-out" style={{ width: `${progress}%`, backgroundImage: 'var(--lab-gradient)' }} />
        </div>
      </div>
      <button type="button" className={arrow} onClick={onUp} disabled={!canGoUp} aria-label="Pregunta anterior">↑</button>
      <button type="button" className={arrow} onClick={onDown} disabled={!canGoDown} aria-label="Pregunta siguiente">↓</button>
    </div>
  )
}
