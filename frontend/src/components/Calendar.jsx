import React, { useState, useEffect, useCallback } from 'react'
import { apiUrl } from '../lib/apiBase'

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

function tzLabel(tz, now) {
  const city = tz.split('/').pop().replace(/_/g, ' ')
  try {
    const time = now.toLocaleTimeString('es-ES', { hour: '2-digit', minute: '2-digit', timeZone: tz, hour12: false })
    return `${city} (${time})`
  } catch { return city }
}

function TzCombo({ tz, onChange }) {
  const [open, setOpen] = useState(false)
  const [query, setQuery] = useState('')
  const [now, setNow] = useState(() => new Date())
  const inputRef = React.useRef(null)

  useEffect(() => {
    const t = setInterval(() => setNow(new Date()), 60000)
    return () => clearInterval(t)
  }, [])

  let zones = []
  try { zones = Intl.supportedValuesOf('timeZone') } catch { zones = [tz] }
  const filtered = query
    ? zones.filter(z => z.toLowerCase().includes(query.toLowerCase()))
    : zones

  return (
    <div className="bk-tz-combo" style={{ position: 'relative' }}>
      <button type="button" className="bk-tz-display-btn" onClick={() => { setOpen(o => !o); setTimeout(() => inputRef.current?.focus(), 50) }}>
        <span style={{ fontSize: '14px', color: '#1a1a2e' }}>{tzLabel(tz, now)}</span>
        <span style={{ fontSize: '8px', color: '#8a8a8a', marginLeft: 4 }}>▼</span>
      </button>
      {open && (
        <div style={{ position: 'absolute', bottom: 'calc(100% + 4px)', left: 0, minWidth: 260, maxWidth: 320, maxHeight: 280, overflowY: 'auto', background: '#fff', border: '1px solid #e2e5e9', borderRadius: 6, boxShadow: '0 -4px 14px rgba(0,0,0,.10)', zIndex: 100 }}>
          <div style={{ padding: '8px 10px', borderBottom: '1px solid #e2e5e9' }}>
            <input ref={inputRef} type="text" value={query} onChange={e => setQuery(e.target.value)} placeholder="Buscar zona…" style={{ width: '100%', border: '1px solid #e2e5e9', borderRadius: 4, padding: '5px 8px', fontSize: 13, outline: 'none', boxSizing: 'border-box' }} onBlur={() => setTimeout(() => setOpen(false), 150)} />
          </div>
          {filtered.slice(0, 120).map(z => (
            <div key={z} onMouseDown={e => { e.preventDefault(); onChange(z); setOpen(false); setQuery('') }} style={{ padding: '7px 12px', fontSize: 12.5, cursor: 'pointer', background: z === tz ? '#e8f0fe' : undefined, color: z === tz ? '#0069ff' : '#1a1a2e', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
              {z}
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

export default function Calendar({ hostSlug, eventTypeSlug, eventoInfo, onSlotSelected }) {
  const [tz, setTz] = useState(detectTZ)
  const [mes, setMes] = useState(currentMonthStr)
  const [slotsData, setSlotsData] = useState(null)
  const [loadingMes, setLoadingMes] = useState(false)
  const [selectedDate, setSelectedDate] = useState(null)

  const fetchMes = useCallback((mesStr) => {
    setLoadingMes(true)
    fetch(apiUrl(`/${hostSlug}/${eventTypeSlug}/slots.json?mes=${mesStr}&tz=${encodeURIComponent(tz)}`))
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
                  <TzCombo tz={tz} onChange={tz => { setTz(tz); setSelectedDate(null); }} />
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
