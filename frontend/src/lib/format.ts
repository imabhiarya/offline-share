// Formatting helpers. Server timestamps are UTC ISO strings ending with "Z".

let dateFormat = 'DD/MM/YYYY'
let timeFormat: '24h' | '12h' = '24h'

export function configureFormats(d?: string, t?: string) {
  if (d) dateFormat = d
  if (t === '12h' || t === '24h') timeFormat = t
}

const pad = (n: number) => String(n).padStart(2, '0')

export function fmtDate(iso?: string | null): string {
  if (!iso) return '—'
  const d = new Date(iso)
  if (isNaN(d.getTime())) return '—'
  const dd = pad(d.getDate()), mm = pad(d.getMonth() + 1), yyyy = String(d.getFullYear())
  const mon = d.toLocaleString('en-GB', { month: 'short' })
  switch (dateFormat) {
    case 'MM/DD/YYYY': return `${mm}/${dd}/${yyyy}`
    case 'YYYY-MM-DD': return `${yyyy}-${mm}-${dd}`
    case 'DD-MMM-YYYY': return `${dd}-${mon}-${yyyy}`
    default: return `${dd}/${mm}/${yyyy}`
  }
}

export function fmtTime(iso?: string | null): string {
  if (!iso) return ''
  const d = new Date(iso)
  if (timeFormat === '12h') {
    const h = d.getHours() % 12 || 12
    return `${h}:${pad(d.getMinutes())} ${d.getHours() < 12 ? 'AM' : 'PM'}`
  }
  return `${pad(d.getHours())}:${pad(d.getMinutes())}`
}

export function fmtDateTime(iso?: string | null): string {
  if (!iso) return '—'
  return `${fmtDate(iso)} ${fmtTime(iso)}`
}

export function timeAgo(iso?: string | null): string {
  if (!iso) return 'never'
  const s = Math.max(0, (Date.now() - new Date(iso).getTime()) / 1000)
  if (s < 45) return 'just now'
  if (s < 3600) return `${Math.round(s / 60)} min ago`
  if (s < 86400) return `${Math.round(s / 3600)} h ago`
  if (s < 86400 * 7) return `${Math.round(s / 86400)} d ago`
  return fmtDate(iso)
}

export function fmtSize(bytes?: number | null): string {
  const n = Number(bytes || 0)
  if (n < 1024) return `${n} B`
  const units = ['KB', 'MB', 'GB', 'TB']
  let v = n / 1024, i = 0
  while (v >= 1024 && i < units.length - 1) { v /= 1024; i++ }
  return `${v < 10 ? v.toFixed(1) : Math.round(v)} ${units[i]}`
}

export function fmtDuration(seconds: number): string {
  const d = Math.floor(seconds / 86400), h = Math.floor((seconds % 86400) / 3600), m = Math.floor((seconds % 3600) / 60)
  return d ? `${d}d ${h}h` : h ? `${h}h ${m}m` : `${m}m`
}

export function initials(name: string): string {
  return name.split(/\s+/).filter(Boolean).slice(0, 2).map((p) => p[0]?.toUpperCase()).join('') || '?'
}

export function plural(n: number, word: string): string {
  return `${n} ${word}${n === 1 ? '' : 's'}`
}
