import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  Activity, ArrowRight, BarChart3, CheckCircle2, Clock, Database, Download, History as HistoryIcon, MonitorSmartphone,
  Network, Send, Server, ShieldCheck, XCircle, AlertTriangle,
} from 'lucide-react'
import { api } from '../lib/api'
import { useAuth } from '../lib/auth'
import { useRealtime, useRealtimeEvent } from '../lib/realtime'
import { fmtSize, fmtTime } from '../lib/format'
import ActivityChart from '../components/ActivityChart'
import TransferIllustration from '../components/TransferIllustration'
import { NAV } from '../components/Layout'
import { cx, ErrorBox, Loading, StatCard, StatusBadge } from '../components/ui'

const QUICK: Record<string, { desc: string; color: string }> = {
  '/send': { desc: 'Transfer files & messages', color: 'text-white' },
  '/receive': { desc: 'View incoming data', color: 'text-sky-600' },
  '/history': { desc: 'Track all transfers', color: 'text-maroon-700' },
  '/devices': { desc: 'View & manage PCs', color: 'text-maroon-700' },
  '/users': { desc: 'Users, roles & access', color: 'text-maroon-700' },
  '/files': { desc: 'Central file repository', color: 'text-orange-500' },
  '/settings': { desc: 'Configure system', color: 'text-maroon-700' },
}

export default function Dashboard() {
  const { session, can, isAdmin } = useAuth()
  const { connected } = useRealtime()
  const [d, setD] = useState<any>(null)
  const [err, setErr] = useState('')
  const [scope, setScope] = useState<'auto' | 'mine'>('auto')
  const nav = useNavigate()
  const load = () => api.get(`/api/dashboard?scope=${scope}`).then((x) => { setD(x); setErr('') }).catch((e) => setErr(e.message))
  useEffect(() => { load(); const t = setInterval(load, 30000); return () => clearInterval(t) }, [scope])
  useRealtimeEvent((m) => { if (['transfer.new', 'transfer.status', 'presence', 'devices.changed'].includes(m.type)) load() }, [scope])

  if (err && !d) return <ErrorBox error={err} onRetry={load} />
  if (!d) return <Loading />
  const s = d.stats
  const h = d.health
  const quick = NAV.filter((n) => n.to !== '/dashboard' && can(n.perm))
  const healthy = h.disk_percent < 90 && (h.cpu_percent ?? 0) < 95 && (h.memory_percent ?? 0) < 95
  const name = session!.user.full_name

  return (
    <div className="space-y-4">
      {/* welcome banner */}
      <section className="relative overflow-hidden rounded-2xl border border-ink-100 bg-gradient-to-r from-white via-white to-maroon-50 shadow-card">
        <div className="grid items-center gap-2 md:grid-cols-[1fr_auto]">
          <div className="flex items-stretch gap-5 px-6 py-6">
            <span className="w-1.5 shrink-0 rounded-full bg-maroon-700" />
            <div className="min-w-0">
              <h1 className="text-[34px] font-medium leading-tight text-ink-900">Welcome, <b className="font-extrabold text-maroon-700">{name}</b></h1>
              <p className="mt-1 text-[17px] text-ink-800">{session!.branding.app_name || 'OFFLINE SHARE'} – A Secure &amp; High-Speed Data Transfer System for Office Network</p>
              {isAdmin && (
                <div className="mt-3 inline-flex rounded-lg border border-ink-200 bg-white p-0.5 text-xs font-semibold">
                  {(['auto', 'mine'] as const).map((v) => (
                    <button key={v} onClick={() => setScope(v)} className={cx('rounded-md px-3 py-1.5', scope === v ? 'bg-maroon-700 text-white' : 'text-ink-600')}>{v === 'auto' ? 'All users' : 'Only mine'}</button>
                  ))}
                </div>
              )}
            </div>
          </div>
          <TransferIllustration className="hidden h-[150px] w-auto md:block lg:h-[170px]" />
        </div>
      </section>

      {/* KPIs */}
      <div className="grid grid-cols-2 gap-3 md:grid-cols-3 xl:grid-cols-6">
        <StatCard label="Total Sent" value={s.total_sent} icon={Send} tone="pink" onClick={() => nav('/history?tab=sent')} />
        <StatCard label="Total Received" value={s.total_received} icon={Download} tone="green" onClick={() => nav('/receive')} />
        <StatCard label="Delivered" value={s.delivered} icon={CheckCircle2} tone="blue" />
        <StatCard label="Pending" value={s.pending} icon={Clock} tone="amber" onClick={() => nav('/history?tab=pending')} />
        <StatCard label="Failed" value={s.failed} icon={XCircle} tone="red" onClick={() => nav('/history?tab=failed')} />
        <StatCard label="Total Data" value={fmtSize(s.total_data)} icon={Database} tone="violet" />
      </div>

      {/* quick access */}
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4 xl:grid-cols-7">
        {quick.map((q, i) => {
          const first = i === 0
          return (
            <button key={q.to} onClick={() => nav(q.to)}
              className={cx('group relative flex min-h-[150px] flex-col justify-between overflow-hidden rounded-2xl border p-4 text-left shadow-card transition hover:-translate-y-1 hover:shadow-pop',
                first ? 'border-maroon-800 bg-gradient-to-br from-maroon-600 to-maroon-900 text-white' : 'border-ink-100 bg-gradient-to-b from-white to-ink-50 text-ink-900')}>
              <q.icon className={cx('h-11 w-11', QUICK[q.to]?.color)} strokeWidth={1.6} />
              <div>
                <div className="text-[18px] font-bold leading-tight">{q.label}</div>
                <div className={cx('mt-1 flex items-center justify-between gap-2 text-[13px]', first ? 'text-white/90' : 'text-ink-700')}>
                  <span>{QUICK[q.to]?.desc}</span><ArrowRight className="h-4 w-4 shrink-0 transition group-hover:translate-x-1" />
                </div>
              </div>
            </button>
          )
        })}
      </div>

      {/* activity · recent · status */}
      <div className="grid gap-4 xl:grid-cols-[1fr_1.25fr_0.85fr]">
        <section className="rounded-2xl border border-ink-100 bg-white p-5 shadow-card">
          <h3 className="mb-3 flex items-center gap-2 text-[18px] font-bold text-maroon-800"><BarChart3 className="h-6 w-6 text-maroon-700" />Transfer Activity <span className="font-normal text-ink-700">(Last 7 Days)</span></h3>
          <ActivityChart data={d.activity} compact />
        </section>

        <section className="rounded-2xl border border-ink-100 bg-white p-5 shadow-card">
          <div className="mb-3 flex items-center justify-between">
            <h3 className="flex items-center gap-2 text-[18px] font-bold text-maroon-800"><HistoryIcon className="h-6 w-6 text-maroon-700" />Recent Transfers</h3>
            {can('history') && <button onClick={() => nav('/history')} className="inline-flex items-center gap-1 rounded-lg border border-maroon-200 bg-maroon-50 px-3 py-1.5 text-sm font-semibold text-maroon-800 hover:bg-maroon-100">View All <ArrowRight className="h-4 w-4" /></button>}
          </div>
          {d.recent.length === 0 ? <div className="py-12 text-center text-sm text-ink-500">No transfers yet. Sent and received data will appear here.</div> : (
            <div className="overflow-x-auto">
              <table className="w-full text-left text-[13px]">
                <thead><tr className="bg-ink-50 text-ink-800">{['Time', 'Direction', 'From', 'To', 'Subject / File', 'Status'].map((h) => <th key={h} className="px-2 py-2 font-bold">{h}</th>)}</tr></thead>
                <tbody>
                  {d.recent.map((r: any) => (
                    <tr key={r.id} className="border-b border-ink-100 last:border-0">
                      <td className="whitespace-nowrap px-2 py-2.5">{fmtTime(r.created_at)}</td>
                      <td className="whitespace-nowrap px-2">{r.direction === 'received'
                        ? <span className="inline-flex items-center gap-1 font-medium text-sky-700"><Download className="h-4 w-4" />Received</span>
                        : <span className="inline-flex items-center gap-1 font-medium text-emerald-700"><Send className="h-4 w-4" />{r.direction === 'sent' ? 'Sent' : 'Transfer'}</span>}</td>
                      <td className="max-w-[110px] truncate px-2">{r.sender_pc || r.sender}</td>
                      <td className="max-w-[110px] truncate px-2">{r.recipient_pc || r.recipient}</td>
                      <td className="max-w-[160px] truncate px-2">{r.subject || '(no subject)'}</td>
                      <td className="px-2"><StatusBadge status={r.status} /></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </section>

        <div className="space-y-4">
          <section className="rounded-2xl border border-ink-100 bg-white p-5 shadow-card">
            <h3 className="mb-3 flex items-center gap-2 text-[18px] font-bold text-maroon-800"><Activity className="h-6 w-6 text-maroon-700" />System Status</h3>
            <ul className="space-y-2.5 text-[14px]">
              <StatusRow icon={Server} label="Server" value={<Pill ok={connected}>{connected ? 'Online' : 'Offline'}</Pill>} />
              <StatusRow icon={Network} label="Connected PCs" value={<span className="rounded-lg bg-ink-50 px-2.5 py-1 font-bold">{d.devices.online} / {d.devices.total}</span>} />
              <StatusRow icon={Database} label="Storage Used" value={<span className="rounded-lg bg-ink-50 px-2.5 py-1 font-bold">{fmtSize(d.storage.used)}{d.storage.quota ? ` / ${fmtSize(d.storage.quota)}` : ''}</span>} />
              <StatusRow icon={ShieldCheck} label="System Status" value={<Pill ok={healthy}>{healthy ? 'Healthy' : 'Attention'}</Pill>} />
              <StatusRow icon={MonitorSmartphone} label="Users online" value={<span className="rounded-lg bg-ink-50 px-2.5 py-1 font-bold">{d.users.online} / {d.users.total}</span>} />
            </ul>
          </section>
          <section className="rounded-2xl border border-ink-100 bg-white p-5 shadow-card">
            <h3 className="mb-2 flex items-center gap-2 text-[18px] font-bold text-maroon-800"><Database className="h-6 w-6 text-maroon-700" />Storage Usage</h3>
            <div className="text-[15px] text-ink-900">{fmtSize(d.storage.used)}{d.storage.quota ? ` of ${fmtSize(d.storage.quota)} (${d.storage.percent}%)` : ' used'}</div>
            <div className="mt-2 h-3.5 overflow-hidden rounded-full bg-ink-100"><div className="h-full rounded-full bg-gradient-to-r from-maroon-600 to-maroon-800" style={{ width: `${Math.max(2, Math.min(100, d.storage.percent))}%` }} /></div>
            <div className="mt-2 flex justify-between text-xs text-ink-600"><span>Transfers {fmtSize(d.storage.transfers_used)}</span><span>Depository {fmtSize(d.storage.repository_used)}</span></div>
            {!healthy && <div className="mt-2 flex items-center gap-1.5 text-xs text-amber-700"><AlertTriangle className="h-3.5 w-3.5" />Server resources are high – check Settings → Maintenance.</div>}
          </section>
        </div>
      </div>
    </div>
  )
}

function StatusRow({ icon: Icon, label, value }: { icon: any; label: string; value: React.ReactNode }) {
  return <li className="flex items-center justify-between gap-2"><span className="flex items-center gap-2.5 text-ink-800"><Icon className="h-5 w-5 text-ink-600" />{label}</span>{value}</li>
}
function Pill({ ok, children }: { ok: boolean; children: React.ReactNode }) {
  return <span className={cx('inline-flex items-center gap-1 rounded-lg px-2.5 py-1 text-[13px] font-semibold', ok ? 'bg-emerald-50 text-emerald-700 ring-1 ring-emerald-200' : 'bg-amber-50 text-amber-700 ring-1 ring-amber-200')}>
    {ok ? <CheckCircle2 className="h-4 w-4" /> : <AlertTriangle className="h-4 w-4" />}{children}</span>
}
