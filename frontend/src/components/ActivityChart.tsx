import { useState } from 'react'

// Grouped bar chart: Sent vs Received per day. Palette validated for colour-vision deficiency
// (maroon #97364b / blue #1f84b8, CVD ΔE 16.6). Legend + per-bar tooltip + table fallback.
export const SERIES = [
  { key: 'sent', label: 'Sent', color: '#97364b' },
  { key: 'received', label: 'Received', color: '#1f84b8' },
] as const

interface Day { date: string; sent: number; received: number; bytes: number }

export default function ActivityChart({ data, compact }: { data: Day[]; compact?: boolean }) {
  const [hover, setHover] = useState<{ i: number; k: string } | null>(null)
  const [table, setTable] = useState(false)
  const W = compact ? 420 : 640, H = compact ? 290 : 220, padL = 32, padB = 26, padT = 10
  const fs = compact ? 12.5 : 10.5
  const max = Math.max(4, ...data.flatMap((d) => [d.sent, d.received]))
  const nice = Math.ceil(max / 4) * 4
  const ticks = [0, nice / 4, nice / 2, (3 * nice) / 4, nice]
  const groupW = (W - padL) / data.length
  const barW = Math.min(compact ? 20 : 22, groupW / 3)
  const y = (v: number) => padT + (H - padT - padB) * (1 - v / nice)
  const label = (iso: string) => new Date(iso + 'T00:00:00').toLocaleDateString('en-GB', compact ? { day: '2-digit', month: 'short' } : { weekday: 'short', day: '2-digit' })

  return (
    <div>
      <div className="mb-2 flex items-center justify-between">
        <div className="flex gap-4 text-xs text-ink-600">
          {SERIES.map((s) => <span key={s.key} className="inline-flex items-center gap-1.5"><span className="h-2.5 w-2.5 rounded-sm" style={{ background: s.color }} />{s.label}</span>)}
        </div>
        <button onClick={() => setTable((t) => !t)} className="text-xs font-medium text-maroon-700 hover:underline">{table ? 'Show chart' : 'Show table'}</button>
      </div>
      {table ? (
        <table className="w-full text-sm">
          <thead><tr className="text-left text-xs text-ink-500"><th className="py-1">Day</th><th>Sent</th><th>Received</th></tr></thead>
          <tbody>{data.map((d) => <tr key={d.date} className="border-t border-ink-100"><td className="py-1">{label(d.date)}</td><td>{d.sent}</td><td>{d.received}</td></tr>)}</tbody>
        </table>
      ) : (
        <div className="relative">
          <svg viewBox={`0 0 ${W} ${H}`} className="h-auto w-full" role="img" aria-label="Transfers sent and received over the last seven days">
            {ticks.map((t) => (
              <g key={t}>
                <line x1={padL} x2={W} y1={y(t)} y2={y(t)} stroke="#efeced" strokeWidth={1} />
                <text x={padL - 8} y={y(t) + 4} textAnchor="end" fontSize={fs} fill="#7a6e72">{Math.round(t)}</text>
              </g>
            ))}
            {data.map((d, i) => {
              const cx = padL + groupW * i + groupW / 2
              return (
                <g key={d.date}>
                  {SERIES.map((s, j) => {
                    const v = (d as any)[s.key] as number
                    const x = cx + (j === 0 ? -barW - 1 : 1)
                    const top = y(v)
                    const h = Math.max(0, y(0) - top)
                    const r = Math.min(4, h)
                    const active = hover && hover.i === i && hover.k === s.key
                    return (
                      <g key={s.key}>
                        {h > 0 && <path d={`M${x},${y(0)} V${top + r} Q${x},${top} ${x + r},${top} H${x + barW - r} Q${x + barW},${top} ${x + barW},${top + r} V${y(0)} Z`}
                          fill={s.color} opacity={hover && !active ? 0.45 : 1} />}
                        <rect x={x - 2} y={padT} width={barW + 4} height={H - padT - padB} fill="transparent"
                          onMouseEnter={() => setHover({ i, k: s.key })} onMouseLeave={() => setHover(null)} />
                      </g>
                    )
                  })}
                  <text x={cx} y={H - 8} textAnchor="middle" fontSize={fs} fill="#5f5458">{label(d.date)}</text>
                </g>
              )
            })}
            <line x1={padL} x2={W} y1={y(0)} y2={y(0)} stroke="#c9c1c4" />
          </svg>
          {hover && (() => {
            const d = data[hover.i]
            const left = ((padL + groupW * hover.i + groupW / 2) / W) * 100
            return (
              <div className="pointer-events-none absolute top-0 -translate-x-1/2 rounded-lg border border-ink-100 bg-white px-3 py-2 text-xs shadow-pop" style={{ left: `${left}%` }}>
                <div className="mb-1 font-semibold text-ink-900">{label(d.date)}</div>
                {SERIES.map((s) => <div key={s.key} className="flex items-center gap-2 text-ink-700"><span className="h-2 w-2 rounded-sm" style={{ background: s.color }} />{s.label}: <b className="text-ink-900">{(d as any)[s.key]}</b></div>)}
              </div>
            )
          })()}
        </div>
      )}
    </div>
  )
}
