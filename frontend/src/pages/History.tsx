import { useEffect, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import {
  CheckCircle2, CheckSquare, Clock, Database, Download, Eye, FileSpreadsheet, FileText, Filter, History as HistoryIcon,
  LayoutList, Paperclip, Printer, RefreshCw, RotateCcw, Send, Trash2, XCircle,
} from 'lucide-react'
import { api, download, qs } from '../lib/api'
import { useAuth } from '../lib/auth'
import { useRealtimeEvent } from '../lib/realtime'
import { useToast } from '../lib/toast'
import { fmtDate, fmtDateTime, fmtSize, fmtTime } from '../lib/format'
import {
  Button, Card, Checkbox, cx, Empty, ErrorBox, FileIcon, IconButton, Input, KV, Loading, PageHeader, Pagination, Panel,
  PriorityBadge, SearchInput, Select, StatCard, StatusBadge, Tabs, useConfirm,
} from '../components/ui'

type Tab = 'all' | 'sent' | 'received' | 'pending' | 'failed'
const EMPTY = { date_from: '', date_to: '', direction: '', status: '', file_type: '', q: '', pc: '' }
const iso = (d: Date) => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`

function rangeFor(r: string): { date_from: string; date_to: string } {
  const now = new Date()
  const today = iso(now)
  if (r === 'today') return { date_from: today, date_to: today }
  if (r === '7d') { const d = new Date(now); d.setDate(d.getDate() - 6); return { date_from: iso(d), date_to: today } }
  if (r === 'month') return { date_from: iso(new Date(now.getFullYear(), now.getMonth(), 1)), date_to: today }
  if (r === 'last_month') return { date_from: iso(new Date(now.getFullYear(), now.getMonth() - 1, 1)), date_to: iso(new Date(now.getFullYear(), now.getMonth(), 0)) }
  if (r === 'year') return { date_from: iso(new Date(now.getFullYear(), 0, 1)), date_to: today }
  return { date_from: '', date_to: '' }
}

export default function HistoryPage() {
  const [params] = useSearchParams()
  const { isAdmin, readOnly } = useAuth()
  const toast = useToast()
  const confirm = useConfirm()
  const [tab, setTab] = useState<Tab>((params.get('tab') as Tab) || 'all')
  const [scope, setScope] = useState<'mine' | 'all'>('mine')
  const [range, setRange] = useState('all')
  const [f, setF] = useState({ ...EMPTY, q: params.get('transfer') || '', pc: params.get('pc') || '' })
  const [applied, setApplied] = useState(f)
  const [page, setPage] = useState(1)
  const [pageSize, setPageSize] = useState(10)
  const [data, setData] = useState<any>(null)
  const [counts, setCounts] = useState<any>({})
  const [err, setErr] = useState('')
  const [sel, setSel] = useState<Set<number>>(new Set())
  const [active, setActive] = useState<string | null>(params.get('transfer'))

  const query = { tab, scope, ...applied }
  const load = () => {
    api.get(`/api/history${qs({ ...query, page, page_size: pageSize })}`).then((d) => {
      setData(d); setErr('')
      if (!active && d.items[0]) setActive(d.items[0].transfer_uid)
    }).catch((e) => setErr(e.message))
    api.get(`/api/history/counts?scope=${scope}`).then(setCounts).catch(() => {})
  }
  useEffect(load, [tab, scope, applied, page, pageSize])
  useEffect(() => { setPage(1); setSel(new Set()) }, [tab, scope, applied, pageSize])
  useRealtimeEvent((m) => { if (m.type === 'transfer.status' || m.type === 'transfer.new') load() }, [tab, scope, applied, page, pageSize])

  const items: any[] = data?.items || []
  const st = counts.stats || {}
  const retry = async (ids: number[]) => {
    const r = await api.post('/api/history/retry', { recipient_ids: ids })
    toast.success(`${r.retried} transfer(s) queued for retry`)
    load()
  }
  const del = async () => {
    const ids = Array.from(sel)
    if (!ids.length) return toast.info('Select records first')
    const ok = await confirm({
      title: 'Delete selected records?', danger: true, confirmLabel: 'Delete', icon: Trash2,
      body: isAdmin ? `${ids.length} record(s) will be permanently removed from transfer history for everyone. This action is audit-logged.`
        : `${ids.length} record(s) will be removed from your history view.`,
    })
    if (!ok) return
    const r = await api.post('/api/history/delete', { recipient_ids: ids })
    toast.success(`${r.deleted} record(s) deleted`)
    setSel(new Set())
    load()
  }
  const exportUrl = `/api/history/export.xlsx${qs(query)}`
  const failedSel = items.filter((i) => sel.has(i.id) && i.can_retry).map((i) => i.id)

  return (
    <div>
      <PageHeader title="Transfer History" subtitle="Complete Record of Sent and Received Data with Delivery Status" icon={HistoryIcon} />
      <div className="print-only mb-3 text-sm">OFFLINE SHARE – Transfer History report · printed {fmtDateTime(new Date().toISOString())}</div>

      <div className="mb-4 grid grid-cols-2 gap-3 md:grid-cols-3 xl:grid-cols-6">
        <StatCard label="Total Sent" value={st.total_sent ?? '—'} icon={Send} tone="pink" onClick={() => setTab('sent')} />
        <StatCard label="Total Received" value={st.total_received ?? '—'} icon={Download} tone="green" onClick={() => setTab('received')} />
        <StatCard label="Delivered" value={st.delivered ?? '—'} icon={CheckCircle2} tone="blue" />
        <StatCard label="Pending" value={st.pending ?? '—'} icon={Clock} tone="amber" onClick={() => setTab('pending')} />
        <StatCard label="Failed" value={st.failed ?? '—'} icon={XCircle} tone="red" onClick={() => setTab('failed')} />
        <StatCard label="Total Data" value={st.total_data !== undefined ? fmtSize(st.total_data) : '—'} icon={FileText} tone="violet" />
      </div>

      <Card className="mb-4 p-3 print:hidden">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <Tabs value={tab} onChange={setTab} tabs={[
            { value: 'all', label: 'All Transfers', icon: LayoutList, count: counts.all }, { value: 'sent', label: 'Sent Data', icon: Send, count: counts.sent },
            { value: 'received', label: 'Received Data', icon: Download, count: counts.received }, { value: 'pending', label: 'Pending', icon: Clock, count: counts.pending },
            { value: 'failed', label: 'Failed', icon: XCircle, count: counts.failed }]} />
          <div className="flex items-center gap-2">
            {isAdmin && (
              <Select value={scope} onChange={(e) => setScope(e.target.value as any)} className="w-40"><option value="mine">My transfers</option><option value="all">All users</option></Select>
            )}
            <span className="whitespace-nowrap text-sm font-semibold text-ink-800">Quick Range :</span>
            <Select value={range} className="w-40" onChange={(e) => {
              setRange(e.target.value)
              const r = rangeFor(e.target.value)
              setF((x) => ({ ...x, ...r })); setApplied((x) => ({ ...x, ...r }))
            }}>
              <option value="all">All time</option><option value="today">Today</option><option value="7d">Last 7 days</option>
              <option value="month">This Month</option><option value="last_month">Last Month</option><option value="year">This Year</option>
            </Select>
          </div>
        </div>
        <div className="mt-3 grid items-end gap-2 sm:grid-cols-3 lg:grid-cols-[150px_150px_190px_150px_150px_1fr_auto_auto]">
          <Lbl t="From Date"><Input type="date" value={f.date_from} onChange={(e) => setF({ ...f, date_from: e.target.value })} /></Lbl>
          <Lbl t="To Date"><Input type="date" value={f.date_to} onChange={(e) => setF({ ...f, date_to: e.target.value })} /></Lbl>
          <Lbl t="Direction"><Select value={f.direction} onChange={(e) => setF({ ...f, direction: e.target.value })}><option value="">All (Sent &amp; Received)</option><option value="sent">Sent</option><option value="received">Received</option></Select></Lbl>
          <Lbl t="Status"><Select value={f.status} onChange={(e) => setF({ ...f, status: e.target.value })}><option value="">All Status</option>{['pending', 'sent', 'delivered', 'read', 'failed'].map((s) => <option key={s} value={s}>{s[0].toUpperCase() + s.slice(1)}</option>)}</Select></Lbl>
          <Lbl t="Type"><Select value={f.file_type} onChange={(e) => setF({ ...f, file_type: e.target.value })}><option value="">All Types</option><option value="text">Text only</option>{['pdf', 'doc', 'docx', 'xls', 'xlsx', 'ppt', 'pptx', 'txt', 'jpg', 'jpeg', 'png', 'zip'].map((x) => <option key={x} value={x}>{x.toUpperCase()}</option>)}</Select></Lbl>
          <div className="flex items-center gap-2">
            <SearchInput value={f.q} onChange={(v) => setF({ ...f, q: v })} placeholder="Search by Transfer ID, PC/User, Subject or File Name…" className="flex-1" />
            {f.pc && <span className="inline-flex items-center gap-1 whitespace-nowrap rounded-lg bg-maroon-50 px-2 py-1.5 text-xs font-semibold text-maroon-800">PC: {f.pc}<button onClick={() => { setF({ ...f, pc: '' }); setApplied({ ...applied, pc: '' }) }} aria-label="Clear PC filter">×</button></span>}
          </div>
          <Button icon={Filter} onClick={() => setApplied(f)}>Filter</Button>
          <Button variant="outline" icon={RefreshCw} onClick={() => { setF(EMPTY); setApplied(EMPTY); setRange('all') }}>Reset</Button>
        </div>
      </Card>

      <div className="grid gap-4 min-[1650px]:grid-cols-[1fr_350px]">
        <Card className="min-w-0 overflow-hidden">
          {err ? <ErrorBox error={err} onRetry={load} /> : !data ? <Loading /> : items.length === 0 ? <Empty icon={HistoryIcon} title="No transfers found" body="Try a different tab, quick range or clear the filters." /> : (
            <div className="overflow-x-auto">
              <table className="w-full border-collapse text-left text-[12.5px]">
                <thead><tr className="bg-ink-100/80 text-ink-900">
                  <th className="w-10 px-3 py-2.5 print:hidden"><Checkbox checked={items.every((i) => sel.has(i.id))} onChange={(v) => setSel(v ? new Set(items.map((i) => i.id)) : new Set())} /></th>
                  {['S.No.', 'Transfer ID', 'Direction', 'From (PC / User)', 'To (PC / User)', 'Subject / File Name', 'Type', 'Size', 'Date & Time', 'Status'].map((h) => <th key={h} className="whitespace-nowrap px-1.5 py-2.5 font-bold">{h}</th>)}
                  <th className="px-1.5 py-2.5 text-center font-bold print:hidden">Action</th>
                </tr></thead>
                <tbody>
                  {items.map((r, i) => (
                    <tr key={r.id} onClick={() => setActive(r.transfer_uid)}
                      className={cx('cursor-pointer border-b border-ink-100 transition', active === r.transfer_uid ? 'bg-maroon-50' : 'hover:bg-ink-50')}>
                      <td className="px-3 py-2 print:hidden" onClick={(e) => e.stopPropagation()}><Checkbox checked={sel.has(r.id)} onChange={(v) => setSel((s) => { const n = new Set(s); v ? n.add(r.id) : n.delete(r.id); return n })} /></td>
                      <td className="px-1.5">{(data.page - 1) * data.page_size + i + 1}</td>
                      <td className="whitespace-nowrap px-1.5 font-medium tracking-tight">{r.transfer_uid}</td>
                      <td className="whitespace-nowrap px-1.5">{r.direction === 'received'
                        ? <span className="inline-flex items-center gap-1.5 font-medium text-sky-700"><Download className="h-4 w-4" />Received</span>
                        : <span className="inline-flex items-center gap-1.5 font-medium text-emerald-700"><Send className="h-4 w-4" />{r.direction === 'sent' ? 'Sent' : 'Transfer'}</span>}</td>
                      <td className="whitespace-nowrap px-1.5 leading-tight"><b>{r.sender_pc || r.sender_ip || '—'}</b><div className="text-ink-600">({r.sender_name})</div></td>
                      <td className="whitespace-nowrap px-1.5 leading-tight"><b>{r.recipient_pc || '—'}</b><div className="text-ink-600">({r.recipient_name})</div></td>
                      <td className="max-w-[190px] px-1.5"><div className="flex items-center gap-1.5"><span className="truncate">{r.subject}</span><PriorityBadge priority={r.priority} /></div></td>
                      <td className="px-1.5">{r.file_types.length ? <FileIcon ext={r.file_types[0]} className="h-6 w-6 text-[8px]" /> : <span className="text-xs text-ink-500">Text</span>}</td>
                      <td className="whitespace-nowrap px-1.5">{r.size ? fmtSize(r.size) : '—'}</td>
                      <td className="whitespace-nowrap px-1.5 leading-tight">{fmtDate(r.created_at)}<div>{fmtTime(r.created_at)}</div></td>
                      <td className="px-1.5"><StatusBadge status={r.status} /></td>
                      <td className="whitespace-nowrap px-2 text-center print:hidden" onClick={(e) => e.stopPropagation()}>
                        <IconButton icon={Eye} label="View details" onClick={() => setActive(r.transfer_uid)} />
                        {r.can_retry && !readOnly ? <IconButton icon={RotateCcw} label="Retry" onClick={() => retry([r.id])} />
                          : <IconButton icon={FileText} label="Export this transfer" onClick={() => download(`/api/history/export.xlsx${qs({ transfer_uid: r.transfer_uid, scope })}`)} />}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </Card>
        <div className="print:hidden">{active ? <TransferDetail uid={active} onRetry={retry} /> : <Panel title="Transfer Details" icon={FileText}><div className="py-8 text-center text-sm text-ink-500">Select a transfer to see its details.</div></Panel>}</div>
      </div>

      <div className="mt-4 flex flex-wrap items-center gap-2 print:hidden">
        <span className="inline-flex h-11 items-center gap-2 rounded-xl bg-maroon-700 px-5 text-[15px] font-semibold text-white shadow-md"><CheckSquare className="h-5 w-5" />{sel.size} Item{sel.size === 1 ? '' : 's'} Selected</span>
        <Button variant="outline" size="lg" icon={Download} onClick={() => download(exportUrl.replace('export.xlsx', 'export.csv'))}>Download</Button>
        <Button variant="outline" size="lg" icon={FileSpreadsheet} onClick={() => download(exportUrl)}>Export to Excel</Button>
        <Button variant="outline" size="lg" icon={Printer} onClick={() => window.print()}>Print</Button>
        {failedSel.length > 0 && !readOnly && <Button variant="outline" size="lg" icon={RotateCcw} onClick={() => retry(failedSel)}>Retry ({failedSel.length})</Button>}
        <Button size="lg" icon={Trash2} onClick={del} className="border border-red-200 bg-red-50 !text-red-600 hover:bg-red-100" variant="ghost">Delete</Button>
        <div className="ml-auto">{data && <Pagination page={data.page} pageSize={pageSize} total={data.total} onPage={setPage} onPageSize={setPageSize} />}</div>
      </div>
    </div>
  )
}

function Lbl({ t, children }: { t: string; children: React.ReactNode }) {
  return <label className="block"><span className="mb-1 block text-[13px] font-bold text-ink-800">{t}</span>{children}</label>
}

function TransferDetail({ uid, onRetry }: { uid: string; onRetry: (ids: number[]) => void }) {
  const [d, setD] = useState<any>(null)
  const [err, setErr] = useState('')
  const { readOnly } = useAuth()
  const load = () => api.get(`/api/history/transfer/${uid}`).then((x) => { setD(x); setErr('') }).catch((e) => setErr(e.message))
  useEffect(() => { setD(null); load() }, [uid])
  useRealtimeEvent((m) => { if (m.type === 'transfer.status' && m.transfer_uid === uid) load() }, [uid])
  if (err) return <Panel title="Transfer Details" icon={FileText}><ErrorBox error={err} /></Panel>
  if (!d) return <Panel title="Transfer Details" icon={FileText}><Loading /></Panel>
  const t = d.transfer
  const failed = d.recipients.filter((r: any) => r.status === 'failed')
  const one = d.recipients.length === 1 ? d.recipients[0] : null
  return (
    <div className="space-y-3">
      <Panel title="Transfer Details" icon={FileText}>
        <KV rows={[
          ['Transfer ID', <span className="font-mono">{t.transfer_uid}</span>],
          ['From', <><b>{d.sender.pc || d.sender.ip}</b> ({d.sender.name})</>],
          ['To', one ? <><b>{one.pc || '—'}</b> ({one.name})</> : `${d.recipients.length} receivers`],
          ['Date & Time', fmtDateTime(t.created_at)],
          ['Status', <span className="flex flex-wrap items-center gap-1.5"><StatusBadge status={d.aggregate} />{one?.read_at && <span className="text-xs text-ink-600">(Read at {fmtTime(one.read_at)})</span>}</span>],
          ['Subject', t.subject],
          ['Priority', t.priority[0].toUpperCase() + t.priority.slice(1)],
        ]} />
        {d.body_html && <>
          <div className="mb-1 mt-3 text-[13.5px] font-semibold text-ink-800">Message :</div>
          <div className="rich max-h-40 overflow-y-auto rounded-xl border border-ink-200 bg-ink-50/50 p-3 text-[13.5px]" dangerouslySetInnerHTML={{ __html: d.body_html }} />
        </>}
        {!one && (
          <div className="mt-3">
            <div className="mb-1 text-[13.5px] font-semibold text-ink-800">Delivery status per PC :</div>
            <ul className="max-h-48 divide-y divide-ink-100 overflow-y-auto rounded-xl border border-ink-200">
              {d.recipients.map((r: any) => (
                <li key={r.id} className="flex items-center justify-between gap-2 px-3 py-1.5 text-[13px]">
                  <span className="min-w-0 truncate"><b>{r.pc || '—'}</b> <span className="text-ink-600">({r.name})</span></span><StatusBadge status={r.status} />
                </li>
              ))}
            </ul>
          </div>
        )}
        {failed.length > 0 && !readOnly && <Button className="mt-3 w-full" icon={RotateCcw} onClick={() => { onRetry(failed.map((r: any) => r.id)); setTimeout(load, 400) }}>Retry {failed.length} failed</Button>}
      </Panel>
      {d.attachments.length > 0 && (
        <Panel title={`Attachments (${d.attachments.length})`} icon={Paperclip} actions={<span className="font-semibold">Total Size : {fmtSize(t.total_size)}</span>} bodyClassName="p-2">
          <ul className="divide-y divide-ink-100">
            {d.attachments.map((a: any) => (
              <li key={a.uid} className="flex items-center gap-2.5 px-2 py-2">
                <FileIcon ext={a.extension} className="h-7 w-7" />
                <span className="min-w-0 flex-1 truncate text-[13.5px] font-medium">{a.name}</span>
                <span className="whitespace-nowrap text-[13px] text-ink-700">{fmtSize(a.size)}</span>
                <IconButton icon={Download} label="Download" onClick={() => download(`/api/attachments/${a.uid}`)} />
                {['pdf', 'png', 'jpg', 'jpeg', 'txt'].includes(a.extension) && <IconButton icon={Eye} label="Open" onClick={() => window.open(`/api/attachments/${a.uid}?inline=1`, '_blank', 'noopener')} />}
              </li>
            ))}
          </ul>
        </Panel>
      )}
      <div className="flex items-center gap-1.5 px-1 text-xs text-ink-500"><Database className="h-3.5 w-3.5" />Delivered = the receiving PC acknowledged receipt.</div>
    </div>
  )
}
