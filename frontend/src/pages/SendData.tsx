import { useEffect, useMemo, useRef, useState } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'
import {
  AlertCircle, CheckCircle2, ChevronRight, Clock, CloudUpload, Eye, FileText, Files, Forward, Inbox, Layers, Maximize2,
  Minimize2, Paperclip, RefreshCw, Reply, Save, Send, Settings2, Trash2, Users, X, MailCheck, CalendarClock,
} from 'lucide-react'
import { api, ApiError, uploadFile } from '../lib/api'
import { useAuth } from '../lib/auth'
import { useRealtimeEvent } from '../lib/realtime'
import { useToast } from '../lib/toast'
import { fmtDateTime, fmtSize, timeAgo } from '../lib/format'
import RichEditor, { RichEditorHandle } from '../components/RichEditor'
import {
  Badge, Button, Card, Checkbox, cx, Empty, FileIcon, IconButton, Input, Modal, PageHeader, Panel, Progress, SearchInput,
  Select, StatusBadge,
} from '../components/ui'

interface Recipient { id: number; full_name: string; login_id: string; section: string; section_id: number | null; pc_name: string; ip_address: string; connection_type: string; user_online: boolean; pc_online: boolean; is_self: boolean }
interface Att { key: string; uid?: string; name: string; size: number; extension: string; progress: number; status: 'uploading' | 'done' | 'error'; error?: string; file?: File; abort?: () => void; forwarded?: boolean }
type Mode = 'text' | 'file' | 'both'
const MAX_CHARS = 10000

export default function SendData() {
  const { session } = useAuth()
  const b = session!.branding
  const toast = useToast()
  const nav = useNavigate()
  const loc = useLocation() as any
  const editor = useRef<RichEditorHandle>(null)
  const fileInput = useRef<HTMLInputElement>(null)

  const [mode, setMode] = useState<Mode>('both')
  const [subject, setSubject] = useState('')
  const [html, setHtml] = useState('')
  const [full, setFull] = useState(false)
  const [atts, setAtts] = useState<Att[]>([])
  const [recips, setRecips] = useState<Recipient[]>([])
  const [selected, setSelected] = useState<Set<number>>(new Set())
  const [pickMode, setPickMode] = useState<'user' | 'section'>('user')
  const [q, setQ] = useState('')
  const [section, setSection] = useState('')
  const [priority, setPriority] = useState('normal')
  const [notify, setNotify] = useState(true)
  const [confirmDelivery, setConfirmDelivery] = useState(b.delivery_confirmation_default)
  const [readReceipt, setReadReceipt] = useState(b.read_receipt_default)
  const [validity, setValidity] = useState(false)
  const [validDays, setValidDays] = useState(7)
  const [draftId, setDraftId] = useState<number | null>(null)
  const [drafts, setDrafts] = useState<any[]>([])
  const [draftsOpen, setDraftsOpen] = useState(false)
  const [sending, setSending] = useState(false)
  const [result, setResult] = useState<any>(null)
  const [drag, setDrag] = useState(false)
  const [context, setContext] = useState<{ kind: 'reply' | 'forward'; transferId: number; label: string } | null>(null)

  const loadRecips = () => api.get<Recipient[]>('/api/transfers/recipients').then(setRecips).catch((e) => toast.error('Could not load receivers', e.message))
  const loadDrafts = () => api.get('/api/drafts').then(setDrafts).catch(() => {})
  useEffect(() => { loadRecips(); loadDrafts() }, [])
  useRealtimeEvent((m) => { if (m.type === 'presence' || m.type === 'devices.changed') loadRecips() }, [])

  useEffect(() => {
    const st = loc.state
    if (!st) return
    if (st.reply) {
      setSubject(st.reply.subject.startsWith('Re:') ? st.reply.subject : `Re: ${st.reply.subject}`)
      if (st.reply.sender_user_id) setSelected(new Set([st.reply.sender_user_id]))
      setHtml(`<br><br><div>— On ${fmtDateTime(st.reply.created_at)}, ${st.reply.sender_name} wrote:</div><div>${st.reply.body_html || ''}</div>`)
      setContext({ kind: 'reply', transferId: st.reply.transfer_id, label: `Replying to ${st.reply.sender_name} (${st.reply.transfer_uid})` })
    }
    if (st.forward) {
      setSubject(st.forward.subject.startsWith('Fwd:') ? st.forward.subject : `Fwd: ${st.forward.subject}`)
      setHtml(`<div>— Forwarded message from ${st.forward.sender_name} (${st.forward.transfer_uid}) —</div><div>${st.forward.body_html || ''}</div>`)
      setAtts(st.forward.attachments.map((a: any) => ({ key: a.uid, uid: a.uid, name: a.name, size: a.size, extension: a.extension, progress: 100, status: 'done', forwarded: true })))
      setContext({ kind: 'forward', transferId: st.forward.transfer_id, label: `Forwarding ${st.forward.transfer_uid}` })
    }
    if (st.to) setSelected(new Set(st.to))
    nav('.', { replace: true, state: null })
  }, [])

  useRealtimeEvent((m) => {
    if (m.type === 'transfer.status' && result && m.transfer_id === result.transfer.id) {
      setResult((r: any) => r && ({ ...r, aggregate: m.aggregate, recipients: r.recipients.map((x: any) => x.id === m.recipient.id ? m.recipient : x) }))
    }
  }, [result?.transfer.id])

  // ------------------------------------------------------------- receivers
  const bySection = useMemo(() => {
    const m = new Map<string, Recipient[]>()
    recips.forEach((r) => m.set(r.section, [...(m.get(r.section) || []), r]))
    return Array.from(m.entries()).sort((a, b) => a[0].localeCompare(b[0]))
  }, [recips])
  const filtered = recips.filter((r) => {
    const t = q.trim().toLowerCase()
    if (t && ![r.full_name, r.login_id, r.pc_name, r.ip_address, r.section].some((v) => v?.toLowerCase().includes(t))) return false
    return !section || r.section === section
  })
  const toggle = (id: number) => setSelected((s) => { const n = new Set(s); n.has(id) ? n.delete(id) : n.add(id); return n })
  const setMany = (ids: number[], on: boolean) => setSelected((s) => { const n = new Set(s); ids.forEach((i) => on ? n.add(i) : n.delete(i)); return n })
  const allIds = recips.map((r) => r.id)
  const triState = (ids: number[]) => ({ checked: ids.length > 0 && ids.every((i) => selected.has(i)), indeterminate: ids.some((i) => selected.has(i)) && !ids.every((i) => selected.has(i)) })

  // ------------------------------------------------------------- uploads
  const addFiles = (files: FileList | File[]) => {
    const list = Array.from(files)
    const allowed = b.allowed_extensions.map((e) => e.toLowerCase())
    const max = b.max_file_size_mb * 1024 * 1024
    let count = atts.length
    for (const f of list) {
      const ext = (f.name.split('.').pop() || '').toLowerCase()
      if (count >= b.max_files_per_transfer) { toast.warning(`Maximum ${b.max_files_per_transfer} files per transfer`); break }
      if (b.file_whitelist_enforced && !allowed.includes(ext)) { toast.error(`${f.name} not allowed`, `Permitted: ${allowed.join(', ')}`); continue }
      if (f.size > max) { toast.error(`${f.name} is too large`, `Maximum ${b.max_file_size_mb} MB`); continue }
      count++
      startUpload({ key: `${Date.now()}-${Math.random()}`, name: f.name, size: f.size, extension: ext, progress: 0, status: 'uploading', file: f })
    }
    if (mode === 'text') setMode('both')
  }
  const startUpload = (a: Att) => {
    const up = uploadFile('/api/transfers/uploads', a.file!, {}, (p) => setAtts((xs) => xs.map((x) => x.key === a.key ? { ...x, progress: p } : x)))
    setAtts((xs) => [...xs.filter((x) => x.key !== a.key), { ...a, status: 'uploading', progress: 0, error: undefined, abort: up.abort }])
    up.promise.then((res) => setAtts((xs) => xs.map((x) => x.key === a.key ? { ...x, uid: res.uid, status: 'done', progress: 100 } : x)))
      .catch((e: ApiError) => { if (e.status !== -1) setAtts((xs) => xs.map((x) => x.key === a.key ? { ...x, status: 'error', error: e.message } : x)) })
  }
  const removeAtt = (a: Att) => {
    a.abort?.()
    setAtts((xs) => xs.filter((x) => x.key !== a.key))
    if (a.uid && !a.forwarded) api.del(`/api/transfers/uploads/${a.uid}`).catch(() => {})
  }
  const viewAtt = (a: Att) => {
    if (a.file) { const u = URL.createObjectURL(a.file); window.open(u, '_blank', 'noopener'); setTimeout(() => URL.revokeObjectURL(u), 60000) }
    else if (a.uid) window.open(`/api/attachments/${a.uid}?inline=1`, '_blank', 'noopener')
  }

  // ------------------------------------------------------------- send / drafts
  const plainText = () => { const d = document.createElement('div'); d.innerHTML = html; return (d.textContent || '').trim() }
  const chars = plainText().length
  const uploading = atts.some((a) => a.status === 'uploading')
  const reset = () => {
    setSubject(''); editor.current?.clear(); setHtml(''); setAtts([]); setSelected(new Set()); setDraftId(null)
    setValidity(false); setPriority('normal'); setContext(null)
  }
  const send = async () => {
    if (!selected.size) return toast.warning('Select at least one receiver')
    const text = mode === 'file' ? '' : plainText()
    const files = mode === 'text' ? [] : atts.filter((a) => a.status === 'done')
    if (!text && !files.length) return toast.warning(mode === 'file' ? 'Attach at least one file' : 'Type a message or attach a file')
    if (chars > MAX_CHARS) return toast.warning(`Message is longer than ${MAX_CHARS.toLocaleString()} characters`)
    if (atts.some((a) => a.status === 'error')) return toast.warning('Remove or retry the failed uploads first')
    setSending(true)
    try {
      const res = await api.post('/api/transfers', {
        subject, body_html: mode === 'file' ? '' : html, recipient_user_ids: Array.from(selected),
        attachment_uids: files.filter((a) => !a.forwarded).map((a) => a.uid),
        forward_attachment_uids: files.filter((a) => a.forwarded).map((a) => a.uid),
        reply_to_transfer_id: context?.kind === 'reply' ? context.transferId : null,
        forwarded_from_transfer_id: context?.kind === 'forward' ? context.transferId : null,
        priority, notify, delivery_confirmation: confirmDelivery, read_receipt: readReceipt,
        expires_at: validity ? new Date(Date.now() + validDays * 86400000).toISOString() : null, draft_id: draftId,
      })
      setResult(res)
      toast.success(`Transfer ${res.transfer.transfer_uid} queued`, `${res.recipients.length} receiver(s). Delivery is confirmed only when each PC acknowledges.`)
      reset(); loadDrafts()
    } catch (e: any) { toast.error('Send failed', e.message) } finally { setSending(false) }
  }
  const saveDraft = async () => {
    const body = { subject, body_html: html, recipient_user_ids: Array.from(selected), attachment_uids: atts.filter((a) => a.uid && !a.forwarded).map((a) => a.uid),
      options: { priority, notify, confirmDelivery, readReceipt, validity, validDays, mode } }
    try {
      const d = draftId ? await api.put(`/api/drafts/${draftId}`, body) : await api.post('/api/drafts', body)
      setDraftId(d.id); toast.success('Draft saved'); loadDrafts()
    } catch (e: any) { toast.error('Could not save draft', e.message) }
  }
  const openDraft = (d: any) => {
    setDraftId(d.id); setSubject(d.subject); setHtml(d.body_html); setSelected(new Set(d.recipient_user_ids))
    setAtts(d.attachments.map((a: any) => ({ key: a.uid, uid: a.uid, name: a.name, size: a.size, extension: a.extension, progress: 100, status: 'done' })))
    const o = d.options || {}
    if (o.priority) setPriority(o.priority)
    if (o.mode) setMode(o.mode)
    setNotify(o.notify ?? true); setConfirmDelivery(o.confirmDelivery ?? true); setReadReceipt(o.readReceipt ?? false)
    setValidity(!!o.validity); setValidDays(o.validDays || 7)
    setDraftsOpen(false)
  }

  const totalSize = atts.reduce((n, a) => n + a.size, 0)
  const selectedList = recips.filter((r) => selected.has(r.id))
  const MODES: { v: Mode; label: string; icon: any }[] = [{ v: 'text', label: 'Text / Message', icon: FileText }, { v: 'file', label: 'File / Document', icon: Files }, { v: 'both', label: 'Text + File (Both)', icon: Layers }]

  return (
    <div>
      <PageHeader title="Send Data" subtitle="Send Text / Message and Files to One or Multiple Users" icon={Send} />
      {context && (
        <div className="mb-3 flex items-center justify-between rounded-xl border border-maroon-200 bg-maroon-50 px-4 py-2 text-sm text-maroon-800">
          <span className="flex items-center gap-2">{context.kind === 'reply' ? <Reply className="h-4 w-4" /> : <Forward className="h-4 w-4" />}{context.label}</span>
          <IconButton icon={X} label="Cancel" onClick={() => setContext(null)} />
        </div>
      )}
      {result && <DeliveryPanel result={result} onClose={() => setResult(null)} onHistory={() => nav(`/history?transfer=${result.transfer.transfer_uid}`)} />}

      <div className="grid gap-4 xl:grid-cols-[1.08fr_1fr]">
        {/* ------------------------------------------------ compose */}
        <Card className={cx('space-y-4 p-4', full && 'fixed inset-4 z-50 overflow-y-auto shadow-pop')}>
          <div className="grid grid-cols-3 gap-2">
            {MODES.map((m) => (
              <button key={m.v} onClick={() => setMode(m.v)} className={cx('flex items-center justify-center gap-2 rounded-xl border px-3 py-2.5 text-[15.5px] font-semibold transition',
                mode === m.v ? 'border-maroon-700 bg-maroon-700 text-white shadow-md' : 'border-ink-200 bg-ink-50 text-ink-900 hover:bg-white')}>
                <m.icon className="h-5 w-5" />{m.label}
              </button>
            ))}
          </div>
          <Input value={subject} onChange={(e) => setSubject(e.target.value)} placeholder="Subject (e.g. Meeting on 25 Nov 2026)" maxLength={255} className="!py-2.5 text-[15px] font-semibold" aria-label="Subject" />
          {mode !== 'file' && (
            <RichEditor ref={editor} value={html} onChange={setHtml} placeholder="Type or paste your message here…"
              label={<span className="flex items-center gap-2 text-[17px] font-bold"><FileText className="h-5 w-5 text-maroon-700" />Message <span className="text-[14px] font-normal text-ink-600">(Paste or type your text here)</span></span>}
              toolbarExtra={<button type="button" title={full ? 'Exit full screen' : 'Full screen'} onClick={() => setFull((f) => !f)} className="rounded-md p-1.5 text-ink-800 hover:bg-maroon-50">{full ? <Minimize2 className="h-[18px] w-[18px]" /> : <Maximize2 className="h-[18px] w-[18px]" />}</button>}
              footer={<span className={chars > MAX_CHARS ? 'font-bold text-red-600' : ''}>{chars.toLocaleString()} / {MAX_CHARS.toLocaleString()}</span>}
              editorClassName={full ? 'min-h-[55vh] max-h-[70vh]' : undefined} />
          )}
          {mode !== 'text' && (
            <div>
              <div className="mb-2 flex items-center gap-2 text-[17px] font-bold"><Paperclip className="h-5 w-5 text-maroon-700" />Attach Files {mode === 'both' && <span className="font-normal text-ink-600">(Optional)</span>}</div>
              <div onDragOver={(e) => { e.preventDefault(); setDrag(true) }} onDragLeave={() => setDrag(false)} onDrop={(e) => { e.preventDefault(); setDrag(false); addFiles(e.dataTransfer.files) }}
                className={cx('rounded-xl border-2 border-dashed px-4 py-4 text-center transition', drag ? 'border-maroon-500 bg-maroon-50' : 'border-ink-300 bg-white')}>
                <div className="flex flex-wrap items-center justify-center gap-3 text-[15px]">
                  <CloudUpload className="h-8 w-8 text-maroon-700" /> Drag &amp; Drop files here or
                  <Button onClick={() => fileInput.current?.click()}>Click to Browse</Button>
                </div>
                <div className="mt-1.5 text-xs text-ink-600">Supported: {b.allowed_extensions.map((e) => e.toUpperCase()).join(', ')} &nbsp;|&nbsp; Max file size: {b.max_file_size_mb} MB per file · up to {b.max_files_per_transfer} files</div>
                <input ref={fileInput} type="file" multiple hidden accept={b.file_whitelist_enforced ? b.allowed_extensions.map((e) => '.' + e).join(',') : undefined}
                  onChange={(e) => { if (e.target.files) addFiles(e.target.files); e.target.value = '' }} />
              </div>
              {atts.length > 0 && (
                <table className="mt-3 w-full text-left text-[14px]">
                  <thead><tr className="bg-ink-100/80">{['S.No.', 'File Name', 'Size', 'Action'].map((h, i) => <th key={h} className={cx('px-3 py-2 font-bold', i === 3 && 'text-center')}>{h}</th>)}</tr></thead>
                  <tbody>
                    {atts.map((a, i) => (
                      <tr key={a.key} className="border-b border-ink-100">
                        <td className="px-3 py-2">{i + 1}</td>
                        <td className="px-3"><div className="flex items-center gap-2"><FileIcon ext={a.extension} className="h-7 w-7" /><span className="truncate font-medium">{a.name}</span>{a.forwarded && <Badge tone="maroon">forwarded</Badge>}</div>
                          {a.status === 'uploading' && <Progress value={a.progress} className="mt-1 h-1.5" />}
                          {a.status === 'error' && <div className="text-xs text-red-600">{a.error}</div>}</td>
                        <td className="whitespace-nowrap px-3">{fmtSize(a.size)}{a.status === 'uploading' && <span className="text-xs text-ink-500"> · {a.progress}%</span>}{a.status === 'done' && <CheckCircle2 className="ml-1 inline h-4 w-4 text-emerald-600" aria-label="ready" />}</td>
                        <td className="whitespace-nowrap px-3 text-center">
                          {a.status === 'error' && a.file ? <IconButton icon={RefreshCw} label="Retry upload" onClick={() => startUpload(a)} /> : <IconButton icon={Eye} label="View" onClick={() => viewAtt(a)} />}
                          <IconButton icon={Trash2} tone="danger" label="Remove attachment" onClick={() => removeAtt(a)} />
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </div>
          )}
          {full && <div className="flex justify-end"><Button variant="outline" icon={Minimize2} onClick={() => setFull(false)}>Exit full screen</Button></div>}
        </Card>

        {/* ------------------------------------------------ receivers + options */}
        <div className="space-y-4">
          <Card className="p-4">
            <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
              <h3 className="flex items-center gap-2 text-[19px] font-bold"><Users className="h-6 w-6 text-maroon-700" />Select Receiver(s)</h3>
              <div className="flex gap-4 text-[15px] font-medium">
                {([['user', 'User / PC'], ['section', 'Section / Group']] as const).map(([v, l]) => (
                  <label key={v} className="flex cursor-pointer items-center gap-2"><input type="radio" className="h-4 w-4 accent-maroon-700" checked={pickMode === v} onChange={() => setPickMode(v)} />{l}</label>
                ))}
              </div>
            </div>
            <SearchInput value={q} onChange={setQ} placeholder="Search by Name, PC Name, Section or IP…" />
            <div className="mt-3 grid gap-3 md:grid-cols-[210px_1fr]">
              <div className="max-h-[260px] overflow-y-auto rounded-xl border border-ink-200 p-1.5">
                <div className={cx('flex items-center gap-2 rounded-lg px-2 py-1.5', !section && 'bg-maroon-50')}>
                  <Checkbox {...triState(allIds)} onChange={(v) => setMany(allIds, v)} />
                  <button className="flex-1 text-left text-[14.5px] font-bold" onClick={() => setSection('')}>All Users ({recips.length})</button>
                </div>
                {bySection.map(([sec, list]) => {
                  const ids = list.map((r) => r.id)
                  return (
                    <div key={sec} className={cx('flex items-center gap-1.5 rounded-lg px-2 py-1.5', section === sec && 'bg-maroon-50')}>
                      <ChevronRight className="h-3.5 w-3.5 text-ink-400" />
                      <Checkbox {...triState(ids)} onChange={(v) => setMany(ids, v)} />
                      <button className="flex-1 truncate text-left text-[14px]" onClick={() => setSection(section === sec ? '' : sec)}>{sec} ({list.length})</button>
                    </div>
                  )
                })}
              </div>
              {pickMode === 'user' ? (
                <div className="max-h-[260px] overflow-y-auto rounded-xl border border-ink-200">
                  <table className="w-full text-left text-[13.5px]">
                    <thead className="sticky top-0 bg-ink-100"><tr>
                      <th className="w-9 px-2 py-2"><Checkbox {...triState(filtered.map((r) => r.id))} onChange={(v) => setMany(filtered.map((r) => r.id), v)} /></th>
                      {['S.No.', 'User / PC Name', 'IP Address', 'Status'].map((h) => <th key={h} className="px-2 py-2 font-bold">{h}</th>)}
                    </tr></thead>
                    <tbody>
                      {filtered.length === 0 && <tr><td colSpan={5} className="py-8 text-center text-ink-500">No receivers match</td></tr>}
                      {filtered.map((r, i) => {
                        const on = r.user_online || r.pc_online
                        return (
                          <tr key={r.id} onClick={() => toggle(r.id)} className={cx('cursor-pointer border-b border-ink-100', selected.has(r.id) ? 'bg-maroon-50' : 'hover:bg-ink-50')}>
                            <td className="px-2 py-1.5"><Checkbox checked={selected.has(r.id)} onChange={() => toggle(r.id)} /></td>
                            <td className="px-2">{i + 1}</td>
                            <td className="px-2 leading-tight"><b>{r.pc_name || '—'}</b>{r.is_self && <Badge className="ml-1">you</Badge>}<div className="text-xs text-ink-600">{r.full_name}</div></td>
                            <td className="whitespace-nowrap px-2">{r.ip_address || '—'}</td>
                            <td className="whitespace-nowrap px-2"><span className={cx('inline-flex items-center gap-1.5 font-semibold', on ? 'text-emerald-600' : 'text-ink-500')} title={r.user_online ? 'Signed in' : r.pc_online ? 'PC on (agent)' : 'Will be queued'}>
                              <span className={cx('h-2.5 w-2.5 rounded-full', on ? 'bg-emerald-500' : 'bg-ink-300')} />{on ? 'Online' : 'Offline'}</span></td>
                          </tr>
                        )
                      })}
                    </tbody>
                  </table>
                </div>
              ) : (
                <div className="grid max-h-[260px] content-start gap-2 overflow-y-auto sm:grid-cols-2">
                  {bySection.map(([sec, list]) => {
                    const ids = list.map((r) => r.id)
                    const t = triState(ids)
                    const online = list.filter((r) => r.user_online || r.pc_online).length
                    return (
                      <button key={sec} onClick={() => setMany(ids, !t.checked)} className={cx('rounded-xl border p-3 text-left transition', t.checked ? 'border-maroon-600 bg-maroon-50' : 'border-ink-200 hover:border-maroon-300')}>
                        <div className="flex items-center gap-2 font-bold"><Checkbox {...t} onChange={(v) => setMany(ids, v)} />{sec}</div>
                        <div className="mt-1 text-xs text-ink-600">{list.length} user(s) · {online} online</div>
                      </button>
                    )
                  })}
                </div>
              )}
            </div>
          </Card>

          <Card className="p-4">
            <div className="mb-2 flex items-center justify-between">
              <h3 className="flex items-center gap-2 text-[18px] font-bold"><Users className="h-5 w-5 text-maroon-700" />Selected Receivers ({selected.size})</h3>
              {selected.size > 0 && <button onClick={() => setSelected(new Set())} className="flex items-center gap-1 text-sm font-semibold text-red-600 hover:underline"><Trash2 className="h-4 w-4" />Clear All</button>}
            </div>
            {selectedList.length === 0 ? <div className="text-sm text-ink-500">No receivers selected. Offline receivers are queued and get the transfer when they next connect.</div> : (
              <div className="flex max-h-28 flex-wrap gap-2 overflow-y-auto">
                {selectedList.map((r) => (
                  <span key={r.id} className="inline-flex items-center gap-1.5 rounded-lg border border-ink-200 bg-ink-50 py-1 pl-3 pr-1.5 text-[13.5px] font-semibold" title={r.full_name}>
                    {r.pc_name || r.full_name}<button onClick={() => toggle(r.id)} className="rounded p-0.5 hover:bg-ink-200" aria-label={`Remove ${r.full_name}`}><X className="h-3.5 w-3.5" /></button>
                  </span>
                ))}
              </div>
            )}
          </Card>

          <Card className="p-4">
            <h3 className="mb-3 flex items-center gap-2 text-[18px] font-bold"><Settings2 className="h-5 w-5 text-maroon-700" />Send Options</h3>
            <div className="grid gap-4 md:grid-cols-[1.3fr_1fr]">
              <div className="space-y-2.5 text-[14.5px]">
                <Checkbox checked={notify} onChange={setNotify} label="Send notification to receiver" />
                <Checkbox checked={confirmDelivery} onChange={setConfirmDelivery} label="Delivery confirmation" />
                <Checkbox checked={readReceipt} onChange={setReadReceipt} label="Request acknowledgment (Read Receipt)" />
                <div className="flex flex-wrap items-center gap-2">
                  <Checkbox checked={validity} onChange={setValidity} label="Set validity / expire after" />
                  <Select value={validDays} disabled={!validity} onChange={(e) => setValidDays(Number(e.target.value))} className="w-28 !py-1.5">{[1, 3, 7, 15, 30].map((n) => <option key={n} value={n}>{n} Day{n > 1 ? 's' : ''}</option>)}</Select>
                </div>
              </div>
              <div className="space-y-3 border-ink-200 md:border-l md:pl-4">
                <label className="flex items-center justify-between gap-3 text-[14.5px] font-medium"><span className="flex items-center gap-2"><CalendarClock className="h-5 w-5 text-maroon-700" />Priority</span>
                  <Select value={priority} onChange={(e) => setPriority(e.target.value)} className={cx('w-36 font-semibold', priority === 'urgent' ? '!bg-red-50 text-red-700' : priority === 'high' ? '!bg-amber-50 text-amber-800' : '!bg-emerald-50 text-emerald-800')}>
                    <option value="normal">Normal</option><option value="high">High</option><option value="urgent">Urgent</option>
                  </Select></label>
                <div className="flex items-start gap-2 rounded-lg bg-ink-50 px-3 py-2 text-xs text-ink-600"><AlertCircle className="mt-0.5 h-3.5 w-3.5 shrink-0" />Expired transfers can no longer be opened if not yet delivered.</div>
              </div>
            </div>
          </Card>
        </div>
      </div>

      <div className="mt-4 flex flex-wrap items-center gap-3">
        <span className="inline-flex h-12 items-center gap-2 rounded-xl border border-maroon-200 bg-maroon-50 px-4 text-[15px] font-medium"><Paperclip className="h-5 w-5" />Total Files : {atts.length} &nbsp;|&nbsp; Total Size : {fmtSize(totalSize)}</span>
        <Button size="lg" icon={Send} loading={sending} disabled={uploading} onClick={send} className="!h-12 min-w-[220px] text-[17px]">{uploading ? 'Uploading…' : 'Send Data'}</Button>
        <Button size="lg" variant="outline" icon={RefreshCw} onClick={reset} className="!h-12">Clear</Button>
        <Button size="lg" variant="outline" icon={Save} onClick={saveDraft} disabled={sending} className="!h-12">Save as Draft</Button>
        <Button size="lg" variant="ghost" icon={FileText} onClick={() => setDraftsOpen(true)} className="!h-12">Drafts{drafts.length ? ` (${drafts.length})` : ''}</Button>
      </div>

      <Modal open={draftsOpen} onClose={() => setDraftsOpen(false)} title="Drafts" icon={FileText} size="lg">
        {drafts.length === 0 ? <Empty icon={FileText} title="No drafts" body="Use “Save as Draft” to keep a message for later." /> : (
          <ul className="divide-y divide-ink-100">
            {drafts.map((d) => (
              <li key={d.id} className="flex items-center gap-3 py-3">
                <FileText className="h-5 w-5 text-maroon-600" />
                <div className="min-w-0 flex-1 cursor-pointer" onClick={() => openDraft(d)}>
                  <div className="truncate text-sm font-medium">{d.subject || '(no subject)'}</div>
                  <div className="text-xs text-ink-500">{d.recipient_user_ids.length} receiver(s) · {d.attachments.length} file(s) · saved {timeAgo(d.updated_at)}</div>
                </div>
                <Button size="sm" variant="secondary" onClick={() => openDraft(d)}>Open</Button>
                <IconButton icon={Trash2} tone="danger" label="Delete draft" onClick={async () => { await api.del(`/api/drafts/${d.id}`); if (draftId === d.id) setDraftId(null); loadDrafts() }} />
              </li>
            ))}
          </ul>
        )}
      </Modal>
    </div>
  )
}

function DeliveryPanel({ result, onClose, onHistory }: { result: any; onClose: () => void; onHistory: () => void }) {
  const t = result.transfer
  const icon = (s: string) => s === 'read' ? MailCheck : s === 'delivered' ? CheckCircle2 : s === 'failed' ? AlertCircle : s === 'sent' ? Send : Clock
  return (
    <Panel className="mb-4" icon={Inbox} title={<span className="flex items-center gap-2">Transfer {t.transfer_uid} – live delivery status</span>}
      actions={<span className="flex items-center gap-2"><button onClick={onHistory} className="rounded-lg bg-white/15 px-3 py-1 font-semibold hover:bg-white/25">Open in history</button><button onClick={onClose} aria-label="Close" className="rounded p-1 hover:bg-white/15"><X className="h-4 w-4" /></button></span>}>
      <div className="mb-2 flex items-center gap-2 text-sm"><StatusBadge status={result.aggregate} /><span className="text-ink-600">{t.subject} · {t.file_count} file(s) · Pending → Sent → Delivered (PC acknowledged) → Read</span></div>
      <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-4">
        {result.recipients.map((r: any) => {
          const I = icon(r.status)
          return (
            <div key={r.id} className="flex items-center gap-3 rounded-xl border border-ink-100 px-3 py-2">
              <I className={cx('h-5 w-5', r.status === 'failed' ? 'text-red-500' : r.status === 'pending' ? 'text-amber-500' : 'text-emerald-600')} />
              <div className="min-w-0 flex-1"><div className="truncate text-sm font-semibold">{r.pc || r.name}</div><div className="truncate text-xs text-ink-500">{r.name}</div></div>
              <StatusBadge status={r.status} />
            </div>
          )
        })}
      </div>
    </Panel>
  )
}
