import { ReactNode, useEffect, useRef, useState } from 'react'
import {
  Activity, Bell, Check, CheckCircle2, Database, DatabaseBackup, Download, FileSpreadsheet, FileText, FolderOpen, Info,
  Network, Power, RefreshCw, RotateCcw, Save, ScrollText, Send, Settings as SettingsIcon, Shield, Trash2, Upload,
  Wrench, X, XCircle,
} from 'lucide-react'
import { api, download, qs, uploadFile } from '../lib/api'
import { applyTheme, THEMES, useAuth } from '../lib/auth'
import { LAYOUTS } from '../components/Layout'
import { useToast } from '../lib/toast'
import { fmtDateTime, fmtSize } from '../lib/format'
import {
  Badge, Button, cx, Empty, Input, Loading, Modal, PageHeader, Pagination, Panel, SearchInput, Select, StatusBadge, Table, Td,
  Th, Toggle, useConfirm,
} from '../components/ui'

const SECTIONS = [
  { key: 'general', label: 'General', icon: SettingsIcon }, { key: 'transfer', label: 'Transfer', icon: Send },
  { key: 'storage', label: 'Storage', icon: Database }, { key: 'security', label: 'Security', icon: Shield },
  { key: 'network', label: 'Network', icon: Network }, { key: 'notifications', label: 'Notification', icon: Bell },
  { key: 'backup', label: 'Backup', icon: DatabaseBackup }, { key: 'maintenance', label: 'Maintenance', icon: Wrench },
] as const
type Key = typeof SECTIONS[number]['key']

const THEME_SWATCH: Record<string, string> = { maroon: '#7e2a3d', blue: '#1b46ad', green: '#15643c', navy: '#304363', purple: '#6729c9' }
const POLICY_PRESETS: Record<string, any> = {
  basic: { label: 'Min 8 characters, with letters & numbers', v: { min_length: 8, require_upper: true, require_lower: true, require_digit: true, require_symbol: false } },
  strong: { label: 'Min 8 characters, letters, numbers & symbol', v: { min_length: 8, require_upper: true, require_lower: true, require_digit: true, require_symbol: true } },
  strict: { label: 'Min 12 characters, letters, numbers & symbol', v: { min_length: 12, require_upper: true, require_lower: true, require_digit: true, require_symbol: true } },
}

export default function SettingsPage() {
  const [data, setData] = useState<any>(null)
  const [vals, setVals] = useState<Record<string, any>>({})
  const [net, setNet] = useState<any>(null)
  const [saving, setSaving] = useState(false)
  const [focus, setFocus] = useState<Key>('general')
  const [dlg, setDlg] = useState<'' | 'logs' | 'audit' | 'nettest' | 'backups'>('')
  const refs = useRef<Record<string, HTMLDivElement | null>>({})
  const toast = useToast()
  const confirm = useConfirm()
  const { refresh, isSuper, session } = useAuth()

  const load = () => api.get('/api/settings').then((d) => {
    setData(d)
    setVals(Object.assign({}, ...Object.values(d.settings)))
    setNet({ ...d.network, allowed: d.network.allowed_subnets.join(', ') })
  })
  const previewLayout = (v: string) => window.dispatchEvent(new CustomEvent('os-layout-preview', { detail: v }))
  useEffect(() => { load(); return () => { applyTheme(session?.branding.theme); previewLayout('') } }, [])
  if (!data || !net) return <Loading />

  const all = Object.assign({}, ...Object.values(data.settings)) as Record<string, any>
  const groupOf = (k: string) => Object.keys(data.settings).find((g) => k in data.settings[g])!
  const canEditKey = (k: string) => data.can_edit && (!['security', 'backup'].includes(groupOf(k)) || isSuper)
  const dirty = Object.keys(all).filter((k) => JSON.stringify(all[k]) !== JSON.stringify(vals[k]))
  const netDirty = ['public_ip', 'port', 'subnet', 'https'].some((k) => String(net[k]) !== String(data.network[k])) || net.allowed !== data.network.allowed_subnets.join(', ')
  const set = (k: string, v: any) => { setVals((x) => ({ ...x, [k]: v })); if (k === 'theme') applyTheme(v); if (k === 'layout_style') previewLayout(v) }
  const ctl = (k: string) => ({ value: vals[k], set: (v: any) => set(k, v), disabled: !canEditKey(k) })

  const save = async () => {
    setSaving(true)
    try {
      if (dirty.length) {
        const editable = dirty.filter(canEditKey)
        await api.put('/api/settings', { values: Object.fromEntries(editable.map((k) => [k, vals[k]])) })
      }
      if (netDirty && isSuper) {
        const r = await api.put('/api/settings/network', { public_ip: net.public_ip, port: Number(net.port), subnet: net.subnet, https: net.https,
          allowed_subnets: String(net.allowed).split(',').map((s: string) => s.trim()).filter(Boolean) })
        toast.warning('Network settings saved', r.message)
      }
      toast.success('Settings saved')
      await load(); await refresh(); previewLayout('')
    } catch (e: any) { toast.error('Could not save', e.message) } finally { setSaving(false) }
  }
  const resetDefaults = async () => {
    if (!(await confirm({ title: 'Reset settings to default?', body: 'All editable settings on this page are set back to their factory defaults. Nothing changes until you click Save Changes. Server address and port are not affected.', confirmLabel: 'Reset', icon: RotateCcw }))) return
    setVals((x) => { const n = { ...x }; Object.keys(data.defaults).forEach((k) => { if (canEditKey(k)) n[k] = data.defaults[k] }); return n })
    applyTheme(data.defaults.theme); previewLayout(data.defaults.layout_style)
  }
  const jump = (k: Key) => { setFocus(k); refs.current[k]?.scrollIntoView({ behavior: 'smooth', block: 'start' }) }
  const card = (k: Key, title: string, icon: any, body: ReactNode) => (
    <div ref={(el) => { refs.current[k] = el }} className={cx('scroll-mt-4 rounded-2xl transition', focus === k && 'ring-2 ring-maroon-400 ring-offset-2')}>
      <Panel title={title} icon={icon} bodyClassName="space-y-2.5 p-4">{body}</Panel>
    </div>
  )

  return (
    <div className="pb-20">
      <PageHeader title="Settings – System Configuration" subtitle="Configure Application, Transfer, Security, Storage and Network Settings" icon={SettingsIcon} />
      <div className="mb-4 grid grid-cols-2 gap-2 sm:grid-cols-4 xl:grid-cols-8">
        {SECTIONS.map((s) => (
          <button key={s.key} onClick={() => jump(s.key)} className={cx('flex items-center justify-center gap-2 rounded-xl border px-3 py-2.5 text-[15.5px] font-semibold transition',
            focus === s.key ? 'border-maroon-700 bg-maroon-700 text-white shadow-md' : 'border-ink-200 bg-white text-ink-900 hover:border-maroon-300')}><s.icon className="h-5 w-5" />{s.label}</button>
        ))}
      </div>
      {!data.can_edit && <div className="mb-3 rounded-xl border border-ink-200 bg-ink-50 px-4 py-2.5 text-sm text-ink-700">You can view but not change settings.</div>}
      {data.can_edit && !isSuper && <div className="mb-3 rounded-xl border border-amber-200 bg-amber-50 px-4 py-2.5 text-sm text-amber-800">Security, backup and network settings can only be changed by a Super Admin.</div>}

      <div className="grid gap-4 xl:grid-cols-3">
        <div className="space-y-4">
          {card('general', 'General Settings', SettingsIcon, <>
            <Row label="Application Name"><TextIn {...ctl('app_name')} /></Row>
            <Row label="Office Name"><TextIn {...ctl('organisation_name')} max={120} placeholder="e.g. MES Office, Garrison Engineer (East)" /></Row>
            <Row label="Office Slogan"><TextIn {...ctl('organisation_slogan')} max={150} placeholder="Motto shown in small text under the office name" /></Row>
            {(vals.organisation_name || vals.organisation_slogan) && (
              <Row label="Header Preview">
                <div className="rounded-lg bg-gradient-to-r from-maroon-900 to-maroon-800 px-3 py-2 text-white">
                  <div className="truncate text-[15px] font-bold leading-tight">{vals.organisation_name || 'Office name'}</div>
                  {vals.organisation_slogan && <div className="truncate text-[11.5px] italic text-amber-100/90">“{vals.organisation_slogan}”</div>}
                </div>
              </Row>
            )}
            <Row label="Subtitle"><TextIn {...ctl('app_subtitle')} /></Row>
            <Row label="Logo"><LogoPicker {...ctl('logo_data_url')} /></Row>
            <Row label="Default Language"><Sel {...ctl('language')} opts={[['en-GB', 'English (UK)'], ['en-IN', 'English (India)'], ['hi-IN', 'Hindi (labels in English)']]} /></Row>
            <Row label="Date Format"><Sel {...ctl('date_format')} opts={[['DD/MM/YYYY', 'dd/mm/yyyy (23/11/2026)'], ['DD-MMM-YYYY', 'dd-MMM-yyyy (23-Nov-2026)'], ['YYYY-MM-DD', 'yyyy-mm-dd (2026-11-23)'], ['MM/DD/YYYY', 'mm/dd/yyyy (11/23/2026)']]} /></Row>
            <Row label="Time Format"><Sel {...ctl('time_format')} opts={[['12h', '12 Hour (HH:MM AM/PM)'], ['24h', '24 Hour (HH:MM)']]} /></Row>
            <Row label="Page Design" top>
              <div className="grid grid-cols-3 gap-2">
                {LAYOUTS.map((l) => {
                  const on = (vals.layout_style || 'classic') === l
                  return (
                    <button key={l} type="button" disabled={!canEditKey('layout_style')} onClick={() => set('layout_style', l)} aria-pressed={on}
                      className={cx('rounded-xl border-2 p-1.5 text-center transition disabled:opacity-50', on ? 'border-maroon-600 bg-maroon-50 shadow-md' : 'border-ink-200 hover:border-maroon-300')}>
                      <LayoutThumb kind={l} />
                      <div className="mt-1 flex items-center justify-center gap-1 text-[12.5px] font-bold">{on && <Check className="h-3.5 w-3.5 text-maroon-700" />}{l[0].toUpperCase() + l.slice(1)}</div>
                    </button>
                  )
                })}
              </div>
              <p className="mt-1.5 text-xs text-ink-500">Previews live. Office default for everyone after Save; users can choose their own in the profile menu.</p>
            </Row>
            <Row label="Theme / Colour">
              <div className="flex gap-2">
                {THEMES.map((t) => {
                  const on = vals.theme === t || (t === 'maroon' && !(THEMES as readonly string[]).includes(vals.theme))
                  return (
                    <button key={t} type="button" disabled={!canEditKey('theme')} onClick={() => set('theme', t)} title={t[0].toUpperCase() + t.slice(1)} aria-label={`${t} theme`}
                      className={cx('flex h-9 w-11 items-center justify-center rounded-lg shadow-sm ring-offset-2 transition disabled:opacity-50', on && 'ring-2 ring-ink-800')} style={{ background: THEME_SWATCH[t] }}>
                      {on && <Check className="h-5 w-5 text-white" />}
                    </button>
                  )
                })}
              </div>
            </Row>
          </>)}
          {card('security', 'Security & Access', Shield, <>
            <Row label="Password Policy">
              <select disabled={!canEditKey('password_policy')} className={fieldCls}
                value={Object.keys(POLICY_PRESETS).find((p) => JSON.stringify(POLICY_PRESETS[p].v) === JSON.stringify(vals.password_policy)) || 'custom'}
                onChange={(e) => e.target.value !== 'custom' && set('password_policy', POLICY_PRESETS[e.target.value].v)}>
                {Object.entries(POLICY_PRESETS).map(([k, p]) => <option key={k} value={k}>{p.label}</option>)}
                <option value="custom" disabled>Custom (min {vals.password_policy?.min_length})</option>
              </select>
            </Row>
            <Row label="Session Timeout"><Sel {...ctl('session_timeout_minutes')} num opts={[[15, '15 Minutes'], [30, '30 Minutes'], [60, '1 Hour'], [120, '2 Hours'], [240, '4 Hours'], [480, '8 Hours'], [720, '12 Hours']]} /></Row>
            <Row label="Max Login Attempts"><Sel {...ctl('max_login_attempts')} num opts={[3, 4, 5, 6, 8, 10].map((n) => [n, String(n)])} /></Row>
            <Row label="Lockout Duration"><Sel {...ctl('lockout_minutes')} num opts={[[5, '5 Minutes'], [15, '15 Minutes'], [30, '30 Minutes'], [60, '1 Hour']]} /></Row>
            <Tog label="Restrict Login to Registered PCs Only" {...ctl('registered_pc_restriction')} />
            <Tog label="Device Approval for New PCs" {...ctl('device_approval_required')} />
            <Tog label="Allow File Type Control (Whitelist)" {...ctl('file_whitelist_enforced')} />
          </>)}
        </div>

        <div className="space-y-4">
          {card('transfer', 'Transfer Settings', Send, <>
            <Row label="Maximum File Size per File"><div className="flex items-center gap-2"><NumIn {...ctl('max_file_size_mb')} min={1} /><Unit>MB</Unit></div></Row>
            <Row label="Maximum Files per Transfer"><Sel {...ctl('max_files_per_transfer')} num opts={[5, 10, 20, 30, 50, 100].map((n) => [n, String(n)])} /></Row>
            <Row label="Allowed File Types" top><ExtChips {...ctl('allowed_extensions')} /></Row>
            <Tog label="Enable Delivery Confirmation (default)" {...ctl('delivery_confirmation_default')} />
            <Tog label="Enable Read Receipt (default)" {...ctl('read_receipt_default')} />
            <Tog label="Auto Retry on Failure" hint="Re-sends to online PCs that have not acknowledged" {...ctl('auto_retry')} />
            <Row label="Retry Attempts"><Sel {...ctl('retry_attempts')} num opts={[1, 2, 3, 5, 8, 10].map((n) => [n, String(n)])} /></Row>
            <Row label="Retry Interval"><Sel {...ctl('retry_interval_seconds')} num opts={[[30, '30 Seconds'], [60, '1 Minute'], [120, '2 Minutes'], [300, '5 Minutes'], [600, '10 Minutes']]} /></Row>
          </>)}
          {card('notifications', 'Notification Settings', Bell, <>
            <Tog label="New Message Alert (Popup)" {...ctl('notify_new_message')} />
            <Tog label="New File Alert (Popup)" {...ctl('notify_new_file')} />
            <Tog label="Sound Notification" {...ctl('sound_notifications')} />
            <Tog label="Desktop Notification" hint="Needs HTTPS and the user's permission" {...ctl('desktop_notifications')} />
            <Tog label="Failed Transfer Alert" {...ctl('notify_failed_transfer')} />
          </>)}
          {card('backup', 'Backup & Restore', DatabaseBackup, <>
            <Tog label="Auto Backup (Database & Files)" {...ctl('auto_backup')} />
            <Tog label="Include stored files in backups" {...ctl('backup_include_files')} />
            <div className="grid grid-cols-2 gap-2">
              <Row label="Frequency" stacked><Sel {...ctl('backup_schedule')} opts={[['daily', 'Daily'], ['weekly', 'Weekly']]} /></Row>
              <Row label="Backup Time" stacked><input type="time" value={vals.backup_time} disabled={!canEditKey('backup_time')} onChange={(e) => set('backup_time', e.target.value)} className={fieldCls} /></Row>
            </div>
            {vals.backup_schedule === 'weekly' && <Row label="Day"><Sel {...ctl('backup_weekday')} num opts={['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday'].map((d, i) => [i, d])} /></Row>}
            <Row label="Keep last scheduled"><Sel {...ctl('backup_keep_count')} num opts={[7, 14, 30, 60].map((n) => [n, `${n} backups`])} /></Row>
            <Row label="Backup Location"><div className="flex items-center gap-2"><Input readOnly value={data.paths.backups} className="text-xs" /><FolderOpen className="h-5 w-5 shrink-0 text-ink-500" /></div></Row>
            <div className="grid grid-cols-2 gap-2 pt-1">
              <BackupNow disabled={!isSuper} />
              <Button variant="outline" icon={RotateCcw} disabled={!data.can_edit} onClick={() => setDlg('backups')}>Restore from Backup</Button>
            </div>
          </>)}
        </div>

        <div className="space-y-4">
          {card('storage', 'Storage & Retention', Database, <>
            <Row label="Data Storage Path"><div className="flex items-center gap-2"><Input readOnly value={data.paths.storage} className="text-xs" /><FolderOpen className="h-5 w-5 shrink-0 text-ink-500" /></div></Row>
            <Row label="Total Storage Quota"><div className="flex items-center gap-2"><NumIn {...ctl('storage_quota_gb')} min={0} /><Unit>GB</Unit></div></Row>
            <Row label="File Depository Quota"><div className="flex items-center gap-2"><NumIn {...ctl('repository_quota_gb')} min={0} /><Unit>GB</Unit></div></Row>
            <Row label="Auto Delete Received Data After"><Sel {...ctl('received_retention_days')} num opts={[[0, 'Never'], [30, '30 Days'], [60, '60 Days'], [90, '90 Days'], [180, '180 Days'], [365, '1 Year']]} /></Row>
            <Row label="Auto Delete Sent Data After"><Sel {...ctl('sent_retention_days')} num opts={[[0, 'Never'], [30, '30 Days'], [90, '90 Days'], [180, '180 Days'], [365, '1 Year']]} /></Row>
            <Row label="Keep Transfer History For"><Sel {...ctl('history_retention_days')} num opts={[[0, 'Forever'], [180, '6 Months'], [365, '1 Year'], [730, '2 Years'], [1825, '5 Years']]} /></Row>
            <p className="text-xs text-ink-500">0 GB = unlimited. Retention runs hourly; history retention erases records and files permanently.</p>
          </>)}
          {card('network', 'Network & Server', Network, <>
            <Row label="Server IP Address"><Input value={net.public_ip} disabled={!isSuper} onChange={(e) => setNet({ ...net, public_ip: e.target.value })} /></Row>
            <Row label="Server Port"><Input type="number" value={net.port} disabled={!isSuper} onChange={(e) => setNet({ ...net, port: e.target.value })} /></Row>
            <Row label="LAN Subnet"><Input value={net.subnet} disabled={!isSuper} onChange={(e) => setNet({ ...net, subnet: e.target.value })} /></Row>
            <Row label="IP Range (Allowed)"><Input value={net.allowed} disabled={!isSuper} onChange={(e) => setNet({ ...net, allowed: e.target.value })} placeholder="192.168.50.0/24" /></Row>
            <Row label="Network Mode"><Sel {...ctl('network_mode')} opts={[['lan+wifi', 'LAN + Wi-Fi (Offline)'], ['lan', 'LAN only (Offline)'], ['wifi', 'Wi-Fi only (Offline)']]} /></Row>
            <Tog label="Auto Discover Devices" {...ctl('device_discovery')} />
            <Tog label="HTTPS (internal certificate)" hint="Run Make_Certificates.bat on the server first" value={net.https} set={(v: boolean) => setNet({ ...net, https: v })} disabled={!isSuper} />
            <Row label="Device Heartbeat Interval"><Sel {...ctl('heartbeat_interval_seconds')} num opts={[[10, '10 Seconds'], [15, '15 Seconds'], [30, '30 Seconds'], [60, '1 Minute'], [120, '2 Minutes']]} /></Row>
            <Row label="Wi-Fi IP Ranges"><Input value={(vals.wifi_ip_ranges || []).join(', ')} disabled={!canEditKey('wifi_ip_ranges')} onChange={(e) => set('wifi_ip_ranges', e.target.value.split(',').map((s) => s.trim()).filter(Boolean))} placeholder="192.168.50.150-192.168.50.199" /></Row>
            {netDirty && <p className="rounded-lg bg-amber-50 px-3 py-2 text-xs text-amber-800">Address changes apply after a service restart. Update the Windows Firewall rule for a new port or subnet.</p>}
          </>)}
          {card('maintenance', 'System Maintenance', Wrench, <Maintenance isSuper={isSuper} canEdit={data.can_edit} open={setDlg} />)}
        </div>
      </div>

      <div className="os-savebar fixed bottom-0 left-0 right-0 z-30 border-t border-ink-200 bg-white/95 px-4 py-3 shadow-[0_-4px_20px_rgba(0,0,0,.06)] backdrop-blur lg:left-[240px]">
        <div className="mx-auto flex max-w-[1700px] flex-wrap items-center gap-3">
          <Info className="hidden h-5 w-5 text-maroon-700 2xl:block" />
          <span className="hidden text-sm 2xl:inline"><b>Note :</b> These settings apply to the entire Offline Share application. Changes may require service restart.</span>
          <span className="ml-auto text-sm text-ink-600">{dirty.length + (netDirty ? 1 : 0) ? `${dirty.length + (netDirty ? 1 : 0)} unsaved change(s)` : 'All changes saved'}</span>
          {(dirty.length > 0 || netDirty) && <Button variant="ghost" onClick={() => { load(); applyTheme(all.theme); previewLayout('') }}>Discard</Button>}
          <Button size="lg" icon={Save} loading={saving} disabled={!data.can_edit || (!dirty.length && !netDirty)} onClick={save}>Save Changes</Button>
          <Button size="lg" variant="outline" icon={RotateCcw} disabled={!data.can_edit} onClick={resetDefaults}>Reset to Default</Button>
        </div>
      </div>

      {dlg === 'logs' && <Modal open onClose={() => setDlg('')} size="xl" title="System Logs" icon={ScrollText}><LogsViewer /></Modal>}
      {dlg === 'audit' && <Modal open onClose={() => setDlg('')} size="xl" title="Audit Log" icon={FileText}><AuditViewer /></Modal>}
      {dlg === 'nettest' && <Modal open onClose={() => setDlg('')} size="lg" title="Network Connectivity Test" icon={Activity}><NetworkTest /></Modal>}
      {dlg === 'backups' && <Modal open onClose={() => setDlg('')} size="xl" title="Backups & Restore" icon={DatabaseBackup}><BackupList isSuper={isSuper} /></Modal>}
    </div>
  )
}

// ---------------------------------------------------------------- form atoms
const fieldCls = 'w-full rounded-lg border border-ink-200 bg-white px-3 py-2 text-sm text-ink-900 focus:border-maroon-400 focus:outline-none focus:ring-2 focus:ring-maroon-100 disabled:bg-ink-50 disabled:text-ink-500'
function Unit({ children }: { children: ReactNode }) { return <span className="rounded-lg border border-ink-200 bg-ink-50 px-3 py-2 text-sm font-semibold">{children}</span> }
function Row({ label, children, top, stacked }: { label: string; children: ReactNode; top?: boolean; stacked?: boolean }) {
  if (stacked) return <div><span className="mb-1 block text-[13.5px] font-semibold text-ink-800">{label}</span>{children}</div>
  return (
    <div className={cx('grid grid-cols-[minmax(130px,42%)_1fr] gap-3', top ? 'items-start' : 'items-center')}>
      <span className="text-[14px] font-medium text-ink-900">{label}</span><div className="min-w-0">{children}</div>
    </div>
  )
}
type C = { value: any; set: (v: any) => void; disabled: boolean }
function TextIn({ value, set, disabled, max, placeholder }: C & { max?: number; placeholder?: string }) { return <input className={fieldCls} value={value ?? ''} maxLength={max} placeholder={placeholder} disabled={disabled} onChange={(e) => set(e.target.value)} /> }
function NumIn({ value, set, disabled, min }: C & { min?: number }) { return <input type="number" min={min} className={fieldCls} value={value ?? ''} disabled={disabled} onChange={(e) => set(e.target.value === '' ? '' : Number(e.target.value))} /> }
function Sel({ value, set, disabled, opts, num }: C & { opts: (string | number)[][]; num?: boolean }) {
  const known = opts.some(([v]) => String(v) === String(value))
  return (
    <select className={fieldCls} value={value ?? ''} disabled={disabled} onChange={(e) => set(num ? Number(e.target.value) : e.target.value)}>
      {!known && value !== undefined && <option value={value}>{String(value)}</option>}
      {opts.map(([v, l]) => <option key={String(v)} value={v}>{l}</option>)}
    </select>
  )
}
function Tog({ label, hint, value, set, disabled }: C & { label: string; hint?: string }) {
  return <Toggle checked={!!value} onChange={set} disabled={disabled} label={<span className="text-[14px] font-medium">{label}</span>} description={hint} />
}
function ExtChips({ value, set, disabled }: C) {
  const [ext, setExt] = useState('')
  const list: string[] = value || []
  const add = () => { const e = ext.trim().toLowerCase().replace(/^\./, ''); if (e) set(Array.from(new Set([...list, e]))); setExt('') }
  return (
    <div className="flex flex-wrap gap-1.5 rounded-lg border border-ink-200 bg-white p-2">
      {list.map((e) => <span key={e} className="inline-flex items-center gap-1 rounded-md border border-ink-200 bg-ink-50 px-2 py-0.5 text-xs font-bold uppercase">{e}{!disabled && <button onClick={() => set(list.filter((x) => x !== e))} aria-label={`Remove ${e}`}><X className="h-3.5 w-3.5" /></button>}</span>)}
      {!disabled && <input value={ext} onChange={(e) => setExt(e.target.value)} onKeyDown={(e) => e.key === 'Enter' && add()} onBlur={add} placeholder="+ add" aria-label="Add file type" className="w-16 flex-1 text-xs outline-none" />}
    </div>
  )
}
function LogoPicker({ value, set, disabled }: C) {
  const input = useRef<HTMLInputElement>(null)
  const toast = useToast()
  const pick = (f: File) => {
    if (f.size > 300 * 1024) return toast.error('Logo must be under 300 KB')
    const r = new FileReader(); r.onload = () => set(r.result as string); r.readAsDataURL(f)
  }
  return (
    <div className="flex flex-wrap items-center gap-2">
      <span className="flex h-16 w-16 items-center justify-center overflow-hidden rounded-xl border border-ink-200 bg-white">{value ? <img src={value} alt="Logo" className="h-full w-full object-contain" /> : <span className="text-xs text-ink-400">No logo</span>}</span>
      <Button size="sm" variant="outline" icon={Upload} disabled={disabled} onClick={() => input.current?.click()}>Change Logo</Button>
      {value && <Button size="sm" variant="ghost" icon={Trash2} disabled={disabled} className="!text-red-600" onClick={() => set('')}>Remove</Button>}
      <input ref={input} type="file" accept="image/png,image/jpeg" hidden onChange={(e) => e.target.files?.[0] && pick(e.target.files[0])} />
    </div>
  )
}

// ---------------------------------------------------------------- backup
function BackupNow({ disabled }: { disabled: boolean }) {
  const [busy, setBusy] = useState(false)
  const toast = useToast()
  return <Button icon={DatabaseBackup} loading={busy} disabled={disabled} className="!bg-emerald-600 hover:!bg-emerald-700" onClick={async () => {
    setBusy(true)
    try { const b = await api.post('/api/system/backups', { include_files: true }); toast.success('Backup created', `${b.filename} (${fmtSize(b.size)})`) } catch (e: any) { toast.error('Backup failed', e.message) } finally { setBusy(false) }
  }}>Create Backup Now</Button>
}

function BackupList({ isSuper }: { isSuper: boolean }) {
  const [list, setList] = useState<any>(null)
  const [busy, setBusy] = useState(false)
  const toast = useToast()
  const confirm = useConfirm()
  const up = useRef<HTMLInputElement>(null)
  const load = () => api.get('/api/system/backups').then(setList).catch(() => {})
  useEffect(() => { load() }, [])
  const restore = async (b: any) => {
    if (!(await confirm({ title: 'Restore this backup?', danger: true, confirmLabel: 'Restore now', icon: RotateCcw, body: <>All current data is replaced with <b>{b.filename}</b> ({fmtDateTime(b.created_at)}). A safety backup of the current database is taken first. Users may need to sign in again.</> }))) return
    setBusy(true)
    try { const r = await api.post('/api/system/restore', { backup_id: b.id, restore_files: true }); toast.success('Restore complete', `${r.restored_files} files restored. Safety copy: ${r.safety_backup}`); setTimeout(() => location.reload(), 1500) } catch (e: any) { toast.error('Restore failed', e.message) } finally { setBusy(false) }
  }
  const restoreUpload = async (f: File) => {
    if (!(await confirm({ title: `Restore from ${f.name}?`, danger: true, confirmLabel: 'Upload & restore', body: 'All current data will be replaced. A safety backup is taken first.' }))) return
    setBusy(true)
    try { await uploadFile('/api/system/restore/upload', f).promise; toast.success('Restore complete'); setTimeout(() => location.reload(), 1500) } catch (e: any) { toast.error('Restore failed', e.message) } finally { setBusy(false) }
  }
  if (!list) return <Loading />
  return (
    <div>
      <div className="mb-3 flex flex-wrap items-center justify-between gap-2 text-sm">
        <span>Location: <span className="font-mono text-xs">{list.location}</span>{list.next_run && <> · next automatic backup <b>{new Date(list.next_run).toLocaleString('en-GB')}</b></>}</span>
        {isSuper && <><Button size="sm" variant="outline" icon={Upload} loading={busy} onClick={() => up.current?.click()}>Restore from file (.zip)</Button>
          <input ref={up} type="file" accept=".zip" hidden onChange={(e) => e.target.files?.[0] && restoreUpload(e.target.files[0])} /></>}
      </div>
      {list.items.length === 0 ? <Empty icon={Database} title="No backups yet" /> : (
        <Table><thead><tr><Th>File</Th><Th>Type</Th><Th>Contents</Th><Th>Size</Th><Th>Created</Th><Th>Status</Th><Th className="text-right">Actions</Th></tr></thead>
          <tbody>{list.items.map((b: any) => (
            <tr key={b.id}>
              <Td className="font-mono text-xs">{b.filename}{!b.exists && <Badge tone="red" className="ml-2">missing</Badge>}</Td>
              <Td><Badge tone={b.kind === 'scheduled' ? 'blue' : b.kind === 'restore' ? 'violet' : 'slate'}>{b.kind}</Badge></Td>
              <Td className="text-xs">{b.message}</Td><Td className="text-xs">{fmtSize(b.size)}</Td><Td className="whitespace-nowrap text-xs">{fmtDateTime(b.created_at)}</Td>
              <Td><StatusBadge status={b.status} /></Td>
              <Td className="whitespace-nowrap text-right">{isSuper && b.exists && b.kind !== 'restore' && <>
                <Button size="sm" variant="ghost" icon={Download} onClick={() => download(`/api/system/backups/${b.id}/download`)}>Download</Button>
                <Button size="sm" variant="ghost" icon={RotateCcw} disabled={busy} onClick={() => restore(b)}>Restore</Button>
                <Button size="sm" variant="ghost" icon={Trash2} aria-label="Delete backup" onClick={async () => { await api.del(`/api/system/backups/${b.id}`); load() }} />
              </>}</Td>
            </tr>))}</tbody></Table>
      )}
      {!isSuper && <p className="mt-3 text-xs text-ink-500">Only a Super Admin can create, download or restore backups.</p>}
    </div>
  )
}

// ---------------------------------------------------------------- maintenance
const TASK: Record<string, string> = { 'Clear Temporary Files': 'clear-temp', 'Rebuild Search Index': 'rebuild-index', 'Database Integrity Check': 'integrity-check', 'Optimise Database': 'optimise', 'Restart Service': 'restart' }

function Maintenance({ isSuper, canEdit, open }: { isSuper: boolean; canEdit: boolean; open: (d: any) => void }) {
  const [busy, setBusy] = useState('')
  const [out, setOut] = useState<Record<string, string>>({})
  const toast = useToast()
  const confirm = useConfirm()
  const run = async (task: string) => {
    if (task === 'restart' && !(await confirm({ title: 'Restart the OFFLINE SHARE service?', body: 'Everyone is disconnected for a few seconds and reconnects automatically. Nothing is lost.', confirmLabel: 'Restart', icon: Power }))) return
    setBusy(task)
    try { const r = await api.post(`/api/system/maintenance/${task}`); setOut((o) => ({ ...o, [task]: r.message })); toast.success(r.message) } catch (e: any) { toast.error(e.message) } finally { setBusy('') }
  }
  const rows: [string, any, string, () => void, boolean?][] = [
    ['Clear Temporary Files', Trash2, 'Clear Now', () => run('clear-temp')],
    ['Rebuild Search Index', RefreshCw, 'Rebuild', () => run('rebuild-index')],
    ['Database Integrity Check', CheckCircle2, 'Check Now', () => run('integrity-check')],
    ['Optimise Database', Database, 'Optimise', () => run('optimise')],
    ['View System Logs', ScrollText, 'View Logs', () => open('logs')],
    ['Audit Log', FileText, 'View', () => open('audit')],
    ['Network Connectivity Test', Activity, 'Run Test', () => open('nettest')],
  ]
  if (isSuper) rows.push(['Restart Service', Power, 'Restart', () => run('restart'), true])
  return (
    <div className="space-y-2">
      {rows.map(([label, I, btn, fn, danger]) => (
        <div key={label}>
          <div className="flex items-center justify-between gap-2">
            <span className="flex items-center gap-2.5 text-[14px] font-medium"><I className="h-5 w-5 text-ink-700" />{label}</span>
            <Button size="sm" variant={danger ? 'danger' : 'outline'} icon={I} className="min-w-[118px]" disabled={!canEdit} loading={busy === TASK[label]} onClick={fn}>{btn}</Button>
          </div>
          {out[TASK[label]] && <div className="ml-7 text-xs font-medium text-emerald-700">{out[TASK[label]]}</div>}
        </div>
      ))}
    </div>
  )
}

function NetworkTest() {
  const [r, setR] = useState<any>(null)
  const [lat, setLat] = useState<number[]>([])
  const [busy, setBusy] = useState(false)
  const run = async () => {
    setBusy(true)
    try {
      const res = await api.get('/api/system/network-test')
      const ts: number[] = []
      for (let i = 0; i < 5; i++) { const t0 = performance.now(); await api.get('/api/health'); ts.push(performance.now() - t0) }
      setR(res); setLat(ts)
    } finally { setBusy(false) }
  }
  useEffect(() => { run() }, [])
  return (
    <div>
      {!r ? <Loading label="Testing…" /> : (
        <div className="space-y-3">
          {r.checks.map((c: any) => <div key={c.name} className="flex items-start gap-2 text-sm">{c.ok ? <CheckCircle2 className="h-4 w-4 text-emerald-600" /> : <XCircle className="h-4 w-4 text-red-500" />}<div><b>{c.name}</b><div className="text-xs text-ink-500">{c.detail}</div></div></div>)}
          <div className="text-sm">Latency (5 pings): <b>{Math.round(Math.min(...lat))}–{Math.round(Math.max(...lat))} ms</b>, average {Math.round(lat.reduce((a, b) => a + b, 0) / lat.length)} ms</div>
          {r.interfaces.length > 0 && <div className="text-xs text-ink-600">Server interfaces: {r.interfaces.map((i: any) => `${i.interface} ${i.ip}${i.up ? '' : ' (down)'}`).join(' · ')}</div>}
        </div>
      )}
      <Button className="mt-4" size="sm" variant="outline" icon={RefreshCw} loading={busy} onClick={run}>Run again</Button>
    </div>
  )
}

function LogsViewer() {
  const [d, setD] = useState<any>(null)
  const [level, setLevel] = useState('')
  const load = () => api.get(`/api/system/logs${qs({ lines: 400, level })}`).then(setD)
  useEffect(() => { load() }, [level])
  return (
    <div>
      <div className="mb-2 flex items-center gap-2 text-xs text-ink-600"><span className="flex-1 truncate font-mono">{d?.path}</span>
        <Select value={level} onChange={(e) => setLevel(e.target.value)} className="!w-32 !py-1 text-xs"><option value="">All levels</option><option>INFO</option><option>WARNING</option><option>ERROR</option></Select>
        <Button size="sm" variant="outline" icon={RefreshCw} onClick={load}>Refresh</Button></div>
      <pre className="max-h-[60vh] overflow-auto rounded-xl bg-ink-900 p-4 font-mono text-[11.5px] leading-relaxed text-ink-100">{d ? (d.lines.length ? d.lines.join('\n') : 'No log entries.') : 'Loading…'}</pre>
    </div>
  )
}

function AuditViewer() {
  const [q, setQ] = useState('')
  const [page, setPage] = useState(1)
  const [d, setD] = useState<any>(null)
  useEffect(() => { const t = setTimeout(() => api.get(`/api/system/audit${qs({ q, page, page_size: 15 })}`).then(setD), 250); return () => clearTimeout(t) }, [q, page])
  return (
    <div>
      <div className="mb-3 flex gap-2"><SearchInput value={q} onChange={(v) => { setQ(v); setPage(1) }} placeholder="Search user, IP, action details" className="flex-1" />
        <Button variant="outline" icon={FileSpreadsheet} onClick={() => download('/api/system/audit/export.xlsx')}>Export</Button></div>
      {!d ? <Loading /> : (<>
        <Table><thead><tr><Th>Time</Th><Th>User</Th><Th>IP</Th><Th>Action</Th><Th>Details</Th></tr></thead>
          <tbody>{d.items.map((a: any) => (
            <tr key={a.id}><Td className="whitespace-nowrap text-xs">{fmtDateTime(a.at)}</Td><Td>{a.user}</Td><Td className="font-mono text-xs">{a.ip}</Td>
              <Td><Badge tone={/fail|block|delete|purge/.test(a.action) ? 'red' : 'slate'}>{a.action}</Badge></Td>
              <Td className="max-w-[380px] truncate font-mono text-[11px] text-ink-500" title={a.details}>{a.entity_id && `${a.entity_type}:${a.entity_id} `}{a.details}</Td></tr>))}</tbody></Table>
        <Pagination page={d.page} pageSize={d.page_size} total={d.total} onPage={setPage} />
      </>)}
    </div>
  )
}

/** Tiny schematic thumbnails of each page design. */
function LayoutThumb({ kind }: { kind: string }) {
  const brand = 'rgb(var(--brand-800))', soft = 'rgb(var(--brand-100))'
  return (
    <svg viewBox="0 0 90 60" className="h-auto w-full rounded-lg ring-1 ring-ink-100" aria-hidden>
      <rect width="90" height="60" fill={kind === 'modern' ? '#f7f5f9' : '#f7f4f5'} />
      {kind === 'classic' && <>
        <rect width="90" height="10" fill={brand} /><rect y="10" width="20" height="50" fill={brand} opacity=".92" />
        {[0, 1, 2, 3, 4].map((i) => <rect key={i} x="4" y={15 + i * 8} width="12" height="4" rx="2" fill={['#38bdf8', '#fb7185', '#34d399', '#a78bfa', '#fbbf24'][i]} />)}
        <rect x="25" y="15" width="60" height="9" rx="2" fill={soft} /><rect x="25" y="28" width="60" height="7" rx="1.5" fill={brand} /><rect x="25" y="35" width="60" height="20" rx="1.5" fill="#fff" />
      </>}
      {kind === 'modern' && <>
        <rect width="90" height="10" fill="#fff" /><rect x="3" y="3" width="22" height="4" rx="2" fill={brand} />
        <rect x="3" y="13" width="18" height="44" rx="5" fill="#fff" stroke="#ece6e8" />
        {[0, 1, 2, 3, 4].map((i) => <rect key={i} x="6" y={17 + i * 8} width="12" height="4" rx="2" fill={['#38bdf8', '#fb7185', '#34d399', '#a78bfa', '#fbbf24'][i]} />)}
        <rect x="25" y="13" width="61" height="10" rx="4" fill="#fff" stroke="#ece6e8" /><rect x="25" y="27" width="61" height="30" rx="5" fill="#fff" stroke="#ece6e8" />
        <rect x="25" y="27" width="2" height="8" fill={brand} /><rect x="29" y="29" width="20" height="3" rx="1.5" fill={brand} />
      </>}
      {kind === 'compact' && <>
        <rect width="90" height="7" fill={brand} /><rect y="7" width="9" height="53" fill={brand} opacity=".92" />
        {[0, 1, 2, 3, 4, 5].map((i) => <rect key={i} x="2.5" y={11 + i * 7} width="4" height="4" rx="1" fill={['#38bdf8', '#fb7185', '#34d399', '#a78bfa', '#fbbf24', '#94a3b8'][i]} />)}
        <rect x="12" y="10" width="75" height="6" rx="1.5" fill={soft} />
        {[0, 1, 2, 3, 4, 5].map((i) => <rect key={i} x="12" y={19 + i * 6.5} width="75" height="4.5" rx="1" fill={i === 0 ? brand : '#fff'} />)}
      </>}
    </svg>
  )
}
