import { ReactNode, useEffect, useRef, useState } from 'react'
import { NavLink, useLocation, useNavigate } from 'react-router-dom'
import {
  Bell, CheckCheck, ChevronDown, FolderArchive, History, Inbox, KeyRound, LayoutDashboard, LogOut, Menu, MonitorSmartphone,
  Send, Settings, Trash2, UserCircle2, Users, Monitor, Network, LayoutTemplate,
} from 'lucide-react'
import { api } from '../lib/api'
import { Perm, useAuth } from '../lib/auth'
import { requestDesktopPermission, useRealtime } from '../lib/realtime'
import { timeAgo } from '../lib/format'
import { useToast } from '../lib/toast'
import { Button, cx, Field, Input, Modal } from './ui'

const NAV_TONE: Record<string, string> = {
  '/dashboard': 'from-sky-400 to-blue-600', '/send': 'from-rose-400 to-pink-600', '/receive': 'from-emerald-400 to-teal-600',
  '/history': 'from-violet-400 to-purple-600', '/devices': 'from-cyan-400 to-sky-600', '/users': 'from-amber-400 to-orange-600',
  '/files': 'from-yellow-300 to-amber-500', '/settings': 'from-slate-400 to-slate-600',
}

export const NAV: { to: string; label: string; icon: any; perm: Perm }[] = [
  { to: '/dashboard', label: 'Dashboard', icon: LayoutDashboard, perm: 'dashboard' },
  { to: '/send', label: 'Send Data', icon: Send, perm: 'send' },
  { to: '/receive', label: 'Receive Data', icon: Inbox, perm: 'receive' },
  { to: '/history', label: 'Transfer History', icon: History, perm: 'history' },
  { to: '/devices', label: 'Connected Devices', icon: MonitorSmartphone, perm: 'devices' },
  { to: '/users', label: 'User Management', icon: Users, perm: 'users' },
  { to: '/files', label: 'File Depository', icon: FolderArchive, perm: 'files' },
  { to: '/settings', label: 'Settings', icon: Settings, perm: 'settings' },
]

export function Logo({ size = 40, src, onDark }: { size?: number; src?: string; onDark?: boolean }) {
  if (src) return <img src={src} alt="Logo" style={{ width: size, height: size }} className="rounded-xl object-contain" />
  const fg = onDark ? 'rgb(var(--brand-800))' : '#fff'
  return (
    <svg width={size} height={size} viewBox="0 0 64 64" aria-label="OFFLINE SHARE logo">
      <defs><linearGradient id="lg" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stopColor="rgb(var(--brand-600))" /><stop offset="1" stopColor="rgb(var(--brand-900))" /></linearGradient></defs>
      <rect width="64" height="64" rx="16" fill={onDark ? '#fff' : 'url(#lg)'} />
      <path d="M18 27a14 14 0 0 1 28 0" stroke={fg} strokeOpacity=".55" strokeWidth="3.5" fill="none" strokeLinecap="round" />
      <path d="M23.5 30a8.5 8.5 0 0 1 17 0" stroke={fg} strokeOpacity=".8" strokeWidth="3.5" fill="none" strokeLinecap="round" />
      <path d="M32 30v17m0 0-6-6m6 6 6-6" stroke={fg} strokeWidth="3.8" fill="none" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  )
}

export type LayoutStyle = 'classic' | 'modern' | 'compact'
export const LAYOUTS: LayoutStyle[] = ['classic', 'modern', 'compact']
const LAYOUT_KEY = 'os_layout'

/** Personal override stored on this PC (falls back to the organisation default from Settings). */
export function getPersonalLayout(): LayoutStyle | '' {
  try { const v = localStorage.getItem(LAYOUT_KEY) || ''; return (LAYOUTS as string[]).includes(v) ? v as LayoutStyle : '' } catch { return '' }
}
export function setPersonalLayout(v: LayoutStyle | '') {
  try { v ? localStorage.setItem(LAYOUT_KEY, v) : localStorage.removeItem(LAYOUT_KEY) } catch { /* storage unavailable */ }
  window.dispatchEvent(new Event('os-layout'))
}
export function applyLayout(v?: string) {
  document.documentElement.dataset.layout = (LAYOUTS as string[]).includes(v || '') ? v : 'classic'
}

export default function Layout({ children }: { children: ReactNode }) {
  const { session, can } = useAuth()
  const [mobileOpen, setMobileOpen] = useState(false)
  const [logoutOpen, setLogoutOpen] = useState(false)
  const [pwdOpen, setPwdOpen] = useState(false)
  const [personal, setPersonal] = useState(getPersonalLayout())
  const [preview, setPreview] = useState<string>('')
  const loc = useLocation()
  useEffect(() => setMobileOpen(false), [loc.pathname])
  useEffect(() => { requestDesktopPermission() }, [])
  useEffect(() => {
    const on = () => setPersonal(getPersonalLayout())
    const pv = (e: Event) => setPreview((e as CustomEvent).detail || '')
    window.addEventListener('os-layout', on); window.addEventListener('os-layout-preview', pv)
    return () => { window.removeEventListener('os-layout', on); window.removeEventListener('os-layout-preview', pv) }
  }, [])
  const orgLayout = session?.branding.layout_style
  const layout: LayoutStyle = (preview || personal || ((LAYOUTS as string[]).includes(orgLayout || '') ? orgLayout : 'classic')) as LayoutStyle
  useEffect(() => { applyLayout(layout) }, [layout])
  if (!session) return null
  const b = session.branding
  const items = NAV.filter((n) => can(n.perm))
  const dark = layout !== 'modern'
  const compact = layout === 'compact'

  const sidebar = (
    <aside className={cx('sb relative flex h-full flex-col overflow-hidden transition-all duration-300',
      compact ? 'w-[78px]' : 'w-[240px]',
      dark ? 'bg-gradient-to-b from-maroon-800 via-maroon-900 to-maroon-950 text-white'
        : 'm-3 mr-0 h-[calc(100%-1.5rem)] rounded-3xl border border-ink-100 bg-white text-ink-900 shadow-[0_8px_30px_rgba(51,15,25,.08)]')}>
      {dark && (
        <div aria-hidden className="pointer-events-none absolute inset-0 overflow-hidden">
          <span className="sb-blob left-[-60px] top-[-40px] h-48 w-48 bg-rose-400/30" />
          <span className="sb-blob sb-blob-2 right-[-70px] top-[38%] h-52 w-52 bg-amber-300/15" />
          <span className="sb-blob sb-blob-3 bottom-[-50px] left-[10%] h-44 w-44 bg-fuchsia-400/20" />
        </div>
      )}
      {!dark && <div aria-hidden className="pointer-events-none absolute -right-16 -top-16 h-44 w-44 rounded-full bg-maroon-100/70 blur-2xl" />}
      <nav className={cx('relative flex-1 space-y-1.5 overflow-y-auto py-4', compact ? 'px-2.5' : 'px-3')}>
        {items.map((n, i) => (
          <NavLink key={n.to} to={n.to} style={{ animationDelay: `${i * 45}ms` }} title={compact ? n.label : undefined} aria-label={n.label}
            className={({ isActive }) => cx('sb-item group relative flex items-center rounded-2xl text-[15px] font-medium transition-all duration-300',
              compact ? 'justify-center p-1.5' : 'gap-3 py-2 pl-2 pr-3',
              dark ? (isActive ? 'sb-active bg-white/[.16] text-white shadow-lg shadow-black/20 ring-1 ring-white/25 backdrop-blur' : 'text-white/90 hover:bg-white/[.08]')
                : (isActive ? 'bg-maroon-50 font-semibold text-maroon-800 ring-1 ring-maroon-100' : 'text-ink-700 hover:bg-ink-50'),
              !compact && !isActive && 'hover:translate-x-1')}>
            {({ isActive }) => (<>
              {isActive && <span className={cx('sb-bar absolute top-1/2 h-7 w-1.5 -translate-y-1/2 rounded-r-full bg-gradient-to-b from-amber-300 to-rose-400', compact ? '-left-2.5' : '-left-3')} />}
              <span className={cx('flex shrink-0 items-center justify-center rounded-xl bg-gradient-to-br shadow-md transition-transform duration-300 group-hover:-rotate-6 group-hover:scale-110',
                compact ? 'h-11 w-11' : 'h-9 w-9', NAV_TONE[n.to] || 'from-white/30 to-white/10', isActive && dark && 'sb-glow scale-105')}>
                <n.icon className={cx('text-white drop-shadow', compact ? 'h-[21px] w-[21px]' : 'h-[19px] w-[19px]')} strokeWidth={2} />
              </span>
              {!compact && <span className="truncate">{n.label}</span>}
              {n.to === '/receive' && <UnreadPill floating={compact} />}
              {isActive && !compact && n.to !== '/receive' && <span className={cx('ml-auto h-2 w-2 rounded-full', dark ? 'bg-amber-300 shadow-[0_0_8px_2px_rgba(252,211,77,.7)]' : 'bg-maroon-600')} />}
            </>)}
          </NavLink>
        ))}
        <div className={cx('!my-3 mx-2 h-px bg-gradient-to-r from-transparent to-transparent', dark ? 'via-white/25' : 'via-ink-200')} />
        <button onClick={() => setLogoutOpen(true)} style={{ animationDelay: `${items.length * 45}ms` }} title={compact ? 'Logout' : undefined} aria-label="Logout"
          className={cx('sb-item group flex w-full items-center rounded-2xl text-[15px] font-medium transition-all duration-300',
            compact ? 'justify-center p-1.5' : 'gap-3 py-2 pl-2 pr-3 hover:translate-x-1', dark ? 'text-white/90 hover:bg-red-500/20' : 'text-ink-700 hover:bg-red-50')}>
          <span className={cx('flex items-center justify-center rounded-xl bg-gradient-to-br from-red-400 to-red-600 text-white shadow-md transition-transform duration-300 group-hover:-rotate-6 group-hover:scale-110', compact ? 'h-11 w-11' : 'h-9 w-9')}>
            <LogOut className="h-[19px] w-[19px]" strokeWidth={2} />
          </span>
          {!compact && 'Logout'}
        </button>
      </nav>
      {compact ? (
        <div className="relative flex flex-col items-center gap-1 pb-4 text-[10px] font-semibold">
          <span className="relative flex h-2.5 w-2.5" title="LAN Secure"><span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-emerald-400 opacity-70" /><span className="relative inline-flex h-2.5 w-2.5 rounded-full bg-emerald-400" /></span>
          <span className={dark ? 'text-white/70' : 'text-ink-500'}>v{session.version}</span>
        </div>
      ) : (
        <div className="relative px-3 pb-4 pt-12">
          <svg aria-hidden className="sb-waves absolute inset-x-0 top-0 h-20 w-[200%]" viewBox="0 0 480 80" preserveAspectRatio="none">
            {[0, 9, 18, 27].map((o, i) => <path key={o} d={`M0 ${55 - o} C 60 ${20 - o}, 120 ${85 - o}, 240 ${45 - o} S 420 ${10 - o}, 480 ${55 - o}`} stroke={['#fda4af', '#fcd34d', '#f0abfc', dark ? '#ffffff' : '#c9c1c4'][i]} strokeOpacity={dark ? '.35' : '.6'} fill="none" strokeWidth="1.2" />)}
          </svg>
          <div className={cx('relative rounded-2xl p-3 text-center', dark ? 'bg-white/10 ring-1 ring-white/15 backdrop-blur-md' : 'bg-gradient-to-br from-maroon-50 to-white ring-1 ring-maroon-100')}>
            <div className={cx('flex items-center justify-center gap-1.5 text-[11px] font-semibold uppercase tracking-wider', dark ? 'text-emerald-300' : 'text-emerald-600')}>
              <span className="relative flex h-2 w-2"><span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-emerald-400 opacity-70" /><span className="relative inline-flex h-2 w-2 rounded-full bg-emerald-400" /></span>
              LAN Secure
            </div>
            <div className={cx('mt-1 bg-clip-text text-[15px] font-extrabold tracking-wide text-transparent', dark ? 'bg-gradient-to-r from-amber-200 via-white to-rose-200' : 'bg-gradient-to-r from-maroon-700 via-rose-600 to-amber-600')}>{b.app_name || 'OFFLINE SHARE'}</div>
            <div className={cx('text-xs', dark ? 'text-white/70' : 'text-ink-500')}>v{session.version}</div>
            {b.organisation_name && <div className={cx('mt-1 truncate text-xs font-semibold', dark ? 'text-white/90' : 'text-ink-800')} title={b.organisation_name}>{b.organisation_name}</div>}
            {b.organisation_slogan && <div className={cx('truncate text-[11px] italic', dark ? 'text-white/60' : 'text-ink-500')} title={b.organisation_slogan}>“{b.organisation_slogan}”</div>}
          </div>
        </div>
      )}
    </aside>
  )

  return (
    <div className={cx('flex h-screen flex-col overflow-hidden', dark ? 'bg-[#f7f4f5]' : 'bg-gradient-to-br from-[#fbf7f8] via-[#f6f3f8] to-[#f3f6fb]')}>
      <Header layout={layout} onMenu={() => setMobileOpen(true)} onLogout={() => setLogoutOpen(true)} onPassword={() => setPwdOpen(true)} />
      <div className="flex min-h-0 flex-1">
        <div className="hidden shrink-0 lg:block print:hidden">{sidebar}</div>
        {mobileOpen && (
          <div className="fixed inset-0 z-40 flex lg:hidden print:hidden">
            <div className="h-full bg-white">{sidebar}</div>
            <div className="flex-1 bg-black/30" onClick={() => setMobileOpen(false)} />
          </div>
        )}
        <main className={cx('min-w-0 flex-1 overflow-y-auto print:overflow-visible print:p-0', compact ? 'px-3 py-3' : layout === 'modern' ? 'px-5 py-5' : 'px-4 py-4 sm:px-5')}>
          <div className="mx-auto max-w-[1700px]">{children}</div>
        </main>
      </div>
      <LogoutDialog open={logoutOpen} onClose={() => setLogoutOpen(false)} />
      <ChangePasswordDialog open={pwdOpen || session.user.must_change_password} forced={session.user.must_change_password} onClose={() => setPwdOpen(false)} />
    </div>
  )
}

function UnreadPill({ floating }: { floating?: boolean }) {
  const { unread, setUnread } = useRealtime()
  const loc = useLocation()
  useEffect(() => { api.get('/api/inbox/unread/count').then((r) => setUnread(r.unread)).catch(() => {}) }, [loc.pathname])
  if (!unread) return null
  return <span className={cx('flex h-6 min-w-6 items-center justify-center rounded-full bg-red-600 px-1.5 text-[12px] font-bold text-white ring-2 ring-white/40',
    floating ? 'absolute -right-1 -top-1 h-5 min-w-5 text-[10.5px]' : 'ml-auto')}>{unread > 99 ? '99+' : unread}</span>
}

const LAYOUT_LABEL: Record<string, string> = { classic: 'Classic', modern: 'Modern', compact: 'Compact' }

function Header({ layout, onMenu, onLogout, onPassword }: { layout: LayoutStyle; onMenu: () => void; onLogout: () => void; onPassword: () => void }) {
  const { session } = useAuth()
  const { connected } = useRealtime()
  const [menu, setMenu] = useState(false)
  const s = session!
  const b = s.branding
  const dark = layout !== 'modern'
  const compact = layout === 'compact'
  const personal = getPersonalLayout()
  const chip = dark ? 'border-2 border-white/70' : 'border border-ink-200 bg-white text-ink-800 shadow-sm'
  return (
    <header className={cx('relative z-20 flex shrink-0 items-center gap-3 pr-4 print:hidden', compact ? 'h-[60px]' : 'h-[76px]',
      dark ? 'bg-gradient-to-r from-maroon-900 via-maroon-800 to-maroon-900 text-white shadow-md' : 'border-b border-ink-100 bg-white/90 text-ink-900 backdrop-blur')}>
      <button className={cx('ml-2 rounded-lg p-2 lg:hidden', dark ? 'hover:bg-white/10' : 'hover:bg-ink-100')} onClick={onMenu} aria-label="Menu"><Menu className="h-6 w-6" /></button>
      <div className={cx('hidden h-full shrink-0 items-center justify-center lg:flex', compact ? 'w-[78px]' : 'w-[240px]')}>
        <Logo src={b.logo_data_url} size={compact ? 42 : 56} onDark={dark} />
      </div>
      <div className={cx('min-w-0 border-r pr-6', dark ? 'border-white/20' : 'border-ink-200')}>
        <div className={cx('truncate font-extrabold leading-none tracking-wide', compact ? 'text-[22px]' : 'text-[28px]', !dark && 'bg-gradient-to-r from-maroon-800 via-maroon-600 to-rose-600 bg-clip-text text-transparent')}>{b.app_name || 'OFFLINE SHARE'}</div>
        {!compact && <div className={cx('mt-1 truncate text-[16px]', dark ? 'text-white/90' : 'text-ink-600')}>{b.app_subtitle || 'Local Data Transfer System (LAN)'}</div>}
      </div>
      {(b.organisation_name || b.organisation_slogan) && (
        <div className="hidden min-w-0 max-w-[340px] pl-1 2xl:block" title={[b.organisation_name, b.organisation_slogan].filter(Boolean).join(' — ')}>
          {b.organisation_name && <div className={cx('truncate font-bold leading-tight', compact ? 'text-[16px]' : 'text-[19px]')}>{b.organisation_name}</div>}
          {b.organisation_slogan && <div className={cx('mt-0.5 truncate text-[12.5px] italic tracking-wide', dark ? 'text-amber-100/90' : 'text-maroon-600')}>“{b.organisation_slogan}”</div>}
        </div>
      )}
      <div className="ml-auto flex items-center gap-3">
        <span className={cx('hidden items-center gap-2 rounded-xl px-4 font-semibold xl:inline-flex', chip, compact ? 'py-1 text-[14px]' : 'py-2 text-[16px]')}>
          <Network className={cx('text-emerald-500', compact ? 'h-5 w-5' : 'h-6 w-6')} /> LAN Only <span className="font-normal">(No Internet)</span>
        </span>
        <span className={cx('hidden items-center gap-3 rounded-xl pl-4 pr-1.5 md:inline-flex', chip, compact ? 'py-1 text-[14px]' : 'py-1.5 text-[16px]')}>
          <Monitor className="h-5 w-5" /> Server : {s.server_ip}
          <span className={cx('inline-flex items-center gap-1.5 rounded-lg px-3 py-1 text-[15px] font-semibold text-white', connected ? 'bg-emerald-600' : 'bg-red-600')}>
            <span className={cx('h-3 w-3 rounded-full', connected ? 'bg-emerald-300' : 'animate-pulse bg-red-300')} />{connected ? 'Online' : 'Offline'}
          </span>
        </span>
        <Notifications dark={dark} />
        <div className="relative">
          <button onClick={() => setMenu((m) => !m)} className={cx('flex items-center gap-2.5 rounded-xl py-1 pl-1 pr-2', dark ? 'hover:bg-white/10' : 'hover:bg-ink-50')} title={s.device ? `This PC: ${s.device.pc_name} (${s.client_ip})` : s.client_ip}>
            <span className={cx('flex items-center justify-center rounded-full font-bold', compact ? 'h-10 w-10 text-base' : 'h-12 w-12 text-lg', dark ? 'bg-white text-maroon-800' : 'bg-gradient-to-br from-maroon-500 to-maroon-800 text-white')}>{s.user.full_name.split(/\s+/).slice(0, 2).map((p) => p[0]).join('').toUpperCase()}</span>
            <div className="hidden text-left sm:block">
              <div className="max-w-[170px] truncate text-[16px] font-semibold leading-tight">{s.user.full_name}</div>
              <div className={cx('text-[14px]', dark ? 'text-white/85' : 'text-ink-500')}>{s.user.role === 'super_admin' || s.user.role === 'admin' ? 'Admin' : s.user.role_name}</div>
            </div>
            <ChevronDown className="h-5 w-5" />
          </button>
          {menu && (
            <>
              <div className="fixed inset-0 z-30" onClick={() => setMenu(false)} />
              <div className="absolute right-0 z-40 mt-2 w-72 rounded-xl border border-ink-100 bg-white p-2 text-ink-900 shadow-pop">
                <div className="border-b border-ink-100 px-3 pb-2.5 pt-1.5">
                  <div className="text-sm font-semibold">{s.user.full_name}</div>
                  <div className="text-xs text-ink-500">{s.user.login_id} · {s.user.role_name}</div>
                  {s.device && <div className="text-xs text-ink-500">This PC: {s.device.pc_name} ({s.client_ip})</div>}
                </div>
                <div className="border-b border-ink-100 px-3 py-2.5">
                  <div className="mb-1.5 flex items-center gap-1.5 text-xs font-bold uppercase tracking-wide text-ink-500"><LayoutTemplate className="h-3.5 w-3.5" />My page design</div>
                  <div className="grid grid-cols-2 gap-1.5">
                    {(['', ...LAYOUTS] as const).map((v) => (
                      <button key={v || 'default'} onClick={() => setPersonalLayout(v)}
                        className={cx('rounded-lg border px-2 py-1.5 text-xs font-semibold transition', personal === v ? 'border-maroon-600 bg-maroon-50 text-maroon-800' : 'border-ink-200 hover:border-maroon-300')}>
                        {v ? LAYOUT_LABEL[v] : `Office default (${LAYOUT_LABEL[b.layout_style] || 'Classic'})`}
                      </button>
                    ))}
                  </div>
                  <div className="mt-1 text-[11px] text-ink-500">Saved on this PC only.</div>
                </div>
                <button onClick={() => { setMenu(false); onPassword() }} className="mt-1 flex w-full items-center gap-2 rounded-lg px-3 py-2 text-sm hover:bg-ink-50"><KeyRound className="h-4 w-4" /> Change password</button>
                <button onClick={() => { setMenu(false); onLogout() }} className="flex w-full items-center gap-2 rounded-lg px-3 py-2 text-sm text-red-600 hover:bg-red-50"><LogOut className="h-4 w-4" /> Logout</button>
              </div>
            </>
          )}
        </div>
      </div>
    </header>
  )
}

interface Note { id: number; type: string; title: string; body: string; link: string; is_read: boolean; created_at: string }

function Notifications({ dark = true }: { dark?: boolean }) {
  const { notifTick, unread: inboxNew } = useRealtime()
  const [open, setOpen] = useState(false)
  const [items, setItems] = useState<Note[]>([])
  const [unread, setUnread] = useState(0)
  const nav = useNavigate()
  const ref = useRef<HTMLDivElement>(null)
  const load = () => api.get('/api/notifications').then((d) => { setItems(d.items); setUnread(d.unread) }).catch(() => {})
  useEffect(() => { load() }, [notifTick, inboxNew])
  const markAll = async () => { await api.post('/api/notifications/read', { all: true }); load() }
  const clear = async () => { await api.post('/api/notifications/clear'); load() }
  return (
    <div className="relative" ref={ref}>
      <button onClick={() => { setOpen((o) => !o); if (!open) load() }} className={cx('relative rounded-xl p-2.5', dark ? 'text-white hover:bg-white/10' : 'text-ink-700 hover:bg-ink-50')} aria-label="Notifications">
        <Bell className="h-7 w-7" strokeWidth={1.8} />
        {unread > 0 && <span className="absolute right-0.5 top-0.5 flex h-5 min-w-5 items-center justify-center rounded-full bg-red-600 px-1 text-[11px] font-bold text-white ring-2 ring-white">{unread > 9 ? '9+' : unread}</span>}
      </button>
      {open && (
        <>
          <div className="fixed inset-0 z-30" onClick={() => setOpen(false)} />
          <div className="absolute right-0 z-40 mt-2 w-[360px] max-w-[calc(100vw-2rem)] rounded-xl border border-ink-100 bg-white text-ink-900 shadow-pop">
            <div className="flex items-center justify-between border-b border-ink-100 px-4 py-3">
              <span className="font-semibold">Notifications</span>
              <div className="flex gap-1">
                <button onClick={markAll} className="rounded-lg p-1.5 text-ink-500 hover:bg-ink-50" title="Mark all read"><CheckCheck className="h-4 w-4" /></button>
                <button onClick={clear} className="rounded-lg p-1.5 text-ink-500 hover:bg-ink-50" title="Clear all"><Trash2 className="h-4 w-4" /></button>
              </div>
            </div>
            <div className="max-h-[400px] overflow-y-auto">
              {items.length === 0 && <div className="px-4 py-10 text-center text-sm text-ink-500">You're all caught up</div>}
              {items.map((n) => (
                <button key={n.id} onClick={async () => {
                  setOpen(false)
                  if (!n.is_read) await api.post('/api/notifications/read', { ids: [n.id] })
                  load()
                  if (n.link) nav(n.link)
                }} className={cx('flex w-full gap-3 border-b border-ink-50 px-4 py-3 text-left hover:bg-maroon-50/40', !n.is_read && 'bg-maroon-50/60')}>
                  <span className={cx('mt-1.5 h-2 w-2 shrink-0 rounded-full', n.is_read ? 'bg-transparent' : n.type === 'failed' ? 'bg-red-500' : 'bg-maroon-600')} />
                  <span className="min-w-0">
                    <span className="block text-sm font-medium text-ink-900">{n.title}</span>
                    {n.body && <span className="block truncate text-xs text-ink-600">{n.body}</span>}
                    <span className="block text-[11px] text-ink-400">{timeAgo(n.created_at)}</span>
                  </span>
                </button>
              ))}
            </div>
          </div>
        </>
      )}
    </div>
  )
}

function LogoutDialog({ open, onClose }: { open: boolean; onClose: () => void }) {
  const { logout, session } = useAuth()
  const [busy, setBusy] = useState(false)
  const nav = useNavigate()
  return (
    <Modal open={open} onClose={onClose} size="sm" title="Logout" icon={LogOut}
      footer={<>
        <Button variant="outline" onClick={onClose}>Cancel</Button>
        <Button variant="primary" icon={LogOut} loading={busy} onClick={async () => {
          setBusy(true)
          try { await logout() } finally { setBusy(false); onClose(); nav('/login') }
        }}>Yes, Logout</Button>
      </>}>
      <div className="flex items-center gap-3">
        <UserCircle2 className="h-10 w-10 text-maroon-300" />
        <p className="text-sm text-ink-700">
          Are you sure you want to log out, <b>{session?.user.full_name}</b>? Your session on this PC will end.
          The OFFLINE SHARE server keeps running for everyone else, and messages sent to you will be queued until you sign in again.
        </p>
      </div>
    </Modal>
  )
}

export function ChangePasswordDialog({ open, forced, onClose }: { open: boolean; forced?: boolean; onClose: () => void }) {
  const { refresh } = useAuth()
  const toast = useToast()
  const [cur, setCur] = useState('')
  const [nw, setNw] = useState('')
  const [rep, setRep] = useState('')
  const [err, setErr] = useState('')
  const [busy, setBusy] = useState(false)
  const submit = async () => {
    setErr('')
    if (nw !== rep) return setErr('New passwords do not match')
    setBusy(true)
    try {
      await api.post('/api/auth/change-password', { current_password: cur, new_password: nw })
      toast.success('Password changed')
      setCur(''); setNw(''); setRep('')
      await refresh()
      onClose()
    } catch (e: any) { setErr(e.message) } finally { setBusy(false) }
  }
  return (
    <Modal open={open} onClose={onClose} dismissible={!forced} size="sm" icon={KeyRound}
      title={forced ? 'Set a new password' : 'Change password'}
      subtitle={forced ? 'For security, choose your own password before continuing.' : undefined}
      footer={<>{!forced && <Button variant="outline" onClick={onClose}>Cancel</Button>}<Button loading={busy} onClick={submit}>Save password</Button></>}>
      <div className="space-y-3">
        <Field label="Current password"><Input type="password" value={cur} onChange={(e) => setCur(e.target.value)} autoComplete="current-password" /></Field>
        <Field label="New password" hint="At least 8 characters with upper- and lowercase letters and a digit (as set by your administrator)."><Input type="password" value={nw} onChange={(e) => setNw(e.target.value)} autoComplete="new-password" /></Field>
        <Field label="Repeat new password"><Input type="password" value={rep} onChange={(e) => setRep(e.target.value)} autoComplete="new-password" onKeyDown={(e) => e.key === 'Enter' && submit()} /></Field>
        {err && <div className="rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700">{err}</div>}
      </div>
    </Modal>
  )
}
