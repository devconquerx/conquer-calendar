import LandingForm from '../landing/LandingForm'
import { safeHtml } from '../../lib/sanitize'
import { LAB_TEXTURE_MASK } from '../../themes/lab'
import { LAB_CARD as CARD, LAB_H1, LabPage, LabLogoBar, LabTag, LabTorn, LabFooter } from './LabParts'

/* ═══ Landing "Conquer Lab" ═══
   Réplica de Figma (Languages · Embudo 3 · Clase online gratuita EU), hecha
   con los componentes de la librería compartida Conquer Lab, así que sirve a
   cualquier marca que traiga su bloque `theme.lab` (colores + assets).

   Estructura (desktop 1440):
     01 Cabecera  — barra con logo, tag, H1, subtítulo y 3 beneficios
     02 Formulario — banda de color con rasgado de papel arriba y abajo
     03 Instructor — tarjeta foto + texto
     99 Footer     — logo, divisor y legales
   El papel de fondo va en mosaico por toda la página (en Figma cada sección
   lleva su propia Superficie, pero son la misma imagen sin costuras).

   Convención del texto que viene de la BD (la misma que paperboard):
   <strong> = acento caligráfico de marca. */

export default function LabLanding({ school, program, region, formConfig, theme, instructor, disclaimer, nextUrl, funnelSlug, videoEnabled }) {
  const lab = theme.lab
  const footer = theme.footer || {}
  const landing = formConfig?.landing || formConfig?.welcome || {}
  const bullets = landing.bullets || []
  const brand = footer.copyrightBrand || 'Conquer'
  // El formulario se pinta con la rama `lab` de LandingForm.
  const formTheme = { ...theme, design: 'lab' }
  const instructorPhoto = instructor?.photoUrl || lab.instructorPhoto || instructor?.imageUrl

  return (
    <LabPage lab={lab}>
      {/* ── 01 · Cabecera ── */}
      <header className="w-full px-4 md:px-16 pt-4 md:pt-[28px] pb-16 md:pb-24 flex flex-col items-center gap-8 md:gap-10">
        <LabLogoBar lab={lab} brand={brand} />

        <div className="w-full max-w-[1000px] flex flex-col items-center gap-5 text-center">
          {landing.subtitle && <LabTag html={landing.subtitle} />}
          <h1
            className={LAB_H1}
            dangerouslySetInnerHTML={safeHtml(landing.title)}
          />
          {landing.description && (
            <p className="text-base leading-6 md:text-lg md:leading-[27px]">{landing.description}</p>
          )}
        </div>

        {bullets.length > 0 && (
          <ul className="w-full max-w-[1140px] flex flex-col gap-3 md:gap-4">
            {bullets.map((item, i) => {
              const icon = lab.bulletIcons?.[i % lab.bulletIcons.length]
              return (
                <li key={i} className={`${CARD} flex items-center gap-4 md:gap-5 px-4 py-4 md:px-6 md:py-5`}>
                  {icon && (
                    <span className="relative flex-shrink-0 w-11 h-11 md:w-14 md:h-14" aria-hidden="true">
                      {/* Un <img> con los cuatro lados fijados no se estira
                          (es un elemento reemplazado); el div sí, y la imagen
                          lo llena. */}
                      <span className="absolute" style={{ inset: icon.inset }}>
                        <img src={icon.src} alt="" className="block w-full h-full max-w-none" />
                      </span>
                    </span>
                  )}
                  <p
                    className="flex-1 min-w-0 text-base leading-6 md:text-xl md:leading-[30px] [&_strong]:font-semibold"
                    dangerouslySetInnerHTML={safeHtml(item)}
                  />
                </li>
              )
            })}
          </ul>
        )}
      </header>

      {/* ── 02 · Formulario (banda de color) ── */}
      <section className="relative w-full px-4 md:px-16 py-20 md:py-28 flex justify-center" style={{ backgroundImage: lab.bandBackground }}>
        {lab.bandTexture && (
          <div
            aria-hidden="true"
            className="absolute inset-0 pointer-events-none bg-cover bg-center"
            style={{ backgroundImage: `url(${lab.bandTexture})`, WebkitMaskImage: LAB_TEXTURE_MASK, maskImage: LAB_TEXTURE_MASK }}
          />
        )}
        <LabTorn src={lab.torn} />
        <div className={`${CARD} relative w-full max-w-[1140px] px-5 py-6 md:px-12 md:py-10`}>
          <LandingForm
            program={program}
            region={region}
            formConfig={formConfig}
            school={school}
            themeOverride={formTheme}
            nextUrl={nextUrl}
            funnelSlug={funnelSlug}
            videoEnabled={videoEnabled}
          />
        </div>
      </section>

      {/* ── 03 · Instructor ── */}
      {instructor && (
        <section className="w-full px-4 md:px-16 py-16 md:py-28 flex justify-center">
          <div className={`${CARD} w-full max-w-[1140px] overflow-hidden flex flex-col lg:flex-row`}>
            {instructorPhoto && (
              <img
                src={instructorPhoto}
                alt={instructor.name}
                width="520"
                height="460"
                loading="lazy"
                className="w-full lg:w-[45.6%] aspect-[520/460] md:aspect-[16/9] lg:aspect-[520/460] object-cover object-[50%_25%] flex-shrink-0"
              />
            )}
            <div className="flex-1 min-w-0 px-5 py-8 md:px-12 md:py-10 lg:px-14 lg:py-12 flex flex-col justify-center gap-4">
              <h2 className="font-semibold text-[32px] leading-[40px] md:text-[40px] md:leading-[48px] tracking-[-0.4px]">
                <LabName name={instructor.name} />
              </h2>
              {instructor.role && (
                <p className="text-lg leading-[27px] md:text-xl md:leading-[30px] [&_strong]:font-semibold" dangerouslySetInnerHTML={safeHtml(instructor.role)} />
              )}
              {instructor.description && (
                <p className="text-base leading-6 md:text-lg md:leading-[27px]" dangerouslySetInnerHTML={safeHtml(instructor.description)} />
              )}
            </div>
          </div>
        </section>
      )}

      {/* ── 99 · Footer ── */}
      <LabFooter lab={lab} footer={footer} disclaimer={disclaimer} />
    </LabPage>
  )
}

// Nombre del instructor: el apellido (última palabra) va con el acento
// caligráfico, como "Andy *Povedano*" en Figma.
function LabName({ name = '' }) {
  const parts = String(name).trim().split(/\s+/)
  if (parts.length < 2) return <>{name}</>
  const last = parts.pop()
  return (
    <>
      {parts.join(' ')}{' '}
      <span className="font-normal [font-family:var(--lab-script)] text-[44px] leading-[48px] md:text-[54px] md:leading-[58px] [background-image:var(--lab-text-gradient)] bg-clip-text text-transparent px-[0.04em]">
        {last}
      </span>
    </>
  )
}
