import { useEffect, useRef, useState } from 'react'
import {
  CheckCircle2, Crown, Edit3, Eye, FileDown, FileSpreadsheet, FileUp, Filter, KeyRound, Monitor, Plus, RefreshCw, Shield,
  ShieldCheck, Trash2, User as UserIcon, UserCheck, UserCog, UserPlus, Users as UsersIcon, UserX, Ban, Lock, Download,
} from 'lucide-react'
import { api, download, qs, uploadFile } from '../lib/api'
import { useAuth } from '../lib/auth'
import { copyText } from '../lib/clipboard'
import { useToast } from '../lib/toast'
import { fmtDate, fmtDateTime, fmtTime } from '../lib/format'
import {
  ActionTile, Button, Card, Checkbox, cx, Empty, ErrorBox, Field, IconButton, Input, KV, Loading, Modal, PageHeader, Pagination,
  Panel, SearchInput, Select, StatCard, StatusBadge,
} from '../components/ui'

function RolePill({ role, name }: { role: string; name: string }) {
  if (role === 'super_admin' || role === 'admin') return <span className="inline-flex items-center gap-1.5 rounded-lg bg-red-50 px-2.5 py-1 text-[13px] font-semibold text-red-700 ring-1 ring-red-200"><Crown className="h-4 w-4" />{role === 'super_admin' ? 'Super Admin' : 'Admin'}</span>
  if (role === 'readonly') return <span className="inline-flex items-center gap-1.5 whitespace-nowrap rounded-lg bg-violet-50 px-2.5 py-1 text-[13px] font-semibold text-violet-700 ring-1 ring-violet-200"><Eye className="h-4 w-4" />Read Only</span>
  return <span className="inline-flex items-center gap-1.5 rounded-lg bg-sky-50 px-2.5 py-1 text-[13px] font-semibold text-sky-700 ring-1 ring-sky-200"><UserIcon className="h-4 w-4" />{name === 'Normal User' ? 'User' : name}</span>
}

const PERM_LABEL: Record<string, string> = { send: 'Send Data', receive: 'Receive Data', files: 'File Depository', history: 'Transfer History', devices: 'Connected Devices', users: 'User Management', settings: 'Settings', dashboard: 'Dashboard' }

export default function UsersPage() {
  const { isSuper, session } = useAuth()
  const toast = useToast()
  const [f, setF] = useState({ q: '', role: '', section: '', status: '' })
  const [applied, setApplied] = useState(f)
  const [page, setPage] = useState(1)
  const [pageSize, setPageSize] = useState(10)
  const [data, setData] = useState<any>(null)
  const [meta, setMeta] = useState<any>(null)
  const [err, setErr] = useState('')
  const [edit, setEdit] = useState<any>(null)
  const [importOpen, setImportOpen] = useState(false)
  const [tempPwd, setTempPwd] = useState<{ name: string; pwd: string } | null>(null)
  const [sel, setSel] = useState<Set<number>>(new Set())
  const [activeId, setActiveId] = useState<number | null>(null)
  const [roleDlg, setRoleDlg] = useState<any[] | null>(null)
  const [confirmDlg, setConfirmDlg] = useState<{ title: string; body: string; label: string; danger?: boolean; run: () => Promise<void> } | null>(null)

  const load = () => api.get(`/api/users${qs({ q: applied.q, role: applied.role, section_id: applied.section, status: applied.status, page, page_size: pageSize })}`)
    .then((d) => { setData(d); setErr('') }).catch((e) => setErr(e.message))
  useEffect(() => { load() }, [applied, page, pageSize])
  useEffect(() => { setPage(1) }, [applied, pageSize])
  useEffect(() => { const t = setTimeout(() => setApplied((a) => ({ ...a, q: f.q })), 300); return () => clearTimeout(t) }, [f.q])
  useEffect(() => { api.get('/api/users/meta').then(setMeta) }, [])

  const items: any[] = data?.items || []
  const active = items.find((u) => u.id === activeId) || items[0]
  const deviceIp = (id: number | null) => meta?.devices.find((d: any) => d.id === id)?.ip_address
  const canTouch = (u: any) => u && (u.role !== 'super_admin' || isSuper)
  const selected = items.filter((u) => sel.has(u.id))
  const targets = (u?: any) => (u ? [u] : selected).filter((x) => canTouch(x) && x.id !== session?.user.id)

  const run = async (label: string, list: any[], fn: (u: any) => Promise<any>) => {
    let ok = 0; const errs: string[] = []
    for (const u of list) { try { await fn(u); ok++ } catch (e: any) { errs.push(`${u.full_name}: ${e.message}`) } }
    if (ok) toast.success(`${label}: ${ok} user(s)`)
    if (errs.length) toast.error(`${errs.length} failed`, errs.slice(0, 3).join(' · '))
    setSel(new Set()); load()
  }
  const setStatus = (status: string, u?: any) => {
    const list = targets(u)
    if (!list.length) return toast.info(u ? 'This account cannot be changed here' : 'Select users first')
    const go = () => run(status === 'active' ? 'Activated' : 'Deactivated', list, (x) => api.post(`/api/users/${x.id}/status`, { status }))
    if (status === 'inactive') setConfirmDlg({ title: `Deactivate ${list.length} user(s)?`, body: 'They are signed out and cannot sign in. Transfer history is kept.', label: 'Deactivate', danger: true, run: go })
    else go()
  }
  const reset = (u?: any) => {
    const list = targets(u ?? (selected.length === 1 ? selected[0] : undefined))
    if (list.length !== 1) return toast.info('Select one user to reset the password')
    const x = list[0]
    setConfirmDlg({ title: `Reset password for ${x.full_name}?`, body: 'A temporary password is generated. The user must change it at next sign-in and is signed out now.', label: 'Reset password',
      run: async () => { try { const r = await api.post(`/api/users/${x.id}/reset-password`, {}); setTempPwd({ name: x.full_name, pwd: r.temporary_password }) } catch (e: any) { toast.error(e.message) } } })
  }
  const del = (u?: any) => {
    const list = targets(u)
    if (!list.length) return toast.info('Select users first')
    setConfirmDlg({ title: `Delete ${list.length} user(s)?`, body: 'Accounts are removed and login IDs freed. All transfer records and audit history are preserved with the users\' names.', label: 'Delete', danger: true,
      run: () => run('Deleted', list, (x) => api.del(`/api/users/${x.id}`)) })
  }
  const assignRole = (u?: any) => {
    const list = targets(u)
    if (!list.length) return toast.info('Select users first')
    setRoleDlg(list)
  }

  const s = data?.stats
  return (
    <div>
      <PageHeader title="User Management" subtitle="Create, Edit, Assign Role, Section, Device and Manage User Access" icon={UsersIcon} />
      {s && (
        <div className="mb-4 grid grid-cols-2 gap-3 md:grid-cols-3 xl:grid-cols-6">
          <StatCard label="Total Users" value={s.total} icon={UsersIcon} tone="blue" onClick={() => { setF({ ...f, status: '', role: '' }); setApplied({ ...applied, status: '', role: '' }) }} />
          <StatCard label="Active Users" value={s.active} icon={UserCheck} tone="green" onClick={() => { setF({ ...f, status: 'active' }); setApplied({ ...applied, status: 'active' }) }} />
          <StatCard label="Inactive Users" value={s.inactive} icon={UserX} tone="red" onClick={() => { setF({ ...f, status: 'inactive' }); setApplied({ ...applied, status: 'inactive' }) }} />
          <StatCard label="Administrators" value={s.admins} icon={Crown} tone="violet" />
          <StatCard label="Normal Users" value={s.normal} icon={UsersIcon} tone="orange" hint={s.readonly ? `+ ${s.readonly} read only` : undefined} />
          <StatCard label="Assigned PCs" value={s.assigned_pcs} icon={Monitor} tone="blue" />
        </div>
      )}

      <div className="mb-3 flex flex-wrap gap-2">
        <Button size="lg" icon={Plus} onClick={() => setEdit({})}>Add User</Button>
        <Button size="lg" variant="outline" icon={FileSpreadsheet} onClick={() => setImportOpen(true)}>Import Excel</Button>
        <Button size="lg" variant="outline" icon={Download} onClick={() => download('/api/users/export.xlsx')}>Export Excel</Button>
        <Button size="lg" variant="outline" icon={KeyRound} onClick={() => reset()}>Reset Password</Button>
        <Button size="lg" variant="outline" icon={UserCog} onClick={() => assignRole()}>Bulk Assign Role</Button>
        <Button size="lg" variant="outline" icon={CheckCircle2} onClick={() => setStatus('active')}>Activate</Button>
        <Button size="lg" variant="outline" icon={Ban} onClick={() => setStatus('inactive')}>Deactivate</Button>
        <Button size="lg" variant="ghost" icon={Trash2} onClick={() => del()} className="border border-red-200 bg-red-50 !text-red-600 hover:bg-red-100">Delete</Button>
        {sel.size > 0 && <span className="self-center text-sm font-semibold text-maroon-800">{sel.size} selected</span>}
      </div>

      <Card className="mb-4 flex flex-wrap items-center gap-2 p-3">
        <SearchInput value={f.q} onChange={(v) => setF({ ...f, q: v })} placeholder="Search by User Name, Login ID, Email or Mobile…" className="min-w-[260px] flex-1" />
        <span className="text-sm font-bold">Section :</span>
        <Select value={f.section} onChange={(e) => setF({ ...f, section: e.target.value })} className="w-44"><option value="">All Sections</option>{meta?.sections.map((r: any) => <option key={r.id} value={r.id}>{r.name}</option>)}</Select>
        <span className="text-sm font-bold">Role :</span>
        <Select value={f.role} onChange={(e) => setF({ ...f, role: e.target.value })} className="w-44"><option value="">All Roles</option>{meta?.roles.map((r: any) => <option key={r.code} value={r.code}>{r.name}</option>)}</Select>
        <span className="text-sm font-bold">Status :</span>
        <Select value={f.status} onChange={(e) => setF({ ...f, status: e.target.value })} className="w-36"><option value="">All</option><option value="active">Active</option><option value="inactive">Inactive</option></Select>
        <Button icon={Filter} onClick={() => setApplied(f)}>Filter</Button>
        <Button variant="outline" icon={RefreshCw} onClick={() => { const e = { q: '', role: '', section: '', status: '' }; setF(e); setApplied(e) }}>Reset</Button>
      </Card>

      <div className="grid gap-4 2xl:grid-cols-[1fr_400px]">
        <Card className="min-w-0 overflow-hidden">
          {err ? <ErrorBox error={err} onRetry={load} /> : !data ? <Loading /> : items.length === 0 ? <Empty icon={UsersIcon} title="No users found" /> : (<>
            <div className="overflow-x-auto">
              <table className="w-full border-collapse text-left text-[13.5px]">
                <thead><tr className="bg-ink-100/80">
                  <th className="w-10 px-3 py-2.5"><Checkbox checked={items.every((u) => sel.has(u.id))} onChange={(v) => setSel(v ? new Set(items.map((u) => u.id)) : new Set())} /></th>
                  {['S.No.', 'User Name', 'Login ID', 'Section / Office', 'Assigned PC (IP)', 'Role', 'Status', 'Last Login'].map((h) => <th key={h} className="whitespace-nowrap px-2.5 py-2.5 font-bold">{h}</th>)}
                  <th className="px-2.5 py-2.5 text-center font-bold">Actions</th>
                </tr></thead>
                <tbody>
                  {items.map((u, i) => (
                    <tr key={u.id} onClick={() => setActiveId(u.id)} className={cx('cursor-pointer border-b border-ink-100', active?.id === u.id ? 'bg-maroon-50' : 'hover:bg-ink-50')}>
                      <td className="px-3 py-2" onClick={(e) => e.stopPropagation()}><Checkbox checked={sel.has(u.id)} onChange={(v) => setSel((x) => { const n = new Set(x); v ? n.add(u.id) : n.delete(u.id); return n })} /></td>
                      <td className="px-2.5">{(data.page - 1) * data.page_size + i + 1}</td>
                      <td className="whitespace-nowrap px-2.5 font-bold">{u.full_name}{u.id === session?.user.id && <span className="ml-1 text-xs font-normal text-ink-500">(you)</span>}</td>
                      <td className="whitespace-nowrap px-2.5">{u.login_id}</td>
                      <td className="px-2.5">{u.section || '—'}</td>
                      <td className="whitespace-nowrap px-2.5">{u.assigned_pc ? `${u.assigned_pc}${deviceIp(u.assigned_device_id) ? ` (${deviceIp(u.assigned_device_id)})` : ''}` : '—'}</td>
                      <td className="px-2.5"><RolePill role={u.role} name={u.role_name} /></td>
                      <td className="px-2.5"><span className="flex items-center gap-1"><StatusBadge status={u.status} />{u.locked && <Lock className="h-4 w-4 text-red-600" aria-label="Locked" />}</span></td>
                      <td className="whitespace-nowrap px-2.5 leading-tight">{u.last_login_at ? <>{fmtDate(u.last_login_at)}<div>{fmtTime(u.last_login_at)}</div></> : 'Never'}</td>
                      <td className="whitespace-nowrap px-2 text-center" onClick={(e) => e.stopPropagation()}>
                        {canTouch(u) && <>
                          <IconButton icon={Edit3} label="Edit" onClick={() => setEdit(u)} />
                          <IconButton icon={KeyRound} label="Reset password" onClick={() => reset(u)} />
                          {u.id !== session?.user.id && <IconButton icon={UserCog} label="Assign role" onClick={() => assignRole(u)} />}
                          {u.id !== session?.user.id && <IconButton icon={Trash2} tone="danger" label="Delete" onClick={() => del(u)} />}
                        </>}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <Pagination page={data.page} pageSize={pageSize} total={data.total} onPage={setPage} onPageSize={setPageSize} label="users" />
          </>)}
        </Card>

        <div className="space-y-4">
          <Panel title="User Details" icon={UserIcon}>
            {!active ? <div className="py-8 text-center text-sm text-ink-500">Select a user.</div> : (
              <div className="flex gap-4">
                <span className="flex h-24 w-20 shrink-0 items-center justify-center rounded-xl border border-ink-200 bg-gradient-to-b from-ink-50 to-white"><UserIcon className="h-14 w-14 text-ink-800" strokeWidth={1.3} /></span>
                <div className="min-w-0 flex-1">
                  <div className="mb-1.5 flex items-center justify-between gap-2"><span className="truncate text-[18px] font-extrabold">{active.full_name}</span><StatusBadge status={active.status} /></div>
                  <KV rows={[['Login ID', active.login_id], ['Role', active.role_name], ['Section', active.section || '—'],
                    ['Assigned PC', active.assigned_pc ? `${active.assigned_pc}${deviceIp(active.assigned_device_id) ? ` (${deviceIp(active.assigned_device_id)})` : ''}` : '—'],
                    ['Mobile', active.mobile || '—'], ['Email', active.email || '—'], ['Last Login', fmtDateTime(active.last_login_at)],
                    ['Online', active.online ? 'Yes – signed in now' : 'No']]} />
                </div>
              </div>
            )}
          </Panel>
          {active && (
            <Panel title="Access Permissions" icon={ShieldCheck}>
              <div className="grid grid-cols-2 gap-x-3 gap-y-2 text-[14px]">
                {['send', 'devices', 'receive', 'users', 'files', 'settings', 'history', 'dashboard'].map((p) => {
                  const on = active.permissions.includes(p)
                  return <div key={p} className="flex items-center gap-2"><span className={cx('flex h-5 w-5 items-center justify-center rounded', on ? 'bg-emerald-600 text-white' : 'border border-ink-300 bg-white')}>{on && <CheckCircle2 className="h-4 w-4" />}</span>{PERM_LABEL[p]}</div>
                })}
              </div>
              {active.role === 'readonly' && <p className="mt-2 text-xs text-ink-500">Read Only users can view but never send, upload or modify data.</p>}
            </Panel>
          )}
          <Panel title="Quick Actions" icon={Shield}>
            <div className="grid grid-cols-3 gap-2">
              <ActionTile icon={KeyRound} label="Reset Password" tone="violet" disabled={!canTouch(active)} onClick={() => reset(active)} />
              <ActionTile icon={Edit3} label="Edit User" tone="blue" disabled={!canTouch(active)} onClick={() => setEdit(active)} />
              <ActionTile icon={UserCog} label="Assign Role" tone="amber" disabled={!canTouch(active) || active?.id === session?.user.id} onClick={() => assignRole(active)} />
              <ActionTile icon={Monitor} label="Assign PC" tone="green" disabled={!canTouch(active)} onClick={() => setEdit(active)} />
              {active?.status === 'inactive'
                ? <ActionTile icon={CheckCircle2} label="Activate" tone="green" disabled={!canTouch(active)} onClick={() => setStatus('active', active)} />
                : <ActionTile icon={Ban} label="Deactivate" tone="red" disabled={!canTouch(active) || active?.id === session?.user.id} onClick={() => setStatus('inactive', active)} />}
              <ActionTile icon={Trash2} label="Delete User" tone="red" disabled={!canTouch(active) || active?.id === session?.user.id} onClick={() => del(active)} />
            </div>
          </Panel>
        </div>
      </div>

      {edit && meta && <UserForm user={edit} meta={meta} onClose={() => setEdit(null)} onSaved={() => { setEdit(null); load() }} />}
      {importOpen && <ImportDialog onClose={() => setImportOpen(false)} onDone={load} />}
      {roleDlg && meta && <RoleDialog users={roleDlg} meta={meta} onClose={() => setRoleDlg(null)} onDone={() => { setRoleDlg(null); setSel(new Set()); load() }} />}
      <Modal open={!!confirmDlg} onClose={() => setConfirmDlg(null)} size="sm" title={confirmDlg?.title} icon={confirmDlg?.danger ? Trash2 : KeyRound}
        footer={<><Button variant="outline" onClick={() => setConfirmDlg(null)}>Cancel</Button><Button variant={confirmDlg?.danger ? 'danger' : 'primary'} onClick={async () => { const c = confirmDlg!; setConfirmDlg(null); await c.run() }}>{confirmDlg?.label}</Button></>}>
        <p className="text-sm text-ink-700">{confirmDlg?.body}</p>
      </Modal>
      <Modal open={!!tempPwd} onClose={() => setTempPwd(null)} size="sm" title="Temporary password" icon={KeyRound}
        footer={<Button onClick={() => { copyText(tempPwd!.pwd); toast.success('Copied') }}>Copy password</Button>}>
        <p className="text-sm text-ink-700">Give this password to <b>{tempPwd?.name}</b> in person. It will not be shown again.</p>
        <div className="mt-3 rounded-lg bg-ink-900 px-4 py-3 text-center font-mono text-lg tracking-wider text-white">{tempPwd?.pwd}</div>
      </Modal>
    </div>
  )
}

function RoleDialog({ users, meta, onClose, onDone }: { users: any[]; meta: any; onClose: () => void; onDone: () => void }) {
  const { isSuper } = useAuth()
  const toast = useToast()
  const [role, setRole] = useState('user')
  const [busy, setBusy] = useState(false)
  const go = async () => {
    setBusy(true)
    let ok = 0; const errs: string[] = []
    for (const u of users) {
      try {
        await api.put(`/api/users/${u.id}`, { full_name: u.full_name, login_id: u.login_id, section_id: u.section_id, assigned_device_id: u.assigned_device_id,
          mobile: u.mobile, email: u.email, role, status: u.status, permission_overrides: {} })
        ok++
      } catch (e: any) { errs.push(`${u.full_name}: ${e.message}`) }
    }
    setBusy(false)
    if (ok) toast.success(`Role updated for ${ok} user(s)`)
    if (errs.length) toast.error(`${errs.length} failed`, errs.slice(0, 3).join(' · '))
    onDone()
  }
  return (
    <Modal open onClose={onClose} size="sm" title={`Assign role to ${users.length} user(s)`} icon={UserCog}
      footer={<><Button variant="outline" onClick={onClose}>Cancel</Button><Button loading={busy} onClick={go}>Assign role</Button></>}>
      <Field label="Role"><Select value={role} onChange={(e) => setRole(e.target.value)}>{meta.roles.filter((r: any) => r.code !== 'super_admin' || isSuper).map((r: any) => <option key={r.code} value={r.code}>{r.name}</option>)}</Select></Field>
      <p className="mt-2 text-xs text-ink-500">Page permissions are reset to the role's defaults. {users.slice(0, 6).map((u) => u.full_name).join(', ')}{users.length > 6 ? '…' : ''}</p>
    </Modal>
  )
}

function UserForm({ user, meta, onClose, onSaved }: { user: any; meta: any; onClose: () => void; onSaved: () => void }) {
  const { isSuper, session } = useAuth()
  const toast = useToast()
  const isNew = !user.id
  const [f, setF] = useState({
    full_name: user.full_name || '', login_id: user.login_id || '', password: '', section_id: user.section_id || '',
    assigned_device_id: user.assigned_device_id || '', mobile: user.mobile || '', email: user.email || '', role: user.role || 'user', status: user.status || 'active',
  })
  const roleDef = meta.roles.find((r: any) => r.code === f.role)
  const initialPerms = () => {
    const base = new Set<string>(user.permissions || roleDef?.permissions || [])
    return base
  }
  const [perms, setPerms] = useState<Set<string>>(initialPerms)
  useEffect(() => { if (isNew || f.role !== user.role) setPerms(new Set(roleDef?.permissions || [])) }, [f.role])
  const [err, setErr] = useState('')
  const [busy, setBusy] = useState(false)
  const self = user.id === session?.user.id

  const save = async () => {
    setBusy(true); setErr('')
    const overrides: Record<string, boolean> = {}
    meta.permissions.forEach((p: any) => { overrides[p.code] = perms.has(p.code) })
    const body = { ...f, password: f.password || null, section_id: f.section_id ? Number(f.section_id) : null, assigned_device_id: f.assigned_device_id ? Number(f.assigned_device_id) : null, permission_overrides: overrides }
    try {
      isNew ? await api.post('/api/users', body) : await api.put(`/api/users/${user.id}`, body)
      toast.success(isNew ? 'User created' : 'User updated', isNew ? 'They must change the password at first sign-in.' : undefined)
      onSaved()
    } catch (e: any) { setErr(e.message) } finally { setBusy(false) }
  }
  const pp = meta.password_policy
  return (
    <Modal open onClose={onClose} size="lg" icon={isNew ? UserPlus : Edit3} title={isNew ? 'Add User' : `Edit ${user.full_name}`}
      footer={<><Button variant="outline" onClick={onClose}>Cancel</Button><Button loading={busy} onClick={save}>{isNew ? 'Create user' : 'Save changes'}</Button></>}>
      <div className="grid gap-3 sm:grid-cols-2">
        <Field label="Full name" required><Input value={f.full_name} onChange={(e) => setF({ ...f, full_name: e.target.value })} /></Field>
        <Field label="Login ID" required hint="Letters, digits, dot, dash, underscore"><Input value={f.login_id} onChange={(e) => setF({ ...f, login_id: e.target.value })} autoComplete="off" /></Field>
        <Field label={isNew ? 'Password' : 'New password (optional)'} required={isNew} hint={`Min ${pp.min_length} chars${pp.require_upper ? ', uppercase' : ''}${pp.require_lower ? ', lowercase' : ''}${pp.require_digit ? ', digit' : ''}${pp.require_symbol ? ', symbol' : ''}. Must be changed at first sign-in.`}>
          <Input type="password" value={f.password} onChange={(e) => setF({ ...f, password: e.target.value })} autoComplete="new-password" />
        </Field>
        <Field label="Section"><Select value={f.section_id} onChange={(e) => setF({ ...f, section_id: e.target.value })}><option value="">—</option>{meta.sections.map((s: any) => <option key={s.id} value={s.id}>{s.name}</option>)}</Select></Field>
        <Field label="Assigned PC"><Select value={f.assigned_device_id} onChange={(e) => setF({ ...f, assigned_device_id: e.target.value })}><option value="">—</option>{meta.devices.map((d: any) => <option key={d.id} value={d.id}>{d.pc_name} ({d.ip_address || 'no IP'})</option>)}</Select></Field>
        <Field label="Mobile number"><Input value={f.mobile} onChange={(e) => setF({ ...f, mobile: e.target.value })} /></Field>
        <Field label="Email"><Input type="email" value={f.email} onChange={(e) => setF({ ...f, email: e.target.value })} /></Field>
        <Field label="Role"><Select value={f.role} disabled={self} onChange={(e) => setF({ ...f, role: e.target.value })}>{meta.roles.filter((r: any) => r.code !== 'super_admin' || isSuper).map((r: any) => <option key={r.code} value={r.code}>{r.name}</option>)}</Select></Field>
        <Field label="Status"><Select value={f.status} disabled={self} onChange={(e) => setF({ ...f, status: e.target.value })}><option value="active">Active</option><option value="inactive">Inactive</option></Select></Field>
      </div>
      <div className="mt-5">
        <div className="mb-2 flex items-center gap-2 text-sm font-semibold"><Shield className="h-4 w-4 text-maroon-700" />Page permissions <span className="text-xs font-normal text-ink-500">— defaults from the {roleDef?.name} role; adjust per user</span></div>
        <div className="grid grid-cols-2 gap-2 rounded-xl bg-ink-50 p-3 sm:grid-cols-4">
          {meta.permissions.map((p: any) => (
            <Checkbox key={p.code} checked={f.role === 'super_admin' || perms.has(p.code)} disabled={f.role === 'super_admin'} label={p.name}
              onChange={(v) => setPerms((s) => { const n = new Set(s); v ? n.add(p.code) : n.delete(p.code); return n })} />
          ))}
        </div>
        {f.role === 'readonly' && <p className="mt-2 text-xs text-ink-500">Read Only users can never send, upload or modify data, even with extra pages enabled.</p>}
      </div>
      {err && <div className="mt-3 rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700">{err}</div>}
    </Modal>
  )
}

function ImportDialog({ onClose, onDone }: { onClose: () => void; onDone: () => void }) {
  const input = useRef<HTMLInputElement>(null)
  const [res, setRes] = useState<any>(null)
  const [busy, setBusy] = useState(false)
  const toast = useToast()
  const go = async (file: File) => {
    setBusy(true)
    try { const r = await uploadFile('/api/users/import', file).promise; setRes(r); onDone() } catch (e: any) { toast.error('Import failed', e.message) } finally { setBusy(false) }
  }
  return (
    <Modal open onClose={onClose} title="Import users from Excel" icon={FileUp}
      footer={<><Button variant="outline" icon={FileDown} onClick={() => download('/api/users/import-template.xlsx')}>Download template</Button><Button icon={Plus} loading={busy} onClick={() => input.current?.click()}>Choose .xlsx file</Button></>}>
      <p className="text-sm text-ink-700">Columns: <b>Full Name, Login ID, Password, Section, Assigned PC, Mobile, Email, Role, Status</b>. Rows with an existing login ID are skipped. Blank passwords get a random one (reset it afterwards to see it).</p>
      <input ref={input} type="file" accept=".xlsx" hidden onChange={(e) => e.target.files?.[0] && go(e.target.files[0])} />
      {res && (
        <div className="mt-4 rounded-xl bg-ink-50 p-3 text-sm">
          <div className="font-semibold text-emerald-700">{res.created} user(s) created</div>
          {res.errors.length > 0 && <ul className="mt-2 max-h-48 list-disc overflow-y-auto pl-5 text-red-700">{res.errors.map((e: string, i: number) => <li key={i}>{e}</li>)}</ul>}
        </div>
      )}
    </Modal>
  )
}
