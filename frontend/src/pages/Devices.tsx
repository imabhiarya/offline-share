import { useEffect, useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  BarChart3, Ban, CheckCircle2, Cable, Copy, Download, Edit3, Eye, FileSpreadsheet, KeyRound, Laptop, Layers, List, Monitor,
  MonitorCheck, MonitorSmartphone, MonitorX, Network, PlusCircle, Printer, RefreshCw, Router, Send, Server,
  ShieldQuestion, Trash2, Unlock, Users, Wifi, Filter, Lock,
} from 'lucide-react'
import { api, download, qs } from '../lib/api'
import { useAuth } from '../lib/auth'
import { copyText } from '../lib/clipboard'
import { useRealtimeEvent } from '../lib/realtime'
import { useToast } from '../lib/toast'
import { fmtDate, fmtDateTime, fmtTime } from '../lib/format'
import {
  ActionTile, Badge, Button, Card, CardHeader, Checkbox, cx, Empty, ErrorBox, Field, IconButton, Input, KV, Loading, Modal, OnlineDot, PageHeader,
  Pagination, Panel, SearchInput, Select, StatCard, StatusBadge, Tabs, Toggle, useConfirm,
} from '../components/ui'

type View = 'list' | 'map' | 'section' | 'stats'

export default function Devices() {
  const { isAdmin } = useAuth()
  const toast = useToast()
  const confirm = useConfirm()
  const nav = useNavigate()
  const [view, setView] = useState<View>('list')
  const [f, setF] = useState({ q: '', section: '', online: '', conn: '', status: '' })
  const [applied, setApplied] = useState(f)
  const [data, setData] = useState<any>(null)
  const [err, setErr] = useState('')
  const [sections, setSections] = useState<any[]>([])
  const [edit, setEdit] = useState<any>(null)
  const [agentOpen, setAgentOpen] = useState(false)
  const [auto, setAuto] = useState(true)
  const [activeId, setActiveId] = useState<number | null>(null)
  const [sel, setSel] = useState<Set<number>>(new Set())
  const [page, setPage] = useState(1)
  const [pageSize, setPageSize] = useState(10)

  const load = () => api.get(`/api/devices${qs({ q: applied.q, section_id: applied.section, status: applied.status, online: applied.online, connection: applied.conn })}`)
    .then((d) => { setData(d); setErr('') }).catch((e) => setErr(e.message))
  useEffect(() => { load(); setPage(1) }, [applied])
  useEffect(() => { api.get('/api/sections').then(setSections).catch(() => {}) }, [])
  useEffect(() => { if (!auto) return; const t = setInterval(load, 30000); return () => clearInterval(t) }, [auto, applied])
  useEffect(() => { const t = setTimeout(() => setApplied((a) => ({ ...a, q: f.q })), 300); return () => clearTimeout(t) }, [f.q])
  useRealtimeEvent((m) => { if (['presence', 'devices.changed', 'device.status'].includes(m.type)) load() }, [applied])

  const items: any[] = data?.items || []
  const active = items.find((d) => d.id === activeId) || items[0]
  const pageItems = items.slice((page - 1) * pageSize, page * pageSize)

  const setDevStatus = async (d: any, st: string) => {
    if (!d) return
    if (st === 'blocked' && !(await confirm({ title: `Block ${d.pc_name}?`, body: 'Users on this PC are signed out immediately and cannot sign in from it until it is unblocked.', danger: true, confirmLabel: 'Block PC', icon: Ban }))) return
    await api.post(`/api/devices/${d.id}/status`, { status: st })
    toast.success(`${d.pc_name}: ${st === 'approved' ? 'approved' : st === 'blocked' ? 'blocked' : 'set to pending'}`)
    load()
  }
  const remove = async (d: any) => {
    if (!(await confirm({ title: `Remove ${d.pc_name}?`, body: 'The device record is deleted. Transfer history keeps the PC name.', danger: true, confirmLabel: 'Remove' }))) return
    await api.del(`/api/devices/${d.id}`)
    load()
  }
  const sendTest = (d: any) => {
    if (!d?.users?.length) return toast.warning('No user is assigned to this PC', 'Assign a user in User Management first.')
    nav('/send', { state: { to: d.users.map((u: any) => u.id) } })
  }

  const s = data?.stats
  return (
    <div>
      <PageHeader title="Connected Devices" subtitle="View and Manage All PCs Connected to Offline Share Network" icon={Monitor} />
      {s && (
        <div className="mb-4 grid grid-cols-2 gap-3 md:grid-cols-3 xl:grid-cols-6">
          <StatCard label="Total Devices" value={s.total} icon={Monitor} tone="green" hint={s.pending ? `${s.pending} awaiting approval` : undefined} onClick={() => { setF({ ...f, online: '' }); setApplied({ ...applied, online: '' }) }} />
          <StatCard label="Online" value={s.online} icon={MonitorCheck} tone="green" onClick={() => { setF({ ...f, online: 'online' }); setApplied({ ...applied, online: 'online' }) }} />
          <StatCard label="Offline" value={s.offline} icon={MonitorX} tone="red" onClick={() => { setF({ ...f, online: 'offline' }); setApplied({ ...applied, online: 'offline' }) }} />
          <StatCard label="LAN (Wired)" value={s.lan} icon={Network} tone="blue" onClick={() => { setF({ ...f, conn: 'lan' }); setApplied({ ...applied, conn: 'lan' }) }} />
          <StatCard label="Wi-Fi (Wireless)" value={s.wifi} icon={Wifi} tone="violet" onClick={() => { setF({ ...f, conn: 'wifi' }); setApplied({ ...applied, conn: 'wifi' }) }} />
          <StatCard label="Active Users" value={s.active_users} icon={Users} tone="orange" />
        </div>
      )}

      <Card className="mb-4 p-3 print:hidden">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <Tabs value={view} onChange={setView} tabs={[{ value: 'list', label: 'Device List', icon: List }, { value: 'map', label: 'Network Map', icon: Network },
            { value: 'section', label: 'Section Wise', icon: Layers }, { value: 'stats', label: 'Device Statistics', icon: BarChart3 }]} />
          <div className="flex items-center gap-3">
            <div className="flex items-center gap-2 text-[14.5px] font-medium">Auto Refresh (30 sec) <Toggle checked={auto} onChange={setAuto} /></div>
            <Button variant="outline" icon={RefreshCw} onClick={load}>Refresh</Button>
          </div>
        </div>
        {view === 'list' && (
          <div className="mt-3 flex flex-wrap items-center gap-2">
            <SearchInput value={f.q} onChange={(v) => setF({ ...f, q: v })} placeholder="Search (PC Name / IP / User / Section)…" className="min-w-[240px] flex-1" />
            <span className="text-sm font-bold">Section :</span>
            <Select value={f.section} onChange={(e) => setF({ ...f, section: e.target.value })} className="w-40"><option value="">All Sections</option>{sections.map((x) => <option key={x.id} value={x.id}>{x.name}</option>)}</Select>
            <span className="text-sm font-bold">Status :</span>
            <Select value={f.online} onChange={(e) => setF({ ...f, online: e.target.value })} className="w-44"><option value="">All (Online &amp; Offline)</option><option value="online">Online</option><option value="offline">Offline</option></Select>
            <span className="text-sm font-bold">Connection :</span>
            <Select value={f.conn} onChange={(e) => setF({ ...f, conn: e.target.value })} className="w-40"><option value="">All (LAN &amp; Wi-Fi)</option><option value="lan">LAN (Wired)</option><option value="wifi">Wi-Fi</option><option value="unknown">Unknown</option></Select>
            <Select value={f.status} onChange={(e) => setF({ ...f, status: e.target.value })} className="w-40" aria-label="Approval"><option value="">Any approval</option><option value="approved">Approved</option><option value="pending">Pending approval</option><option value="blocked">Blocked</option></Select>
            <Button icon={Filter} onClick={() => setApplied(f)}>Filter</Button>
            <Button variant="outline" icon={RefreshCw} onClick={() => { const e = { q: '', section: '', online: '', conn: '', status: '' }; setF(e); setApplied(e) }}>Reset</Button>
          </div>
        )}
      </Card>

      {view === 'map' ? <NetworkMap /> : view === 'section' ? <SectionWise items={items} /> : view === 'stats' ? <DeviceStats items={items} /> : (
        <div className="grid gap-4 2xl:grid-cols-[1fr_400px]">
          <Card className="min-w-0 overflow-hidden">
            {err ? <ErrorBox error={err} onRetry={load} /> : !data ? <Loading /> : items.length === 0 ? <Empty icon={Monitor} title="No devices found" /> : (<>
              <div className="overflow-x-auto">
                <table className="w-full border-collapse text-left text-[13.5px]">
                  <thead><tr className="bg-ink-100/80">
                    <th className="w-10 px-3 py-2.5 print:hidden"><Checkbox checked={pageItems.every((d) => sel.has(d.id))} onChange={(v) => setSel(v ? new Set(pageItems.map((d) => d.id)) : new Set())} /></th>
                    {['S.No.', 'PC Name', 'IP Address', 'User Name', 'Section / Office', 'Connection', 'Status', 'Last Active'].map((h) => <th key={h} className="whitespace-nowrap px-2.5 py-2.5 font-bold">{h}</th>)}
                    <th className="px-2.5 py-2.5 text-center font-bold print:hidden">Actions</th>
                  </tr></thead>
                  <tbody>
                    {pageItems.map((d, i) => (
                      <tr key={d.id} onClick={() => setActiveId(d.id)} className={cx('cursor-pointer border-b border-ink-100', active?.id === d.id ? 'bg-maroon-50' : 'hover:bg-ink-50', d.status === 'blocked' && 'opacity-60')}>
                        <td className="px-3 py-2 print:hidden" onClick={(e) => e.stopPropagation()}><Checkbox checked={sel.has(d.id)} onChange={(v) => setSel((x) => { const n = new Set(x); v ? n.add(d.id) : n.delete(d.id); return n })} /></td>
                        <td className="px-2.5">{(page - 1) * pageSize + i + 1}</td>
                        <td className="whitespace-nowrap px-2.5 font-bold">{d.pc_name}{d.is_unknown && <Badge tone="amber" className="ml-1.5"><ShieldQuestion className="h-3 w-3" />Unknown</Badge>}{d.status === 'pending' && <Badge tone="amber" className="ml-1.5">Pending</Badge>}{d.status === 'blocked' && <Badge tone="red" className="ml-1.5"><Lock className="h-3 w-3" />Blocked</Badge>}</td>
                        <td className="whitespace-nowrap px-2.5">{d.ip_address || '—'}</td>
                        <td className="px-2.5">{d.users.map((u: any) => u.full_name).join(', ') || <span className="text-ink-400">—</span>}</td>
                        <td className="px-2.5">{d.section || '—'}</td>
                        <td className="whitespace-nowrap px-2.5">{d.connection_type === 'wifi' ? <span className="inline-flex items-center gap-1.5 font-medium text-sky-700"><Wifi className="h-4 w-4" />Wi-Fi</span>
                          : d.connection_type === 'lan' ? <span className="inline-flex items-center gap-1.5 font-medium text-emerald-700"><Network className="h-4 w-4" />LAN</span> : <span className="text-ink-500">Unknown</span>}</td>
                        <td className="px-2.5"><StatusBadge status={d.online ? 'online' : 'offline'} /></td>
                        <td className="whitespace-nowrap px-2.5 leading-tight">{d.online ? fmtTime(d.last_seen_at) : d.last_seen_at ? <>Since {fmtDate(d.last_seen_at)},<div>{fmtTime(d.last_seen_at)}</div></> : 'Never'}</td>
                        <td className="whitespace-nowrap px-2 text-center print:hidden" onClick={(e) => e.stopPropagation()}>
                          <IconButton icon={Eye} label="View" onClick={() => setActiveId(d.id)} />
                          {isAdmin && <IconButton icon={Edit3} label="Edit" onClick={() => setEdit(d)} />}
                          {isAdmin && <IconButton icon={Trash2} tone="danger" label="Remove" onClick={() => remove(d)} />}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              <Pagination page={page} pageSize={pageSize} total={items.length} onPage={setPage} onPageSize={(n) => { setPageSize(n); setPage(1) }} label="devices" />
            </>)}
          </Card>

          <div className="space-y-4 print:hidden">
            <Panel title="Device Details" icon={Monitor}>
              {!active ? <div className="py-8 text-center text-sm text-ink-500">Select a device.</div> : (<>
                <div className="flex gap-4">
                  <span className="flex h-20 w-24 shrink-0 items-center justify-center rounded-xl border border-ink-200 bg-gradient-to-b from-sky-50 to-white">
                    {active.connection_type === 'wifi' ? <Laptop className="h-12 w-12 text-ink-800" strokeWidth={1.4} /> : <Monitor className="h-12 w-12 text-ink-800" strokeWidth={1.4} />}
                  </span>
                  <div className="min-w-0 flex-1">
                    <div className="mb-1.5 flex items-center justify-between gap-2"><span className="truncate text-[19px] font-extrabold">{active.pc_name}</span><StatusBadge status={active.online ? 'online' : 'offline'} /></div>
                    <KV rows={[
                      ['PC Name', active.pc_name], ['IP Address', active.ip_address || '—'], ['User Name', active.users.map((u: any) => u.full_name).join(', ') || '—'],
                      ['Section', active.section || '—'],
                      ['Connection', active.connection_type === 'wifi' ? 'Wi-Fi (Wireless)' : active.connection_type === 'lan' ? 'LAN (Wired)' : 'Unknown'],
                      ['Last Active', fmtDateTime(active.last_seen_at)],
                      ['Browser', active.browser_active ? 'Session active' : 'No session'],
                      ['Agent', active.agent_installed ? `v${active.agent_version || '?'}${active.agent_online ? ' · reporting' : ' · silent'}` : 'Not installed'],
                      ['Approval', <StatusBadge status={active.status} />],
                    ]} />
                  </div>
                </div>
                <div className="mt-3 grid grid-cols-3 gap-2">
                  <ActionTile icon={BarChart3} label="View Activity" onClick={() => nav(`/history?pc=${encodeURIComponent(active.pc_name)}`)} />
                  {isAdmin && (active.status === 'blocked'
                    ? <ActionTile icon={Unlock} label="Unblock" tone="green" onClick={() => setDevStatus(active, 'approved')} />
                    : <ActionTile icon={Lock} label="Block Device" tone="red" onClick={() => setDevStatus(active, 'blocked')} />)}
                  {isAdmin && active.status === 'pending' && <ActionTile icon={CheckCircle2} label="Approve" tone="green" onClick={() => setDevStatus(active, 'approved')} />}
                  {isAdmin && active.status !== 'pending' && <ActionTile icon={Edit3} label="Edit Device" tone="blue" onClick={() => setEdit(active)} />}
                </div>
              </>)}
            </Panel>
            <Panel title="Quick Actions" icon={MonitorSmartphone}>
              <div className="grid grid-cols-3 gap-2">
                <ActionTile icon={PlusCircle} label="Add Device" tone="green" disabled={!isAdmin} onClick={() => setEdit({})} />
                <ActionTile icon={Edit3} label="Edit Device" tone="blue" disabled={!isAdmin || !active} onClick={() => setEdit(active)} />
                <ActionTile icon={Lock} label="Block / Unblock" tone="amber" disabled={!isAdmin || !active} onClick={() => setDevStatus(active, active?.status === 'blocked' ? 'approved' : 'blocked')} />
                <ActionTile icon={Send} label="Send Test Data" tone="violet" disabled={!active} onClick={() => sendTest(active)} />
                <ActionTile icon={FileSpreadsheet} label="Export List (Excel)" onClick={() => download('/api/devices/export.xlsx')} />
                <ActionTile icon={Printer} label="Print Report" onClick={() => window.print()} />
              </div>
              {isAdmin && <button onClick={() => setAgentOpen(true)} className="mt-3 flex w-full items-center justify-center gap-2 rounded-lg border border-dashed border-ink-300 py-2 text-sm font-semibold text-ink-700 hover:border-maroon-400 hover:text-maroon-700"><KeyRound className="h-4 w-4" />Client agent setup &amp; enrolment key</button>}
            </Panel>
          </div>
        </div>
      )}
      {edit && <DeviceForm device={edit} sections={sections} onClose={() => setEdit(null)} onSaved={() => { setEdit(null); load() }} />}
      {agentOpen && <AgentInfo onClose={() => setAgentOpen(false)} />}
    </div>
  )
}

function SectionWise({ items }: { items: any[] }) {
  const groups = useMemo(() => {
    const m = new Map<string, any[]>()
    items.forEach((d) => m.set(d.section || 'Unassigned', [...(m.get(d.section || 'Unassigned') || []), d]))
    return Array.from(m.entries()).sort((a, b) => a[0].localeCompare(b[0]))
  }, [items])
  if (!items.length) return <Card><Empty icon={Layers} title="No devices" /></Card>
  return (
    <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
      {groups.map(([sec, list]) => {
        const on = list.filter((d) => d.online).length
        return (
          <Panel key={sec} title={sec} icon={Layers} actions={<span className="font-semibold">{on} / {list.length} online</span>} bodyClassName="p-0">
            <ul className="divide-y divide-ink-100">
              {list.map((d) => (
                <li key={d.id} className="flex items-center justify-between gap-2 px-4 py-2 text-[13.5px]">
                  <span className="flex min-w-0 items-center gap-2"><OnlineDot online={d.online} /><b className="truncate">{d.pc_name}</b><span className="truncate text-ink-600">{d.users[0]?.full_name}</span></span>
                  <span className="whitespace-nowrap text-ink-600">{d.ip_address} · {d.connection_type === 'wifi' ? 'Wi-Fi' : 'LAN'}</span>
                </li>
              ))}
            </ul>
          </Panel>
        )
      })}
    </div>
  )
}

function DeviceStats({ items }: { items: any[] }) {
  const count = (fn: (d: any) => boolean) => items.filter(fn).length
  const rows: [string, [string, number, string][]][] = [
    ['Presence', [['Online', count((d) => d.online), 'bg-emerald-500'], ['Offline', count((d) => !d.online), 'bg-ink-400']]],
    ['Connection', [['LAN (Wired)', count((d) => d.connection_type === 'lan'), 'bg-sky-500'], ['Wi-Fi', count((d) => d.connection_type === 'wifi'), 'bg-violet-500'], ['Unknown', count((d) => d.connection_type === 'unknown'), 'bg-ink-300']]],
    ['Approval', [['Approved', count((d) => d.status === 'approved'), 'bg-emerald-500'], ['Pending', count((d) => d.status === 'pending'), 'bg-amber-500'], ['Blocked', count((d) => d.status === 'blocked'), 'bg-red-500']]],
    ['Monitoring', [['Agent installed', count((d) => d.agent_installed), 'bg-maroon-600'], ['Browser only', count((d) => !d.agent_installed), 'bg-ink-300'], ['Active browser session', count((d) => d.browser_active), 'bg-sky-500']]],
  ]
  const total = Math.max(1, items.length)
  return (
    <div className="grid gap-4 md:grid-cols-2">
      {rows.map(([title, parts]) => (
        <Card key={title} className="p-5">
          <h3 className="mb-3 text-[17px] font-bold">{title}</h3>
          <div className="space-y-3">
            {parts.map(([label, n, color]) => (
              <div key={label}>
                <div className="mb-1 flex justify-between text-sm"><span>{label}</span><b>{n} <span className="font-normal text-ink-500">({Math.round(n / total * 100)}%)</span></b></div>
                <div className="h-2.5 overflow-hidden rounded-full bg-ink-100"><div className={cx('h-full rounded-full', color)} style={{ width: `${n / total * 100}%` }} /></div>
              </div>
            ))}
          </div>
        </Card>
      ))}
    </div>
  )
}

function DeviceForm({ device, sections, onClose, onSaved }: { device: any; sections: any[]; onClose: () => void; onSaved: () => void }) {
  const [f, setF] = useState({ pc_name: device.pc_name || '', ip_address: device.ip_address || '', mac_address: device.mac_address || '', section_id: device.section_id || '', connection_type: device.connection_type || 'lan', status: device.status || 'approved', notes: device.notes || '' })
  const [err, setErr] = useState('')
  const [busy, setBusy] = useState(false)
  const toast = useToast()
  const save = async () => {
    setBusy(true); setErr('')
    try {
      const body = { ...f, section_id: f.section_id ? Number(f.section_id) : null }
      device.id ? await api.put(`/api/devices/${device.id}`, body) : await api.post('/api/devices', body)
      toast.success(device.id ? 'Device updated' : 'Device added')
      onSaved()
    } catch (e: any) { setErr(e.message) } finally { setBusy(false) }
  }
  return (
    <Modal open onClose={onClose} title={device.id ? `Edit ${device.pc_name}` : 'Add Device'} icon={Monitor}
      footer={<><Button variant="outline" onClick={onClose}>Cancel</Button><Button loading={busy} onClick={save}>Save</Button></>}>
      <div className="grid gap-3 sm:grid-cols-2">
        <Field label="PC name" required hint="Windows computer name, e.g. ACC-PC-01"><Input value={f.pc_name} onChange={(e) => setF({ ...f, pc_name: e.target.value })} /></Field>
        <Field label="IP address" hint="Use a DHCP reservation so the IP stays fixed"><Input value={f.ip_address} onChange={(e) => setF({ ...f, ip_address: e.target.value })} placeholder="192.168.50.101" /></Field>
        <Field label="MAC address"><Input value={f.mac_address} onChange={(e) => setF({ ...f, mac_address: e.target.value })} placeholder="AA:BB:CC:DD:EE:FF" /></Field>
        <Field label="Section"><Select value={f.section_id} onChange={(e) => setF({ ...f, section_id: e.target.value })}><option value="">—</option>{sections.map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}</Select></Field>
        <Field label="Connection type"><Select value={f.connection_type} onChange={(e) => setF({ ...f, connection_type: e.target.value })}><option value="lan">LAN (wired)</option><option value="wifi">Wi-Fi (wireless)</option><option value="unknown">Unknown</option></Select></Field>
        <Field label="Approval"><Select value={f.status} onChange={(e) => setF({ ...f, status: e.target.value })}><option value="approved">Approved</option><option value="pending">Pending</option><option value="blocked">Blocked</option></Select></Field>
        <Field label="Notes" className="sm:col-span-2"><Input value={f.notes} onChange={(e) => setF({ ...f, notes: e.target.value })} /></Field>
      </div>
      {err && <div className="mt-3 rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700">{err}</div>}
    </Modal>
  )
}

function AgentInfo({ onClose }: { onClose: () => void }) {
  const [k, setK] = useState<any>(null)
  const toast = useToast()
  useEffect(() => { api.get('/api/devices/agent-key').then(setK).catch((e) => toast.error(e.message)) }, [])
  const cmd = k ? `OfflineShareAgent.exe install --server ${k.server_url} --key ${k.enrolment_key}` : ''
  return (
    <Modal open onClose={onClose} title="Optional Windows client agent" icon={KeyRound} size="lg">
      <div className="space-y-3 text-sm text-ink-700">
        <p>The agent is a small Windows service that reports the PC's presence every heartbeat interval, even when no browser is open. It does not transfer files and needs no internet access.</p>
        <ol className="list-decimal space-y-1 pl-5">
          <li>Run <b>OFFLINE_SHARE_Client_Agent_Setup.exe</b> on the client PC as administrator.</li>
          <li>Enter the server URL and the enrolment key below when asked (or run the command).</li>
          <li>The PC appears here as <i>pending</i>; approve it.</li>
        </ol>
        {k && (<>
          <Field label="Server URL"><Input readOnly value={k.server_url} /></Field>
          <Field label="Enrolment key" hint="Keep this private. Anyone with the key can register a PC (which still needs approval)."><Input readOnly value={k.enrolment_key} className="font-mono" /></Field>
          <div className="rounded-lg bg-ink-900 p-3 font-mono text-xs text-white">{cmd}</div>
          <Button size="sm" variant="outline" icon={Copy} onClick={() => copyText(cmd).then(() => toast.success('Command copied'))}>Copy command</Button>
        </>)}
      </div>
    </Modal>
  )
}

function NetworkMap() {
  const [m, setM] = useState<any>(null)
  useEffect(() => { api.get('/api/devices/network-map').then(setM) }, [])
  useRealtimeEvent((e) => { if (['presence', 'devices.changed'].includes(e.type)) api.get('/api/devices/network-map').then(setM) }, [])
  if (!m) return <Loading />
  const Node = ({ icon: I, title, sub, tone = 'maroon', online }: any) => (
    <div className={cx('flex min-w-[150px] items-center gap-2.5 rounded-xl border bg-white px-3 py-2 shadow-card', tone === 'maroon' ? 'border-maroon-200' : 'border-ink-100')}>
      <span className={cx('flex h-9 w-9 items-center justify-center rounded-lg', tone === 'maroon' ? 'bg-maroon-700 text-white' : tone === 'violet' ? 'bg-violet-50 text-violet-700' : 'bg-sky-50 text-sky-700')}><I className="h-4 w-4" /></span>
      <div className="min-w-0"><div className="truncate text-sm font-semibold">{title}</div><div className="truncate text-[11px] text-ink-500">{sub}</div></div>
      {online !== undefined && <OnlineDot online={online} />}
    </div>
  )
  const Group = ({ items, icon, tone }: any) => (
    <div className="grid gap-2 sm:grid-cols-2">
      {items.length === 0 && <div className="text-sm text-ink-400">No devices</div>}
      {items.map((d: any) => <Node key={d.id} icon={icon} tone={tone} title={d.pc_name} sub={`${d.ip_address} · ${d.users[0]?.full_name || d.section || ''}`} online={d.online} />)}
    </div>
  )
  return (
    <Card className="p-6">
      <CardHeader title="Network map" subtitle={`Subnet ${m.server.subnet}`} icon={Network} />
      <div className="flex flex-col items-center gap-0 pt-6">
        <Node icon={Server} title="Main Server" sub={`${m.server.ip}:${m.server.port}`} online />
        <div className="h-8 w-0.5 bg-maroon-200" />
        <Node icon={Router} title="LAN Switch / Router" sub="192.168.50.1" tone="slate" />
        <div className="h-8 w-0.5 bg-maroon-200" />
        <div className="h-0.5 w-2/3 bg-maroon-200" />
        <div className="grid w-full gap-6 pt-0 lg:grid-cols-2">
          <div className="flex flex-col items-center">
            <div className="h-8 w-0.5 bg-maroon-200" />
            <div className="mb-3 flex items-center gap-2 text-sm font-semibold text-sky-800"><Cable className="h-4 w-4" />Wired PCs ({m.wired.length})</div>
            <Group items={m.wired} icon={Monitor} tone="blue" />
          </div>
          <div className="flex flex-col items-center">
            <div className="h-8 w-0.5 bg-maroon-200" />
            <Node icon={Wifi} title="Wi-Fi Access Point" sub="192.168.50.2" tone="violet" />
            <div className="h-6 w-0.5 border-l-2 border-dashed border-violet-300" />
            <div className="mb-3 flex items-center gap-2 text-sm font-semibold text-violet-800"><Wifi className="h-4 w-4" />Wireless PCs ({m.wireless.length})</div>
            <Group items={m.wireless} icon={Laptop} tone="violet" />
          </div>
        </div>
      </div>
      <div className="mt-6 flex justify-center"><Button size="sm" variant="ghost" icon={Download} onClick={() => window.print()}>Print map</Button></div>
    </Card>
  )
}
