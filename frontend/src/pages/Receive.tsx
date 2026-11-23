import { useEffect, useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import {
  AlertCircle, Archive, ArchiveRestore, ClipboardCopy, Copy, Download, Eye, FileText, Filter, Forward, Inbox, Mail,
  MailCheck, MailOpen, Paperclip, RefreshCw, Reply, Star, Trash2, Undo2, Database, List,
} from 'lucide-react'
import { api, download, qs } from '../lib/api'
import { useAuth } from '../lib/auth'
import { copyImageFromUrl, copyRich, copyText } from '../lib/clipboard'
import { useRealtime, useRealtimeEvent } from '../lib/realtime'
import { useToast } from '../lib/toast'
import { fmtDate, fmtDateTime, fmtSize, fmtTime } from '../lib/format'
import {
  Button, Card, Checkbox, cx, Empty, ErrorBox, FileIcon, IconButton, Input, KV, Loading, Modal, PageHeader, Pagination,
  Panel, PriorityBadge, SearchInput, useConfirm,
} from '../components/ui'

const CATS = [
  { key: 'all', label: 'All Received', icon: Mail }, { key: 'unread', label: 'Unread', icon: Mail },
  { key: 'read', label: 'Read', icon: MailOpen }, { key: 'attachments', label: 'With Attachment', icon: Paperclip },
  { key: 'text', label: 'Text Only', icon: List }, { key: 'flagged', label: 'Flagged', icon: Star, gap: true },
  { key: 'important', label: 'Important', icon: AlertCircle }, { key: 'archived', label: 'Archived', icon: Archive, gap: true },
  { key: 'deleted', label: 'Deleted', icon: Trash2 },
]

export default function Receive() {
  const [params, setParams] = useSearchParams()
  const [cat, setCat] = useState(params.get('category') || 'all')
  const [q, setQ] = useState('')
  const [from, setFrom] = useState('')
  const [to, setTo] = useState('')
  const [applied, setApplied] = useState({ q: '', from: '', to: '' })
  const [page, setPage] = useState(1)
  const [pageSize, setPageSize] = useState(10)
  const [data, setData] = useState<any>(null)
  const [counts, setCounts] = useState<any>({})
  const [err, setErr] = useState('')
  const [sel, setSel] = useState<Set<number>>(new Set())
  const [openId, setOpenId] = useState<number | null>(params.get('open') ? Number(params.get('open')) : null)
  const { setUnread } = useRealtime()
  const toast = useToast()
  const confirm = useConfirm()

  const load = () => {
    api.get(`/api/inbox${qs({ category: cat, q: applied.q, date_from: applied.from, date_to: applied.to, page, page_size: pageSize })}`)
      .then((d) => { setData(d); setErr('') }).catch((e) => setErr(e.message))
    api.get('/api/inbox/counts').then((c) => { setCounts(c); setUnread(c.unread) }).catch(() => {})
  }
  useEffect(load, [cat, applied, page, pageSize])
  useEffect(() => { setPage(1); setSel(new Set()) }, [cat, applied, pageSize])
  useEffect(() => { const t = setTimeout(() => setApplied((a) => ({ ...a, q })), 300); return () => clearTimeout(t) }, [q])
  useEffect(() => { const o = params.get('open'); if (o) { setOpenId(Number(o)); params.delete('open'); setParams(params, { replace: true }) } }, [params])
  useRealtimeEvent((m) => { if (m.type === 'transfer.new') load() }, [cat, applied, page, pageSize])

  const bulk = async (action: string, ids = Array.from(sel)) => {
    if (!ids.length) return toast.info('Select messages first')
    if (action === 'purge' && !(await confirm({ title: 'Delete permanently?', body: `${ids.length} message(s) will be removed from your inbox permanently. Transfer history is kept for audit.`, danger: true, confirmLabel: 'Delete permanently' }))) return
    await api.post('/api/inbox/bulk', { recipient_ids: ids, action })
    setSel(new Set())
    toast.success({ read: 'Marked as read', flag: 'Flagged', unflag: 'Unflagged', archive: 'Archived', unarchive: 'Moved to inbox', delete: 'Moved to Deleted', restore: 'Restored', purge: 'Deleted permanently', important: 'Marked important', unimportant: 'Unmarked' }[action] || 'Done')
    load()
  }

  const items: any[] = data?.items || []
  const allSel = items.length > 0 && items.every((i) => sel.has(i.recipient_id))
  const stg = counts.storage

  return (
    <div>
      <PageHeader title="Receive Data (Inbox)" subtitle="View, Copy, Download and Manage Received Data" icon={Download} />
      <Card className="mb-4 flex flex-wrap items-center gap-3 p-3">
        <SearchInput value={q} onChange={setQ} placeholder="Search by Sender, Subject, File Name or Transfer ID…" className="min-w-[280px] flex-1" />
        <label className="flex items-center gap-2 text-[15px] font-semibold">From <Input type="date" value={from} onChange={(e) => setFrom(e.target.value)} className="w-40" /></label>
        <label className="flex items-center gap-2 text-[15px] font-semibold">To <Input type="date" value={to} onChange={(e) => setTo(e.target.value)} className="w-40" /></label>
        <Button icon={Filter} onClick={() => setApplied({ q, from, to })}>Filter</Button>
        <Button variant="outline" icon={RefreshCw} onClick={() => { setFrom(''); setTo(''); setQ(''); setApplied({ q: '', from: '', to: '' }); load() }}>Refresh</Button>
      </Card>

      <div className="grid gap-4 xl:grid-cols-[230px_1fr_420px]">
        <div className="space-y-4">
          <Card className="p-3">
            <h3 className="mb-2 flex items-center gap-2 px-2 text-[19px] font-bold"><Inbox className="h-6 w-6" />My Inbox</h3>
            {CATS.map((c) => (
              <div key={c.key}>
                {c.gap && <div className="my-1.5 border-t border-ink-100" />}
                <button onClick={() => setCat(c.key)}
                  className={cx('flex w-full items-center gap-3 rounded-xl px-3 py-2 text-[15px] transition', cat === c.key ? 'bg-maroon-100 font-bold text-ink-900' : 'text-ink-800 hover:bg-ink-50')}>
                  <c.icon className={cx('h-5 w-5', c.key === 'flagged' && 'text-amber-500', c.key === 'important' && 'text-red-600', c.key === 'deleted' && 'text-red-600')} />
                  <span className="flex-1 text-left">{c.label}</span>
                  {counts[c.key] !== undefined && (c.key !== 'archived' && c.key !== 'deleted' || counts[c.key] > 0) &&
                    <span className={cx('min-w-7 rounded-lg px-2 py-0.5 text-center text-xs font-bold', c.key === 'unread' && counts[c.key] ? 'bg-red-600 text-white' : 'bg-ink-100 text-ink-700')}>{counts[c.key]}</span>}
                </button>
              </div>
            ))}
          </Card>
          <Card className="p-4">
            <h3 className="flex items-center gap-2 text-[17px] font-bold"><Database className="h-5 w-5" />Storage Status</h3>
            {stg ? <>
              <div className="mt-2 text-[14px]">Your files : <b>{fmtSize(stg.inbox_bytes)}</b>{stg.quota ? <> / {fmtSize(stg.quota)}</> : null}</div>
              {stg.quota > 0 && <div className="text-[13px] text-ink-600">({(stg.inbox_bytes / stg.quota * 100).toFixed(2)}% of server quota)</div>}
              <div className="mt-2 h-3 overflow-hidden rounded-full bg-ink-100"><div className="h-full rounded-full bg-emerald-500" style={{ width: `${stg.quota ? Math.max(2, Math.min(100, stg.inbox_bytes / stg.quota * 100)) : 2}%` }} /></div>
            </> : <div className="mt-2 text-sm text-ink-500">—</div>}
          </Card>
        </div>

        <Card className="min-w-0 overflow-hidden">
          {sel.size > 0 && (
            <div className="flex flex-wrap items-center gap-1 border-b border-ink-100 bg-maroon-50 px-3 py-1.5">
              <span className="px-1 text-xs font-bold text-maroon-800">{sel.size} selected</span>
              {cat === 'deleted' ? (<>
                <Button size="sm" variant="ghost" icon={Undo2} onClick={() => bulk('restore')}>Restore</Button>
                <Button size="sm" variant="ghost" icon={Trash2} onClick={() => bulk('purge')}>Delete forever</Button>
              </>) : (<>
                <Button size="sm" variant="ghost" icon={MailCheck} onClick={() => bulk('read')}>Mark read</Button>
                <Button size="sm" variant="ghost" icon={Star} onClick={() => bulk('flag')}>Flag</Button>
                <Button size="sm" variant="ghost" icon={cat === 'archived' ? ArchiveRestore : Archive} onClick={() => bulk(cat === 'archived' ? 'unarchive' : 'archive')}>{cat === 'archived' ? 'Unarchive' : 'Archive'}</Button>
                <Button size="sm" variant="ghost" icon={Trash2} onClick={() => bulk('delete')}>Delete</Button>
              </>)}
            </div>
          )}
          {err ? <ErrorBox error={err} onRetry={load} /> : !data ? <Loading /> : items.length === 0 ? (
            <Empty icon={Inbox} title={applied.q ? 'No matching messages' : 'Nothing here'} body={cat === 'all' ? 'When someone sends you data it appears here instantly.' : undefined} />
          ) : (<>
            <div className="overflow-x-auto">
              <table className="w-full border-collapse text-left text-[13.5px]">
                <thead><tr className="bg-ink-100/80">
                  <th className="w-10 px-3 py-2.5"><Checkbox checked={allSel} onChange={(v) => setSel(v ? new Set(items.map((i) => i.recipient_id)) : new Set())} /></th>
                  <th className="w-8" />
                  {['From (PC / User)', 'Subject / Message', 'Type', 'Size', 'Received On ↓'].map((h) => <th key={h} className="whitespace-nowrap px-2.5 py-2.5 font-bold">{h}</th>)}
                  <th className="w-6" />
                </tr></thead>
                <tbody>
                  {items.map((m) => {
                    const unread = !m.is_read
                    return (
                      <tr key={m.recipient_id} onClick={() => setOpenId(m.recipient_id)}
                        className={cx('cursor-pointer border-b border-ink-100 transition', openId === m.recipient_id ? 'bg-maroon-50' : 'hover:bg-ink-50')}>
                        <td className="px-3 py-2" onClick={(e) => e.stopPropagation()}><Checkbox checked={sel.has(m.recipient_id)} onChange={(v) => setSel((s) => { const n = new Set(s); v ? n.add(m.recipient_id) : n.delete(m.recipient_id); return n })} /></td>
                        <td><Mail className={cx('h-5 w-5', unread ? 'text-amber-500' : 'text-amber-300')} /></td>
                        <td className="whitespace-nowrap px-2.5 leading-tight"><div className="font-bold">{m.sender_pc || m.sender_ip}</div><div className="text-ink-700">{m.sender_name}</div></td>
                        <td className="max-w-[300px] px-2.5 leading-tight">
                          <div className="flex items-center gap-1.5">
                            {m.is_flagged && <Star className="h-3.5 w-3.5 shrink-0 fill-amber-400 text-amber-500" />}
                            <span className={cx('truncate', unread ? 'font-bold' : 'font-semibold')}>{m.subject || '(no subject)'}</span><PriorityBadge priority={m.priority} />
                          </div>
                          <div className="truncate text-ink-600">{m.preview || m.file_names?.join(', ')}</div>
                        </td>
                        <td className="px-2.5">{m.file_types.length ? <FileIcon ext={m.file_types[0]} className="h-7 w-7" /> : <FileText className="h-5 w-5 text-ink-400" />}</td>
                        <td className="whitespace-nowrap px-2.5">{m.total_size ? fmtSize(m.total_size) : '—'}</td>
                        <td className="whitespace-nowrap px-2.5 leading-tight">{fmtDate(m.created_at)}<div>{fmtTime(m.created_at)}</div></td>
                        <td className="pr-3">{unread && <span className="block h-2.5 w-2.5 rounded-full bg-red-600" title="Unread" />}</td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
            </div>
            <Pagination page={data.page} pageSize={pageSize} total={data.total} onPage={setPage} onPageSize={setPageSize} />
          </>)}
        </Card>

        <div>{openId ? <MessagePreview rid={openId} onChanged={load} onClosed={() => setOpenId(null)} />
          : <Panel title="Message Preview" icon={Mail}><div className="py-14 text-center text-sm text-ink-500"><Mail className="mx-auto mb-2 h-10 w-10 text-ink-300" />Select a message to preview it here.</div></Panel>}</div>
      </div>
    </div>
  )
}

function MessagePreview({ rid, onChanged, onClosed }: { rid: number; onChanged: () => void; onClosed: () => void }) {
  const [m, setM] = useState<any>(null)
  const [err, setErr] = useState('')
  const [preview, setPreview] = useState<any>(null)
  const toast = useToast()
  const nav = useNavigate()
  const { can, readOnly } = useAuth()
  useEffect(() => { setM(null); setErr(''); api.get(`/api/inbox/${rid}`).then((x) => { setM(x); onChanged() }).catch((e) => setErr(e.message)) }, [rid])

  const flag = async (patch: any) => { const r = await api.patch(`/api/inbox/${rid}`, patch); setM((x: any) => ({ ...x, ...r })); onChanged() }
  const copyMessage = async () => {
    try {
      await copyRich(m.body_html, m.body_text)
      toast.success('Message copied to this PC\'s clipboard', window.isSecureContext ? undefined : 'Plain text copied (HTTPS enables rich copy).')
    } catch (e: any) { toast.error('Copy failed', e.message) }
  }
  const copyFile = async (a: any) => {
    const url = `/api/attachments/${a.uid}?inline=1`
    try {
      if (['png', 'jpg', 'jpeg'].includes(a.extension) && await copyImageFromUrl(url)) return toast.success('Image copied to clipboard')
      if (a.extension === 'txt') { await copyText(await (await fetch(url, { credentials: 'same-origin' })).text()); return toast.success('Text file contents copied') }
      await copyText(a.name)
      toast.info('File name copied', 'Browsers cannot place documents on the Windows clipboard — use Download to save the file.')
    } catch (e: any) { toast.error('Copy failed', e.message) }
  }
  const reply = () => nav('/send', { state: { reply: { transfer_id: m.id, transfer_uid: m.transfer_uid, subject: m.subject, sender_user_id: m.sender_user_id, sender_name: m.sender_name, body_html: m.body_html, created_at: m.created_at } } })
  const forward = () => nav('/send', { state: { forward: { transfer_id: m.id, transfer_uid: m.transfer_uid, subject: m.subject, sender_name: m.sender_name, body_html: m.body_html, attachments: m.attachments } } })

  if (err) return <Panel title="Message Preview" icon={Mail}><ErrorBox error={err} /></Panel>
  if (!m) return <Panel title="Message Preview" icon={Mail}><Loading /></Panel>
  const canWrite = can('send') && !readOnly
  return (
    <Panel title="Message Preview" icon={Mail} actions={<span className="text-[13px] font-semibold">ID : {m.transfer_uid}</span>} bodyClassName="space-y-3 p-3">
      <div className="rounded-xl border border-ink-200 bg-ink-50/50 p-3">
        <KV rows={[
          ['From', <><b>{m.sender_pc || m.sender_ip}</b> ({m.sender_name})</>],
          ['Received', fmtDateTime(m.created_at)],
          ['Subject', <span className="flex flex-wrap items-center gap-1.5"><b>{m.subject || '(no subject)'}</b><PriorityBadge priority={m.priority} /></span>],
        ]} />
      </div>
      <div className="rich max-h-60 min-h-[90px] overflow-y-auto rounded-xl border border-ink-200 p-3 text-[14px]">
        {m.body_html ? <div dangerouslySetInnerHTML={{ __html: m.body_html }} /> : <span className="text-ink-500">No message text — file transfer only.</span>}
      </div>
      {m.attachments.length > 0 && (
        <div className="rounded-xl border border-ink-200">
          <div className="flex items-center justify-between border-b border-ink-100 px-3 py-2">
            <span className="flex items-center gap-2 text-[16px] font-bold"><Paperclip className="h-5 w-5 text-maroon-700" />Attachments ({m.attachments.length})</span>
            <span className="text-[13px] font-semibold">Total Size : {fmtSize(m.total_size)}</span>
          </div>
          <ul className="divide-y divide-ink-100">
            {m.attachments.map((a: any) => (
              <li key={a.uid} className="flex items-center gap-2 px-3 py-1.5">
                <FileIcon ext={a.extension} className="h-7 w-7" />
                <span className="min-w-0 flex-1 truncate text-[13.5px] font-medium">{a.name}</span>
                <span className="whitespace-nowrap text-[13px]">{fmtSize(a.size)}</span>
                {previewable(a.extension) && <IconButton icon={Eye} label="Preview" onClick={() => setPreview(a)} />}
                <IconButton icon={Download} label="Download" onClick={() => download(`/api/attachments/${a.uid}`)} />
                <IconButton icon={Copy} label="Copy file" onClick={() => copyFile(a)} />
              </li>
            ))}
          </ul>
        </div>
      )}
      <div className="grid grid-cols-2 gap-2">
        <Button size="lg" icon={ClipboardCopy} onClick={copyMessage} disabled={!m.body_text}>Copy Message</Button>
        <Button size="lg" icon={Download} className="!bg-emerald-600 hover:!bg-emerald-700" disabled={!m.attachments.length} onClick={() => download(`/api/transfers/${m.id}/zip`)}>Download All</Button>
      </div>
      <div className="grid grid-cols-3 gap-2">
        <Button variant="outline" icon={Reply} disabled={!canWrite} onClick={reply}>Reply</Button>
        <Button variant="outline" icon={Forward} disabled={!canWrite} onClick={forward}>Forward</Button>
        <Button variant="outline" icon={MailCheck} disabled={m.is_read} onClick={() => flag({ is_read: true })}>Mark as Read</Button>
        <Button variant="outline" icon={Star} onClick={() => flag({ is_flagged: !m.is_flagged })} className={m.is_flagged ? '!border-amber-300 !bg-amber-50' : ''}>{m.is_flagged ? 'Unflag' : 'Flag'}</Button>
        <Button variant="outline" icon={m.is_archived ? ArchiveRestore : Archive} onClick={() => flag({ is_archived: !m.is_archived })}>{m.is_archived ? 'Unarchive' : 'Archive'}</Button>
        <Button variant="outline" icon={m.is_deleted ? Undo2 : Trash2} className={m.is_deleted ? '' : '!border-red-200 !bg-red-50 !text-red-600'}
          onClick={async () => { await flag({ is_deleted: !m.is_deleted }); if (!m.is_deleted) onClosed() }}>{m.is_deleted ? 'Restore' : 'Delete'}</Button>
      </div>
      <div className="flex flex-wrap gap-x-3 text-xs text-ink-500">
        <button className="hover:text-maroon-700" onClick={() => flag({ is_important: !m.is_important })}>{m.is_important ? '★ Marked important' : '☆ Mark important'}</button>
        {m.read_at && <span>Read {fmtDateTime(m.read_at)}{m.read_receipt && ' · sender notified'}</span>}
        {m.expires_at && <span className="text-amber-700">Expires {fmtDateTime(m.expires_at)}</span>}
      </div>
      {preview && <FilePreview name={preview.name} ext={preview.extension} url={`/api/attachments/${preview.uid}?inline=1`} downloadUrl={`/api/attachments/${preview.uid}`} onClose={() => setPreview(null)} />}
    </Panel>
  )
}

export const previewable = (ext: string) => ['pdf', 'png', 'jpg', 'jpeg', 'gif', 'txt', 'bmp', 'webp'].includes((ext || '').toLowerCase())

export function FilePreview({ name, ext, url, downloadUrl, onClose }: { name: string; ext: string; url: string; downloadUrl: string; onClose: () => void }) {
  const e = ext.toLowerCase()
  return (
    <Modal open onClose={onClose} size="xl" title={name} icon={Eye} footer={<Button icon={Download} onClick={() => download(downloadUrl)}>Download</Button>}>
      {['png', 'jpg', 'jpeg', 'gif', 'bmp', 'webp'].includes(e) ? <img src={url} alt={name} className="mx-auto max-h-[65vh] rounded-lg" />
        : previewable(e) ? <iframe src={url} title={name} className="h-[65vh] w-full rounded-lg border border-ink-100 bg-white" />
        : <Empty title="Preview not available" body="Office documents open in Word/Excel/PowerPoint after downloading." />}
    </Modal>
  )
}


