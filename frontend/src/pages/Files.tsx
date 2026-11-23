import { useEffect, useRef, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import {
  ChevronRight, Copy, Database, Download, Edit3, Eye, FileText, Folder, FolderInput, FolderOpen, FolderPlus,
  Globe, History, Lock, Plus, RefreshCw, Share2, Trash2, Undo2, Upload, Users as UsersIcon, X, Building2, CloudUpload,
  MoreVertical, FolderArchive, ExternalLink,
} from 'lucide-react'
import { api, ApiError, download, qs, uploadFile } from '../lib/api'
import { useAuth } from '../lib/auth'
import { useToast } from '../lib/toast'
import { fmtDateTime, fmtSize } from '../lib/format'
import { FilePreview, previewable } from './Receive'
import {
  Badge, Button, Card, Checkbox, cx, Empty, ErrorBox, Field, FileIcon, IconButton, Input, KV, Loading, Modal, PageHeader, Pagination,
  Panel, Progress, SearchInput, Select, StatCard, Table, Tabs, Td, Textarea, Th, useConfirm,
} from '../components/ui'

type View = { kind: 'all' | 'shared' | 'recycle' | 'folder'; folderId?: number; name: string }

export default function Files() {
  const { readOnly, isAdmin } = useAuth()
  const toast = useToast()
  const confirm = useConfirm()
  const [params] = useSearchParams()
  const [view, setView] = useState<View>(params.get('view') === 'shared' ? { kind: 'shared', name: 'Shared with Me' } : { kind: 'all', name: 'All Files' })
  const [tree, setTree] = useState<any>(null)
  const [q, setQ] = useState('')
  const [sort, setSort] = useState('date')
  const [page, setPage] = useState(1)
  const [pageSize, setPageSize] = useState(10)
  const [data, setData] = useState<any>(null)
  const [storage, setStorage] = useState<any>(null)
  const [err, setErr] = useState('')
  const [uploadOpen, setUploadOpen] = useState(false)
  const [detail, setDetail] = useState<number | null>(null)
  const [share, setShare] = useState<any>(null)
  const [moveCopy, setMoveCopy] = useState<{ file: any; mode: 'move' | 'copy' } | null>(null)
  const [rename, setRename] = useState<any>(null)
  const [preview, setPreview] = useState<any>(null)
  const [newFolder, setNewFolder] = useState(false)
  const [renameFolder, setRenameFolder] = useState<any>(null)
  const [activeId, setActiveId] = useState<number | null>(null)
  const [sel, setSel] = useState<Set<number>>(new Set())
  const [menu, setMenu] = useState<number | null>(null)

  const loadTree = () => { api.get('/api/files/folders').then(setTree); api.get('/api/files/storage').then(setStorage) }
  const load = () => {
    api.get(`/api/files${qs({ view: view.kind, folder_id: view.folderId, q, sort, page, page_size: pageSize })}`)
      .then((d) => { setData(d); setErr('') }).catch((e) => setErr(e.message))
  }
  const reloadAll = () => { load(); loadTree() }
  useEffect(() => { loadTree() }, [])
  useEffect(() => { const t = setTimeout(load, q ? 250 : 0); return () => clearTimeout(t) }, [view, q, sort, page, pageSize])
  useEffect(() => { setPage(1); setSel(new Set()); setActiveId(null) }, [view, q, sort, pageSize])

  const items: any[] = data?.items || []
  const active = items.find((f) => f.id === activeId) || items[0]
  const target = items.find((f) => sel.has(f.id)) || active
  const recycleView = view.kind === 'recycle'

  const recycle = async (f: any) => {
    if (!f) return
    if (!(await confirm({ title: `Delete ${f.name}?`, body: 'The file moves to the Recycle Bin and can be restored.', confirmLabel: 'Move to Recycle Bin', danger: true }))) return
    try { await api.del(`/api/files/${f.id}`); toast.success('Moved to Recycle Bin'); reloadAll() } catch (e: any) { toast.error(e.message) }
  }
  const deleteSelected = async () => {
    const list = items.filter((f) => sel.has(f.id) && f.can_modify)
    if (!list.length) return target ? recycle(target) : toast.info('Select files first')
    if (!(await confirm({ title: `Delete ${list.length} file(s)?`, body: 'They move to the Recycle Bin and can be restored.', confirmLabel: 'Move to Recycle Bin', danger: true }))) return
    for (const f of list) await api.del(`/api/files/${f.id}`).catch(() => {})
    toast.success(`${list.length} file(s) moved to Recycle Bin`); setSel(new Set()); reloadAll()
  }
  const downloadSelected = () => {
    const list = items.filter((f) => sel.has(f.id))
    const go = list.length ? list : target ? [target] : []
    if (!go.length) return toast.info('Select a file first')
    go.forEach((f, i) => setTimeout(() => download(`/api/files/${f.id}/download`), i * 400))
  }
  const restore = async (f: any) => { await api.post(`/api/files/${f.id}/restore`); toast.success(`${f.name} restored`); reloadAll() }
  const purge = async (f: any) => {
    if (!(await confirm({ title: `Permanently delete ${f.name}?`, body: 'All versions are erased from the server. This cannot be undone.', confirmLabel: 'Delete permanently', danger: true }))) return
    await api.del(`/api/files/${f.id}/permanent`); reloadAll()
  }
  const emptyBin = async () => {
    if (!(await confirm({ title: 'Empty Recycle Bin?', body: isAdmin ? 'All files in the Recycle Bin will be erased permanently.' : 'Your files in the Recycle Bin will be erased permanently.', confirmLabel: 'Empty', danger: true }))) return
    const r = await api.post('/api/files/recycle/empty'); toast.success(`${r.purged} file(s) erased`); reloadAll()
  }

  const folders = tree?.folders || []
  const currentFolder = folders.find((f: any) => f.id === view.folderId)
  const navItem = (v: View, icon: any, count?: number, tone = 'text-amber-500') => {
    const on = v.kind === view.kind && v.folderId === view.folderId
    const I = icon
    return (
      <button key={`${v.kind}-${v.folderId}`} onClick={() => setView(v)} className={cx('flex w-full items-center gap-2 rounded-lg px-2 py-1.5 text-[15px] transition', on ? 'bg-maroon-100 font-bold' : 'hover:bg-ink-50')}>
        <ChevronRight className="h-3.5 w-3.5 text-ink-500" /><I className={cx('h-5 w-5 shrink-0', tone)} fill={tone.includes('amber') ? 'currentColor' : 'none'} fillOpacity={0.35} />
        <span className="flex-1 truncate text-left">{v.name}</span>
        {count !== undefined && <span className={cx('min-w-9 rounded-lg px-2 py-0.5 text-center text-xs font-bold', on ? 'bg-white' : 'bg-ink-100 text-ink-700')}>{count}</span>}
      </button>
    )
  }
  const tb = 'h-11 text-[15px]'
  const noSel = !target

  return (
    <div>
      <PageHeader title="File Depository (Central Repository)" subtitle="Upload, Store, Share and Manage Common Files & Folders" icon={FolderOpen} />
      {storage && (
        <div className="mb-4 grid grid-cols-2 gap-3 md:grid-cols-3 xl:grid-cols-6">
          <StatCard label="Total Folders" value={storage.folders} icon={Folder} tone="orange" />
          <StatCard label="Total Files" value={storage.files} icon={FileText} tone="blue" />
          <StatCard label="Total Size" value={fmtSize(storage.used)} icon={Database} tone="pink" hint="incl. all versions" />
          <StatCard label="This Month Upload" value={<>{storage.month_uploads} <span className="text-lg font-bold">({fmtSize(storage.month_upload_bytes)})</span></>} icon={CloudUpload} tone="green" />
          <StatCard label="This Month Download" value={<>{storage.month_downloads} <span className="text-lg font-bold">({fmtSize(storage.month_download_bytes)})</span></>} icon={Download} tone="blue" />
          <div className="flex flex-col justify-center rounded-2xl border border-ink-200 bg-white px-4 py-3 shadow-sm">
            <div className="text-[15px] font-semibold text-ink-800">Storage Used :</div>
            <div className="whitespace-nowrap text-[17px] font-extrabold">{fmtSize(storage.used)}{storage.quota ? ` / ${fmtSize(storage.quota)}` : ''}</div>
            <div className="mt-2 flex items-center gap-2"><Progress value={storage.quota ? Math.max(1, storage.percent) : 1} tone={storage.percent > 90 ? 'red' : storage.percent > 75 ? 'amber' : 'green'} className="h-3" /><b className="text-sm">{storage.percent}%</b></div>
          </div>
        </div>
      )}

      <div className="mb-3 flex flex-wrap items-center gap-2">
        {!readOnly && <Button className={tb} icon={Upload} onClick={() => setUploadOpen(true)}>Upload File(s)</Button>}
        {!readOnly && <Button className={tb} variant="outline" icon={FolderPlus} onClick={() => setNewFolder(true)}>New Folder</Button>}
        <Button className={tb} variant="outline" icon={Download} disabled={noSel || recycleView} onClick={downloadSelected}>Download</Button>
        {!readOnly && <Button className={tb} variant="outline" icon={FolderInput} disabled={noSel || recycleView || !target?.can_modify} onClick={() => setMoveCopy({ file: target, mode: 'move' })}>Move To</Button>}
        {!readOnly && <Button className={tb} variant="outline" icon={Copy} disabled={noSel || recycleView} onClick={() => setMoveCopy({ file: target, mode: 'copy' })}>Copy</Button>}
        {!readOnly && <Button className={tb} variant="outline" icon={Edit3} disabled={noSel || recycleView || !target?.can_modify} onClick={() => setRename(target)}>Rename</Button>}
        {!readOnly && !recycleView && <Button className={cx(tb, 'border border-red-200 bg-red-50 !text-red-600 hover:bg-red-100')} variant="ghost" icon={Trash2} disabled={noSel} onClick={deleteSelected}>Delete</Button>}
        {recycleView && <Button className={tb} variant="danger" icon={Trash2} onClick={emptyBin}>Empty Recycle Bin</Button>}
        <SearchInput value={q} onChange={setQ} placeholder="Search file or folder…" className="ml-auto min-w-[260px]" />
      </div>

      <div className="grid gap-4 xl:grid-cols-[270px_1fr] 2xl:grid-cols-[270px_1fr_380px]">
        <Card className="h-fit p-3">
          <div className="mb-2 flex items-center justify-between px-1">
            <h3 className="text-[20px] font-bold">Folders</h3>
            <div className="flex gap-1">{!readOnly && <IconButton icon={Plus} label="New folder" onClick={() => setNewFolder(true)} />}<IconButton icon={RefreshCw} label="Refresh" onClick={reloadAll} /></div>
          </div>
          {navItem({ kind: 'all', name: 'All Files' }, Folder, tree?.virtual.all)}
          {folders.filter((f: any) => f.system_key !== 'archive').map((f: any) => navItem({ kind: 'folder', folderId: f.id, name: f.name }, Folder, f.count))}
          {navItem({ kind: 'shared', name: 'Shared with Me' }, Folder, tree?.virtual.shared)}
          {folders.filter((f: any) => f.system_key === 'archive').map((f: any) => navItem({ kind: 'folder', folderId: f.id, name: f.name }, Folder, f.count))}
          {navItem({ kind: 'recycle', name: 'Recycle Bin' }, Trash2, tree?.virtual.recycle, 'text-amber-600')}
          {currentFolder && !currentFolder.is_system && !readOnly && (
            <div className="mt-2 flex gap-1 border-t border-ink-100 pt-2">
              <Button size="sm" variant="ghost" icon={Edit3} onClick={() => setRenameFolder(currentFolder)}>Rename folder</Button>
              <Button size="sm" variant="ghost" icon={Trash2} onClick={async () => { try { await api.del(`/api/files/folders/${currentFolder.id}`); setView({ kind: 'all', name: 'All Files' }); loadTree() } catch (e: any) { toast.error(e.message) } }}>Delete</Button>
            </div>
          )}
        </Card>

        <Card className="min-w-0 overflow-hidden">
          <div className="flex items-center justify-between border-b border-ink-100 px-4 py-2.5">
            <div className="flex items-center gap-2 text-[15px]"><Folder className="h-5 w-5 fill-amber-400/40 text-amber-500" /><ChevronRight className="h-4 w-4 text-ink-400" /><b>{view.name}</b></div>
            <Select value={sort} onChange={(e) => setSort(e.target.value)} className="!w-40 !py-1.5"><option value="date">Newest first</option><option value="name">Name A–Z</option><option value="size">Largest first</option><option value="type">Type</option></Select>
          </div>
          {err ? <ErrorBox error={err} onRetry={load} /> : !data ? <Loading /> : items.length === 0 ? (
            <Empty icon={recycleView ? Trash2 : FolderArchive} title={recycleView ? 'Recycle Bin is empty' : 'No files here'}
              action={!readOnly && !recycleView && view.kind !== 'shared' && <Button icon={Upload} onClick={() => setUploadOpen(true)}>Upload files</Button>} />
          ) : (<>
            <div className="overflow-x-auto">
              <table className="w-full border-collapse text-left text-[13px]">
                <thead><tr className="bg-ink-100/80">
                  <th className="w-10 px-3 py-2.5"><Checkbox checked={items.every((f) => sel.has(f.id))} onChange={(v) => setSel(v ? new Set(items.map((f) => f.id)) : new Set())} /></th>
                  {['File / Folder Name', 'Type', 'Size', 'Uploaded By', recycleView ? 'Deleted On' : 'Upload Date & Time', 'Access'].map((h) => <th key={h} className="whitespace-nowrap px-2 py-2.5 font-bold">{h}</th>)}
                  <th className="px-2 py-2.5 text-center font-bold">Actions</th>
                </tr></thead>
                <tbody>
                  {items.map((f) => (
                    <tr key={f.id} onClick={() => setActiveId(f.id)} className={cx('cursor-pointer border-b border-ink-100', active?.id === f.id ? 'bg-maroon-50' : 'hover:bg-ink-50')}>
                      <td className="px-3 py-2" onClick={(e) => e.stopPropagation()}><Checkbox checked={sel.has(f.id)} onChange={(v) => setSel((x) => { const n = new Set(x); v ? n.add(f.id) : n.delete(f.id); return n })} /></td>
                      <td className="px-2"><div className="flex items-center gap-2.5"><FileIcon ext={f.extension} className="h-7 w-7" /><span className="max-w-[220px] truncate font-semibold">{f.name}</span>{f.version > 1 && <Badge>v{f.version}</Badge>}</div></td>
                      <td className="px-2">{f.extension.toUpperCase() || '—'}</td>
                      <td className="whitespace-nowrap px-2">{fmtSize(f.size)}</td>
                      <td className="whitespace-nowrap px-2">{f.uploaded_by_name}</td>
                      <td className="whitespace-nowrap px-2">{fmtDateTime(recycleView ? f.deleted_at : f.created_at)}</td>
                      <td className="px-2"><AccessBadge scope={f.access_scope} /></td>
                      <td className="relative whitespace-nowrap px-2 text-center" onClick={(e) => e.stopPropagation()}>
                        {recycleView ? (<>
                          <IconButton icon={Undo2} label="Restore" onClick={() => restore(f)} />
                          {f.can_modify && <IconButton icon={Trash2} tone="danger" label="Delete permanently" onClick={() => purge(f)} />}
                        </>) : (<>
                          {previewable(f.extension) ? <IconButton icon={Eye} label="Preview" onClick={() => setPreview(f)} /> : <span className="inline-block w-8" />}
                          <IconButton icon={Download} label="Download" onClick={() => download(`/api/files/${f.id}/download`)} />
                          <IconButton icon={MoreVertical} label="More actions" onClick={() => setMenu(menu === f.id ? null : f.id)} />
                          {menu === f.id && (<>
                            <div className="fixed inset-0 z-10" onClick={() => setMenu(null)} />
                            <div className="absolute right-2 top-9 z-20 w-44 rounded-xl border border-ink-100 bg-white p-1 text-left shadow-pop">
                              {[[Share2, 'Share / Access', () => setShare(f), f.can_modify], [FolderInput, 'Move To', () => setMoveCopy({ file: f, mode: 'move' }), f.can_modify],
                                [Copy, 'Copy', () => setMoveCopy({ file: f, mode: 'copy' }), !readOnly], [Edit3, 'Rename', () => setRename(f), f.can_modify],
                                [History, 'File History', () => setDetail(f.id), true], [Trash2, 'Delete', () => recycle(f), f.can_modify]].filter((x) => x[3]).map(([I, l, fn]: any) => (
                                <button key={l} onClick={() => { setMenu(null); fn() }} className={cx('flex w-full items-center gap-2 rounded-lg px-3 py-2 text-sm hover:bg-ink-50', l === 'Delete' && 'text-red-600')}><I className="h-4 w-4" />{l}</button>
                              ))}
                            </div>
                          </>)}
                        </>)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <Pagination page={data.page} pageSize={pageSize} total={data.total} onPage={setPage} onPageSize={setPageSize} label="items" />
          </>)}
        </Card>

        <div className="xl:col-span-2 2xl:col-span-1">
          <Panel title="File Preview & Details" icon={FileText}>
            {!active ? <div className="py-10 text-center text-sm text-ink-500">Select a file to see its details.</div> : (<>
              <div className="mb-3 flex items-center gap-3"><FileIcon ext={active.extension} className="h-12 w-12 text-[13px]" /><span className="min-w-0 break-words text-[18px] font-extrabold">{active.name}</span></div>
              <KV rows={[['Size', fmtSize(active.size)], ['Type', `${active.extension.toUpperCase()} Document`], ['Location', `/${active.folder}/${active.name}`],
                ['Uploaded By', active.uploaded_by_name], ['Uploaded On', fmtDateTime(active.created_at)], ['Version', `v${active.version}`],
                ['Access', <AccessBadge scope={active.access_scope} />]]} />
              <div className="mt-3 overflow-hidden rounded-xl border border-ink-200 bg-ink-50">
                {recycleView ? <div className="py-10 text-center text-sm text-ink-500">In Recycle Bin</div>
                  : ['png', 'jpg', 'jpeg', 'gif', 'bmp', 'webp'].includes(active.extension) ? <img src={`/api/files/${active.id}/download?inline=1`} alt={active.name} className="mx-auto max-h-56 object-contain" />
                  : ['pdf', 'txt'].includes(active.extension) ? <iframe src={`/api/files/${active.id}/download?inline=1#toolbar=0&view=FitH`} title={active.name} className="h-56 w-full bg-white" />
                  : <div className="flex h-40 flex-col items-center justify-center gap-2 text-sm text-ink-500"><FileIcon ext={active.extension} className="h-14 w-14 text-[15px]" />Preview not available – download to open in Office.</div>}
              </div>
              {recycleView ? (
                <div className="mt-3 grid grid-cols-2 gap-2"><Button icon={Undo2} onClick={() => restore(active)}>Restore</Button>{active.can_modify && <Button variant="danger" icon={Trash2} onClick={() => purge(active)}>Delete forever</Button>}</div>
              ) : (
                <div className="mt-3 grid grid-cols-2 gap-2">
                  <Button size="lg" icon={previewable(active.extension) ? Eye : ExternalLink} onClick={() => previewable(active.extension) ? setPreview(active) : download(`/api/files/${active.id}/download`)}>View / Open</Button>
                  <Button size="lg" variant="outline" icon={Download} onClick={() => download(`/api/files/${active.id}/download`)}>Download</Button>
                  <Button size="lg" variant="outline" icon={Share2} disabled={!active.can_modify} onClick={() => setShare(active)}>Share / Access</Button>
                  <Button size="lg" variant="outline" icon={History} onClick={() => setDetail(active.id)}>File History</Button>
                </div>
              )}
            </>)}
          </Panel>
        </div>
      </div>

      {uploadOpen && tree && <UploadDialog folders={folders} defaultFolder={view.kind === 'folder' ? view.folderId : undefined} onClose={() => setUploadOpen(false)} onDone={reloadAll} />}
      {detail && <FileDetail id={detail} onClose={() => setDetail(null)} onChanged={reloadAll} />}
      {share && <ShareDialog file={share} onClose={() => setShare(null)} onDone={() => { setShare(null); load() }} />}
      {moveCopy && <MoveCopyDialog {...moveCopy} folders={folders} onClose={() => setMoveCopy(null)} onDone={() => { setMoveCopy(null); reloadAll() }} />}
      {rename && <RenameDialog file={rename} onClose={() => setRename(null)} onDone={() => { setRename(null); load() }} />}
      {preview && <FilePreview name={preview.name} ext={preview.extension} url={`/api/files/${preview.id}/download?inline=1`} downloadUrl={`/api/files/${preview.id}/download`} onClose={() => setPreview(null)} />}
      {newFolder && <NewFolderDialog onClose={() => setNewFolder(false)} onDone={() => { setNewFolder(false); loadTree() }} />}
      {renameFolder && <NewFolderDialog folder={renameFolder} onClose={() => setRenameFolder(null)} onDone={(name: string) => { setRenameFolder(null); loadTree(); setView({ ...view, name }) }} />}
    </div>
  )
}

function AccessBadge({ scope }: { scope: string }) {
  const [cls, I, label] = scope === 'section' ? ['bg-sky-50 text-sky-700 ring-sky-200', Building2, 'Section Only']
    : scope === 'specific' ? ['bg-violet-50 text-violet-700 ring-violet-200', Lock, 'Specific Users'] : ['bg-emerald-50 text-emerald-700 ring-emerald-200', UsersIcon, 'All Users']
  return <span className={cx('inline-flex items-center gap-1.5 whitespace-nowrap rounded-lg px-2 py-1 text-[12.5px] font-semibold ring-1', cls)}><I className="h-4 w-4" />{label}</span>
}

function AccessPicker({ scope, setScope, sectionId, setSectionId, userIds, setUserIds }: any) {
  const [meta, setMeta] = useState<any>(null)
  const [q, setQ] = useState('')
  useEffect(() => {
    Promise.all([api.get('/api/sections'), api.get('/api/transfers/recipients').catch(() => [])]).then(([sections, users]) => setMeta({ sections, users }))
  }, [])
  return (
    <div className="space-y-3">
      <Tabs value={scope} onChange={setScope} tabs={[{ value: 'all', label: 'All Users', icon: Globe }, { value: 'section', label: 'Section Only', icon: Building2 }, { value: 'specific', label: 'Specific Users', icon: UsersIcon }]} />
      {scope === 'section' && meta && <Field label="Section"><Select value={sectionId || ''} onChange={(e) => setSectionId(Number(e.target.value) || null)}><option value="">Choose…</option>{meta.sections.map((s: any) => <option key={s.id} value={s.id}>{s.name}</option>)}</Select></Field>}
      {scope === 'specific' && meta && (
        <div className="rounded-xl border border-ink-100">
          <div className="border-b border-ink-100 p-2"><SearchInput value={q} onChange={setQ} placeholder="Find users" /></div>
          <div className="max-h-52 overflow-y-auto p-2">
            {meta.users.filter((u: any) => !q || u.full_name.toLowerCase().includes(q.toLowerCase()) || u.login_id.includes(q.toLowerCase())).map((u: any) => (
              <div key={u.id} className="px-2 py-1"><Checkbox checked={userIds.includes(u.id)} onChange={(v) => setUserIds(v ? [...userIds, u.id] : userIds.filter((x: number) => x !== u.id))}
                label={<span>{u.full_name} <span className="text-xs text-ink-500">{u.section}</span></span>} /></div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}

interface Up { key: string; file: File; progress: number; status: 'queued' | 'uploading' | 'done' | 'error' | 'duplicate' | 'skipped'; msg?: string }

function UploadDialog({ folders, defaultFolder, onClose, onDone }: { folders: any[]; defaultFolder?: number; onClose: () => void; onDone: () => void }) {
  const [folderId, setFolderId] = useState<number>(defaultFolder || folders[0]?.id)
  const [scope, setScope] = useState('all')
  const [sectionId, setSectionId] = useState<number | null>(null)
  const [userIds, setUserIds] = useState<number[]>([])
  const [desc, setDesc] = useState('')
  const [items, setItems] = useState<Up[]>([])
  const [busy, setBusy] = useState(false)
  const input = useRef<HTMLInputElement>(null)
  const toast = useToast()
  const upd = (key: string, p: Partial<Up>) => setItems((xs) => xs.map((x) => x.key === key ? { ...x, ...p } : x))

  const one = async (it: Up, onDup: string) => {
    upd(it.key, { status: 'uploading', progress: 0, msg: undefined })
    try {
      const r = await uploadFile('/api/files/upload', it.file, { folder_id: String(folderId), access_scope: scope, section_id: sectionId ? String(sectionId) : '', user_ids: JSON.stringify(userIds), description: desc, on_duplicate: onDup },
        (p) => upd(it.key, { progress: p })).promise
      upd(it.key, { status: r.skipped ? 'skipped' : 'done', progress: 100, msg: r.warning || (r.file?.version > 1 ? `Saved as version ${r.file.version}` : undefined) })
    } catch (e: any) {
      const err = e as ApiError
      if (err.status === 409 && err.data?.duplicate) upd(it.key, { status: 'duplicate', msg: err.message })
      else upd(it.key, { status: 'error', msg: err.message })
    }
  }
  const start = async () => {
    if (scope === 'section' && !sectionId) return toast.warning('Choose a section')
    setBusy(true)
    for (const it of items.filter((x) => x.status === 'queued' || x.status === 'error')) await one(it, 'ask')
    setBusy(false)
    onDone()
  }
  const resolve = async (it: Up, mode: string) => { await one(it, mode); onDone() }

  return (
    <Modal open onClose={onClose} size="lg" title="Upload files" icon={Upload}
      footer={<><Button variant="outline" onClick={onClose}>Close</Button><Button icon={Upload} loading={busy} disabled={!items.some((x) => x.status === 'queued' || x.status === 'error')} onClick={start}>Upload {items.filter((x) => x.status === 'queued').length || ''}</Button></>}>
      <div className="grid gap-4 md:grid-cols-2">
        <div className="space-y-3">
          <Field label="Destination folder"><Select value={folderId} onChange={(e) => setFolderId(Number(e.target.value))}>{folders.map((f) => <option key={f.id} value={f.id}>{f.name}</option>)}</Select></Field>
          <Field label="Description (optional)"><Textarea value={desc} onChange={(e) => setDesc(e.target.value)} className="min-h-[60px]" /></Field>
          <Field group label="Access permission"><AccessPicker scope={scope} setScope={setScope} sectionId={sectionId} setSectionId={setSectionId} userIds={userIds} setUserIds={setUserIds} /></Field>
        </div>
        <div>
          <div onClick={() => input.current?.click()} onDragOver={(e) => e.preventDefault()}
            onDrop={(e) => { e.preventDefault(); setItems((xs) => [...xs, ...Array.from(e.dataTransfer.files).map((f) => ({ key: Math.random().toString(36), file: f, progress: 0, status: 'queued' as const }))]) }}
            className="flex cursor-pointer flex-col items-center rounded-xl border-2 border-dashed border-ink-200 px-4 py-6 text-center hover:border-maroon-300 hover:bg-maroon-50/40">
            <Upload className="mb-2 h-6 w-6 text-maroon-600" /><div className="text-sm font-semibold">Drop files or click to browse</div><div className="text-xs text-ink-500">Single or multiple files</div>
            <input ref={input} type="file" multiple hidden onChange={(e) => { const fs = Array.from(e.target.files || []); setItems((xs) => [...xs, ...fs.map((f) => ({ key: Math.random().toString(36), file: f, progress: 0, status: 'queued' as const }))]); e.target.value = '' }} />
          </div>
          <ul className="mt-3 max-h-72 space-y-2 overflow-y-auto">
            {items.map((it) => (
              <li key={it.key} className="rounded-xl border border-ink-100 px-3 py-2">
                <div className="flex items-center gap-2">
                  <FileIcon ext={it.file.name.split('.').pop()} className="h-8 w-8" />
                  <div className="min-w-0 flex-1"><div className="truncate text-sm font-medium">{it.file.name}</div><div className="text-xs text-ink-500">{fmtSize(it.file.size)} · {it.status}</div></div>
                  {(it.status === 'queued' || it.status === 'error') && <IconButton icon={X} label="Remove" onClick={() => setItems((xs) => xs.filter((x) => x.key !== it.key))} />}
                </div>
                {it.status === 'uploading' && <Progress value={it.progress} className="mt-1.5 h-1.5" />}
                {it.msg && <div className={cx('mt-1 text-xs', it.status === 'error' ? 'text-red-600' : it.status === 'duplicate' ? 'text-amber-700' : 'text-ink-600')}>{it.msg}</div>}
                {it.status === 'duplicate' && (
                  <div className="mt-1.5 flex flex-wrap gap-1.5">
                    <Button size="sm" variant="secondary" onClick={() => resolve(it, 'version')}>Save as new version</Button>
                    <Button size="sm" variant="outline" onClick={() => resolve(it, 'rename')}>Keep both</Button>
                    <Button size="sm" variant="ghost" onClick={() => upd(it.key, { status: 'skipped', msg: 'Skipped' })}>Skip</Button>
                  </div>
                )}
              </li>
            ))}
          </ul>
        </div>
      </div>
    </Modal>
  )
}

function FileDetail({ id, onClose, onChanged }: { id: number; onClose: () => void; onChanged: () => void }) {
  const [f, setF] = useState<any>(null)
  const [tab, setTab] = useState<'details' | 'versions' | 'activity'>('details')
  const toast = useToast()
  const load = () => api.get(`/api/files/${id}`).then(setF).catch((e) => toast.error(e.message))
  useEffect(() => { load() }, [id])
  return (
    <Modal open onClose={onClose} size="lg" title={f?.name || 'File'} icon={History}
      footer={f && !f.deleted_at && <Button icon={Download} onClick={() => download(`/api/files/${id}/download`)}>Download</Button>}>
      {!f ? <Loading /> : (
        <div>
          <Tabs className="mb-4" value={tab} onChange={setTab} tabs={[{ value: 'details', label: 'Details' }, { value: 'versions', label: 'Versions', count: f.versions.length }, { value: 'activity', label: 'Activity log', count: f.activity.length }]} />
          {tab === 'details' && (
            <dl className="grid gap-3 text-sm sm:grid-cols-2">
              {[['File name', f.name], ['File type', f.extension.toUpperCase()], ['Size', fmtSize(f.size)], ['Uploaded by', f.uploaded_by_name], ['Upload date & time', fmtDateTime(f.created_at)], ['Last updated', fmtDateTime(f.updated_at)],
                ['Storage location', f.storage_location], ['Access permission', f.access_scope === 'specific' ? `Specific: ${f.allowed_users.map((u: any) => u.full_name).join(', ')}` : f.access_scope === 'section' ? 'Section only' : 'All users'],
                ['Current version', f.version], ['SHA-256', <span className="break-all font-mono text-xs">{f.sha256}</span>], ['Description', f.description || '—']].map(([k, v]: any) => (
                <div key={k} className="rounded-lg bg-ink-50 px-3 py-2"><dt className="text-xs text-ink-500">{k}</dt><dd className="font-medium">{v}</dd></div>
              ))}
            </dl>
          )}
          {tab === 'versions' && (
            <Table><thead><tr><Th>Version</Th><Th>Size</Th><Th>By</Th><Th>Date</Th><Th>Note</Th><Th></Th></tr></thead>
              <tbody>{f.versions.map((v: any) => (
                <tr key={v.version}>
                  <Td><b>v{v.version}</b> {v.current && <Badge tone="green">current</Badge>}</Td><Td className="text-xs">{fmtSize(v.size)}</Td><Td>{v.uploaded_by}</Td><Td className="text-xs">{fmtDateTime(v.created_at)}</Td><Td className="text-xs">{v.note}</Td>
                  <Td className="whitespace-nowrap text-right">
                    <IconButton icon={Download} label="Download version" onClick={() => download(`/api/files/${id}/download?version=${v.version}`)} />
                    {!v.current && f.can_modify && <IconButton icon={Undo2} label="Restore this version" onClick={async () => { await api.post(`/api/files/${id}/versions/${v.version}/restore`); toast.success(`Restored v${v.version} as a new version`); load(); onChanged() }} />}
                  </Td>
                </tr>))}</tbody></Table>
          )}
          {tab === 'activity' && (
            <ul className="divide-y divide-ink-100 text-sm">
              {f.activity.map((a: any, i: number) => (
                <li key={i} className="flex justify-between gap-3 py-2"><span><b className="capitalize">{a.action.replace('_', ' ')}</b> by {a.user} <span className="text-xs text-ink-500">({a.ip})</span></span><span className="whitespace-nowrap text-xs text-ink-500">{fmtDateTime(a.at)}</span></li>
              ))}
            </ul>
          )}
        </div>
      )}
    </Modal>
  )
}

function ShareDialog({ file, onClose, onDone }: { file: any; onClose: () => void; onDone: () => void }) {
  const [scope, setScope] = useState(file.access_scope)
  const [sectionId, setSectionId] = useState<number | null>(file.section_id)
  const [userIds, setUserIds] = useState<number[]>(file.allowed_user_ids)
  const [busy, setBusy] = useState(false)
  const toast = useToast()
  const save = async () => {
    setBusy(true)
    try { await api.patch(`/api/files/${file.id}`, { access_scope: scope, section_id: sectionId, user_ids: userIds }); toast.success('Access updated'); onDone() } catch (e: any) { toast.error(e.message) } finally { setBusy(false) }
  }
  return (
    <Modal open onClose={onClose} title={`Share “${file.name}”`} icon={Share2} footer={<><Button variant="outline" onClick={onClose}>Cancel</Button><Button loading={busy} onClick={save}>Save access</Button></>}>
      <AccessPicker scope={scope} setScope={setScope} sectionId={sectionId} setSectionId={setSectionId} userIds={userIds} setUserIds={setUserIds} />
      <p className="mt-3 text-xs text-ink-500">Newly added users get a notification and see the file under “Shared with Me”.</p>
    </Modal>
  )
}

function MoveCopyDialog({ file, mode, folders, onClose, onDone }: any) {
  const [target, setTarget] = useState<number>(folders.find((f: any) => f.id !== file.folder_id)?.id)
  const toast = useToast()
  const go = async () => {
    try { await api.post(`/api/files/${file.id}/${mode}`, { folder_id: target }); toast.success(mode === 'move' ? 'File moved' : 'File copied'); onDone() } catch (e: any) { toast.error(e.message) }
  }
  return (
    <Modal open onClose={onClose} size="sm" title={`${mode === 'move' ? 'Move' : 'Copy'} “${file.name}”`} icon={FolderInput} footer={<><Button variant="outline" onClick={onClose}>Cancel</Button><Button onClick={go}>{mode === 'move' ? 'Move' : 'Copy'}</Button></>}>
      <Field label="Target folder"><Select value={target} onChange={(e) => setTarget(Number(e.target.value))}>{folders.map((f: any) => <option key={f.id} value={f.id} disabled={mode === 'move' && f.id === file.folder_id}>{f.name}</option>)}</Select></Field>
    </Modal>
  )
}

function RenameDialog({ file, onClose, onDone }: any) {
  const [name, setName] = useState(file.name.replace(new RegExp(`\\.${file.extension}$`, 'i'), ''))
  const [desc, setDesc] = useState(file.description)
  const toast = useToast()
  const go = async () => { try { await api.patch(`/api/files/${file.id}`, { name, description: desc }); toast.success('Saved'); onDone() } catch (e: any) { toast.error(e.message) } }
  return (
    <Modal open onClose={onClose} size="sm" title="Rename file" icon={Edit3} footer={<><Button variant="outline" onClick={onClose}>Cancel</Button><Button onClick={go}>Save</Button></>}>
      <div className="space-y-3">
        <Field label="File name" hint={`The .${file.extension} extension is kept`}><Input value={name} onChange={(e) => setName(e.target.value)} autoFocus /></Field>
        <Field label="Description"><Textarea value={desc} onChange={(e) => setDesc(e.target.value)} /></Field>
      </div>
    </Modal>
  )
}

function NewFolderDialog({ onClose, onDone, folder }: any) {
  const [name, setName] = useState(folder?.name || '')
  const toast = useToast()
  const go = async () => {
    try {
      if (folder) { await api.patch(`/api/files/folders/${folder.id}`, { name }); toast.success('Folder renamed') }
      else { await api.post('/api/files/folders', { name }); toast.success('Folder created') }
      onDone(name)
    } catch (e: any) { toast.error(e.message) }
  }
  return (
    <Modal open onClose={onClose} size="sm" title={folder ? 'Rename folder' : 'Create folder'} icon={FolderPlus} footer={<><Button variant="outline" onClick={onClose}>Cancel</Button><Button onClick={go} disabled={!name.trim()}>{folder ? 'Rename' : 'Create'}</Button></>}>
      <Field label="Folder name"><Input value={name} onChange={(e) => setName(e.target.value)} autoFocus onKeyDown={(e) => e.key === 'Enter' && name.trim() && go()} /></Field>
    </Modal>
  )
}
