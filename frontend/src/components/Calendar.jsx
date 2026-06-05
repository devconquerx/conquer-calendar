import React, { useState, useEffect, useCallback } from 'react'

const MESES = ['Enero','Febrero','Marzo','Abril','Mayo','Junio',
               'Julio','Agosto','Septiembre','Octubre','Noviembre','Diciembre']
const MESES_ES = ['enero','febrero','marzo','abril','mayo','junio',
                  'julio','agosto','septiembre','octubre','noviembre','diciembre']
const DIAS_ES = ['domingo','lunes','martes','miércoles','jueves','viernes','sábado']

function pad(n) { return String(n).padStart(2, '0') }
function todayISO() {
  const d = new Date()
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`
}
function detectTZ() {
  try { return Intl.DateTimeFormat().resolvedOptions().timeZone } catch (e) { return 'UTC' }
}
function currentMonthStr() {
  const d = new Date()
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}`
}
function fechaDisplay(ds) {
  const [, m, d] = ds.split('-')
  return `${parseInt(d)} de ${MESES_ES[parseInt(m) - 1]}`
}
function fechaTitle(ds) {
  const date = new Date(ds + 'T12:00:00')
  const dow = DIAS_ES[date.getDay()]
  return dow.charAt(0).toUpperCase() + dow.slice(1) + ', ' + fechaDisplay(ds)
}

function LeftPanel({ eventoInfo }) {
  return (
    <div className="bk-left">
      <h1 className="bk-title">{eventoInfo?.nombre || 'Consultoría'}</h1>
      {eventoInfo?.duracion_minutos && (
        <div className="bk-meta">
          <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/>
          </svg>
          {eventoInfo.duracion_minutos} min
        </div>
      )}
      {eventoInfo?.precio && (
        <div className="bk-meta">
          <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <line x1="12" y1="1" x2="12" y2="23"/><path d="M17 5H9.5a3.5 3.5 0 0 0 0 7h5a3.5 3.5 0 0 1 0 7H6"/>
          </svg>
          {eventoInfo.precio} EUR
        </div>
      )}
      {eventoInfo?.descripcion && (
        <div className="bk-desc" dangerouslySetInnerHTML={{ __html: eventoInfo.descripcion }} />
      )}
    </div>
  )
}

export default function Calendar({ hostSlug, eventTypeSlug, eventoInfo, onSlotSelected }) {
  const [tz] = useState(detectTZ)
  const [mes, setMes] = useState(currentMonthStr)
  const [slotsData, setSlotsData] = useState(null)
  const [loadingMes, setLoadingMes] = useState(false)
  const [selectedDate, setSelectedDate] = useState(null)

  const fetchMes = useCallback((mesStr) => {
    setLoadingMes(true)
    fetch(`/${hostSlug}/${eventTypeSlug}/slots.json?mes=${mesStr}&tz=${encodeURIComponent(tz)}`)
      .then(r => r.json())
      .then(data => { setSlotsData(data); setLoadingMes(false) })
      .catch(() => setLoadingMes(false))
  }, [hostSlug, eventTypeSlug, tz])

  useEffect(() => { fetchMes(mes) }, [mes, fetchMes])

  const HOY = todayISO()
  const mesData = slotsData

  let gridRows = []
  let mesLabel = ''

  if (mesData) {
    const [year, month] = mesData.mes.slice(0, 7).split('-').map(Number)
    mesLabel = `${MESES[month - 1]} ${year}`
    const firstDow = new Date(Date.UTC(year, month - 1, 1)).getUTCDay()
    const leadDays = firstDow === 0 ? 6 : firstDow - 1
    const daysInMonth = new Date(Date.UTC(year, month, 0)).getUTCDate()
    const numRows = Math.ceil((leadDays + daysInMonth) / 7)
    const cur = new Date(Date.UTC(year, month - 1, 1 - leadDays))
    for (let w = 0; w < numRows; w++) {
      const week = []
      for (let c = 0; c < 7; c++) {
        const dy = cur.getUTCFullYear(), dm = cur.getUTCMonth() + 1, dd = cur.getUTCDate()
        const ds = `${dy}-${pad(dm)}-${pad(dd)}`
        const inM = dm === month
        const hasS = !!(mesData.dias?.[ds]?.length)
        const ok = inM && hasS && ds >= HOY && ds <= mesData.max_fecha
        week.push({ ds, dd, inM, ok, isToday: ds === HOY, isSel: ds === selectedDate })
        cur.setUTCDate(cur.getUTCDate() + 1)
      }
      gridRows.push(week)
    }
  }

  const slotsForDay = selectedDate && mesData ? (mesData.dias?.[selectedDate] || []) : []
  const utcsForDay = selectedDate && mesData ? (mesData.slots_utc?.[selectedDate] || []) : []
  const canPrev = mesData?.mes_anterior != null
  const canNext = mesData?.mes_siguiente != null

  return (
    <div className="bk-wrapper">
      <div className={`bk-card${selectedDate ? ' has-slots' : ''}`}>

        <LeftPanel eventoInfo={eventoInfo} />

        <div className="bk-right">
          <div className="bk-date-inner">
            <div className="bk-cal-col">
              <p className="bk-step-title">Selecciona una fecha y hora</p>

              <div className="bk-month-nav">
                <button
                  type="button"
                  className={`bk-nav-btn${!canPrev ? ' off' : ''}`}
                  onClick={() => { if (canPrev && mesData?.mes_anterior) { setMes(mesData.mes_anterior.slice(0, 7)); setSelectedDate(null) } }}
                >‹</button>
                <span className="bk-month-label">{mesLabel}</span>
                <button
                  type="button"
                  className={`bk-nav-btn${!canNext ? ' off' : ''}`}
                  onClick={() => { if (canNext && mesData?.mes_siguiente) { setMes(mesData.mes_siguiente.slice(0, 7)); setSelectedDate(null) } }}
                >›</button>
              </div>

              <table className="bk-grid">
                <thead>
                  <tr><th>LUN</th><th>MAR</th><th>MIÉ</th><th>JUE</th><th>VIE</th><th>SÁB</th><th>DOM</th></tr>
                </thead>
                <tbody>
                  {loadingMes ? (
                    <tr><td colSpan={7} style={{ textAlign: 'center', padding: '20px', color: '#aaa', fontSize: '14px' }}>Cargando…</td></tr>
                  ) : gridRows.map((week, wi) => (
                    <tr key={wi}>
                      {week.map(({ ds, dd, inM, ok, isToday, isSel }) => (
                        <td key={ds}>
                          {!inM ? (
                            <span className="bk-day out">{dd}</span>
                          ) : ok ? (
                            <button
                              type="button"
                              className={`bk-day avail${isSel ? ' sel' : ''}${isToday ? ' today' : ''}`}
                              onClick={() => setSelectedDate(ds)}
                            >{dd}</button>
                          ) : (
                            <span className={`bk-day${isToday ? ' today' : ''}`}>{dd}</span>
                          )}
                        </td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>

              <div className="bk-tz-section">
                <p className="bk-tz-label">Zona horaria</p>
                <div className="bk-tz-row">
                  <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                    <circle cx="12" cy="12" r="10"/><line x1="2" y1="12" x2="22" y2="12"/>
                    <path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z"/>
                  </svg>
                  <span style={{ fontSize: '14px', color: '#1a1a2e' }}>{tz}</span>
                </div>
              </div>
            </div>

            {selectedDate && (
              <div className="bk-slots-col">
                <p className="bk-slots-title">{fechaTitle(selectedDate)}</p>
                {slotsForDay.length > 0 ? (
                  <div className="bk-slots-scroll">
                    {slotsForDay.map((hora, i) => (
                      <button
                        key={i}
                        type="button"
                        className="bk-slot"
                        onClick={() => onSlotSelected({
                          utc: utcsForDay[i],
                          label: hora + ' h',
                          fechaDisplay: fechaDisplay(selectedDate),
                          tz,
                        })}
                      >{hora} h</button>
                    ))}
                  </div>
                ) : (
                  <p className="bk-empty">Sin horarios para este día.</p>
                )}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}
