import { FormEvent, KeyboardEvent, useEffect, useState } from 'react'
import { Navigate, useLocation, useNavigate } from 'react-router-dom'
import {
  AlertTriangle, ArrowRight, CloudOff, Eye, EyeOff, Gauge, IndianRupee, KeyRound, Lock, PlugZap, Quote, Server, ShieldCheck,
  User, Users, WifiOff, ClipboardCheck, Monitor,
} from 'lucide-react'
import { api } from '../lib/api'
import { applyTheme, useAuth } from '../lib/auth'
import { Logo } from '../components/Layout'
import { cx } from '../components/ui'

// Why working offline is better – shown as a rotating quote carousel.
const QUOTES = [
  { icon: ShieldCheck, tone: 'from-emerald-400 to-teal-600', title: 'Data Security', text: 'Your files never leave the building — security begins where the internet ends.' },
  { icon: PlugZap, tone: 'from-amber-400 to-orange-600', title: 'Always Available', text: 'No internet, no problem. Office work keeps moving even when the outside network goes down.' },
  { icon: Gauge, tone: 'from-sky-400 to-blue-600', title: 'LAN Speed', text: 'Local network speed beats any cloud — large files cross the office in seconds, not minutes.' },
  { icon: IndianRupee, tone: 'from-fuchsia-400 to-purple-600', title: 'Zero Cloud Cost', text: 'No subscriptions, no data packs, no upload limits — share as much as your network can carry.' },
  { icon: ClipboardCheck, tone: 'from-rose-400 to-pink-600', title: 'Full Accountability', text: 'Every transfer is logged and every delivery confirmed — complete audit trail, built in.' },
  { icon: Lock, tone: 'from-lime-400 to-green-600', title: 'Your Control', text: 'Sensitive documents stay on your own server, under your own administrator — nobody else.' },
]

const CHIPS = [
  { icon: WifiOff, label: 'No Internet Needed', c: 'bg-emerald-400/20 text-emerald-100 ring-emerald-300/30' },
  { icon: CloudOff, label: 'No Cloud', c: 'bg-sky-400/20 text-sky-100 ring-sky-300/30' },
  { icon: ShieldCheck, label: 'Encrypted Passwords', c: 'bg-amber-400/20 text-amber-100 ring-amber-300/30' },
  { icon: Users, label: 'Role-based Access', c: 'bg-fuchsia-400/20 text-fuchsia-100 ring-fuchsia-300/30' },
]

export default function Login() {
  const { session, login, loading } = useAuth()
  const [loginId, setLoginId] = useState('')
  const [password, setPassword] = useState('')
  const [show, setShow] = useState(false)
  const [caps, setCaps] = useState(false)
  const [err, setErr] = useState('')
  const [busy, setBusy] = useState(false)
  const [cfg, setCfg] = useState<any>(null)
  const [q, setQ] = useState(0)
  const nav = useNavigate()
  const loc = useLocation() as any

  useEffect(() => { api.get('/api/auth/config').then((c) => { setCfg(c); applyTheme(c.branding?.theme) }).catch(() => setCfg(false)) }, [])
  useEffect(() => { const t = setInterval(() => setQ((x) => (x + 1) % QUOTES.length), 5500); return () => clearInterval(t) }, [])
  if (!loading && session) return <Navigate to={loc.state?.from || '/'} replace />

  const submit = async (e: FormEvent) => {
    e.preventDefault()
    setErr('')
    setBusy(true)
    try {
      await login(loginId.trim(), password)
      nav(loc.state?.from || '/', { replace: true })
    } catch (e: any) {
      setErr(e.message)
    } finally {
      setBusy(false)
    }
  }
  const capsCheck = (e: KeyboardEvent<HTMLInputElement>) => setCaps(e.getModifierState?.('CapsLock') ?? false)
  const b = cfg?.branding
  const quote = QUOTES[q]
  const hour = new Date().getHours()
  const greet = hour < 12 ? 'Good morning' : hour < 17 ? 'Good afternoon' : 'Good evening'

  return (
    <div className="lg-bg relative flex min-h-screen overflow-hidden text-white">
      {/* animated colourful backdrop */}
      <div aria-hidden className="pointer-events-none absolute inset-0">
        <span className="lg-blob left-[-8%] top-[-12%] h-[34rem] w-[34rem] bg-rose-500/40" />
        <span className="lg-blob lg-b2 right-[-10%] top-[10%] h-[30rem] w-[30rem] bg-amber-400/25" />
        <span className="lg-blob lg-b3 bottom-[-15%] left-[30%] h-[32rem] w-[32rem] bg-fuchsia-500/30" />
        <span className="lg-blob lg-b4 bottom-[-10%] right-[5%] h-[24rem] w-[24rem] bg-sky-400/20" />
        <div className="hero-dots absolute inset-0 opacity-60" />
        <svg className="lg-net absolute inset-0 h-full w-full opacity-[0.12]" aria-hidden>
          {Array.from({ length: 14 }).map((_, i) => <circle key={i} cx={`${(i * 37) % 100}%`} cy={`${(i * 53) % 100}%`} r="3" fill="#fff" />)}
          {Array.from({ length: 13 }).map((_, i) => <line key={i} x1={`${(i * 37) % 100}%`} y1={`${(i * 53) % 100}%`} x2={`${((i + 1) * 37) % 100}%`} y2={`${((i + 1) * 53) % 100}%`} stroke="#fff" strokeWidth="1" strokeDasharray="4 6" />)}
        </svg>
      </div>

      {/* ------------------------------------------------------------ left: brand + benefits */}
      <section className="relative hidden w-[54%] flex-col justify-between p-10 lg:flex xl:p-14">
        <div className="lg-rise flex items-center gap-4">
          <div className="rounded-2xl bg-white/10 p-1.5 ring-1 ring-white/20 backdrop-blur"><Logo size={60} src={b?.logo_data_url} onDark /></div>
          <div className="min-w-0">
            <div className="text-[30px] font-extrabold leading-none tracking-wide">{b?.app_name || 'OFFLINE SHARE'}</div>
            <div className="mt-1 text-[15px] text-white/80">{b?.app_subtitle || 'Local Data Transfer System (LAN)'}</div>
          </div>
          {b?.organisation_name && (
            <div className="ml-6 min-w-0 border-l border-white/25 pl-6">
              <div className="truncate text-lg font-bold">{b.organisation_name}</div>
              {b.organisation_slogan && <div className="truncate text-sm italic text-amber-100/90">“{b.organisation_slogan}”</div>}
            </div>
          )}
        </div>

        <div className="max-w-2xl">
          <h1 className="lg-rise text-[44px] font-extrabold leading-[1.1] tracking-tight" style={{ animationDelay: '.1s' }}>
            Share messages &amp; files<br />across the office —<br />
            <span className="lg-shimmer bg-gradient-to-r from-amber-200 via-rose-200 to-fuchsia-200 bg-clip-text text-transparent">without the internet.</span>
          </h1>
          <div className="lg-rise mt-6 flex flex-wrap gap-2" style={{ animationDelay: '.2s' }}>
            {CHIPS.map((c) => <span key={c.label} className={cx('inline-flex items-center gap-1.5 rounded-full px-3 py-1.5 text-[13px] font-semibold ring-1 backdrop-blur', c.c)}><c.icon className="h-4 w-4" />{c.label}</span>)}
          </div>

          {/* rotating benefit quote */}
          <div className="lg-rise relative mt-8 overflow-hidden rounded-3xl bg-white/10 p-6 ring-1 ring-white/20 backdrop-blur-md" style={{ animationDelay: '.3s' }} aria-live="polite">
            <Quote className="absolute right-5 top-4 h-16 w-16 text-white/10" />
            <div key={q} className="lg-quote flex gap-4">
              <span className={cx('flex h-14 w-14 shrink-0 items-center justify-center rounded-2xl bg-gradient-to-br shadow-lg', quote.tone)}><quote.icon className="h-7 w-7" /></span>
              <div>
                <div className="text-[13px] font-bold uppercase tracking-[.18em] text-amber-200">Why offline? · {quote.title}</div>
                <p className="mt-1.5 text-[19px] font-medium italic leading-snug">“{quote.text}”</p>
              </div>
            </div>
            <div className="mt-5 flex items-center gap-2">
              {QUOTES.map((x, i) => (
                <button key={x.title} onClick={() => setQ(i)} aria-label={x.title}
                  className={cx('h-2 rounded-full transition-all duration-500', i === q ? 'w-8 bg-gradient-to-r from-amber-300 to-rose-300' : 'w-2 bg-white/35 hover:bg-white/60')} />
              ))}
              <span className="ml-auto text-xs text-white/60">{q + 1} / {QUOTES.length}</span>
            </div>
          </div>

          {/* benefit grid */}
          <div className="lg-rise mt-5 grid grid-cols-3 gap-3" style={{ animationDelay: '.4s' }}>
            {QUOTES.slice(0, 3).map((x) => (
              <div key={x.title} className="group rounded-2xl bg-white/[.07] p-3.5 ring-1 ring-white/15 transition hover:-translate-y-1 hover:bg-white/[.12]">
                <span className={cx('mb-2 flex h-9 w-9 items-center justify-center rounded-xl bg-gradient-to-br shadow transition group-hover:scale-110', x.tone)}><x.icon className="h-5 w-5" /></span>
                <div className="text-sm font-bold">{x.title}</div>
              </div>
            ))}
          </div>
        </div>

        <div className="text-xs text-white/60">Authorised office users only · All activity is audit-logged · v{cfg?.version || '1.0.0'}</div>
      </section>

      {/* ------------------------------------------------------------ right: login card */}
      <section className="relative flex flex-1 items-center justify-center p-5 sm:p-8">
        <div className="lg-card-in w-full max-w-[440px]">
          <div className="mb-6 flex items-center gap-3 lg:hidden">
            <Logo size={48} src={b?.logo_data_url} onDark />
            <div><div className="text-2xl font-extrabold">{b?.app_name || 'OFFLINE SHARE'}</div><div className="text-xs text-white/75">{b?.organisation_name || b?.app_subtitle}</div></div>
          </div>

          <div className="lg-ring rounded-[28px] p-[2px] shadow-2xl shadow-black/40">
            <div className="rounded-[26px] bg-white/95 px-7 pb-7 pt-8 text-ink-900 backdrop-blur-xl sm:px-9">
              <div className="flex flex-col items-center text-center">
                <span className="lg-avatar relative flex h-20 w-20 items-center justify-center rounded-full bg-gradient-to-br from-maroon-500 via-rose-500 to-amber-400 shadow-xl">
                  <span className="flex h-[72px] w-[72px] items-center justify-center rounded-full bg-white"><KeyRound className="h-9 w-9 text-maroon-700" /></span>
                </span>
                <div className="mt-4 text-sm font-semibold text-maroon-600">{greet} 👋</div>
                <h2 className="text-[28px] font-extrabold tracking-tight">Sign in</h2>
                <p className="mt-0.5 text-sm text-ink-500">Use the Login ID and password issued by your administrator.</p>
              </div>

              <form onSubmit={submit} className="mt-6 space-y-4" noValidate>
                <div>
                  <label htmlFor="login-id" className="mb-1.5 block text-[13px] font-bold uppercase tracking-wide text-ink-600">Login ID</label>
                  <span className="lg-field group flex items-center gap-3 rounded-2xl border-2 border-ink-100 bg-ink-50/70 px-2 py-1.5 transition focus-within:border-maroon-400 focus-within:bg-white focus-within:shadow-[0_0_0_4px_rgb(var(--brand-100))]">
                    <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-gradient-to-br from-sky-400 to-blue-600 text-white shadow-md transition group-focus-within:scale-105"><User className="h-5 w-5" /></span>
                    <input id="login-id" autoFocus value={loginId} onChange={(e) => setLoginId(e.target.value)} autoComplete="username" required spellCheck={false}
                      placeholder="e.g. rahul.mehta" className="min-w-0 flex-1 bg-transparent py-2 text-[16px] font-medium outline-none placeholder:font-normal placeholder:text-ink-400" />
                  </span>
                </div>
                <div>
                  <div className="mb-1.5 flex items-center justify-between">
                    <label htmlFor="login-password" className="text-[13px] font-bold uppercase tracking-wide text-ink-600">Password</label>
                    {caps && <span role="status" className="inline-flex items-center gap-1 rounded-full bg-amber-100 px-2 py-0.5 text-[11px] font-bold text-amber-800"><AlertTriangle className="h-3 w-3" />Caps Lock is on</span>}
                  </div>
                  <span className="lg-field group flex items-center gap-3 rounded-2xl border-2 border-ink-100 bg-ink-50/70 px-2 py-1.5 transition focus-within:border-maroon-400 focus-within:bg-white focus-within:shadow-[0_0_0_4px_rgb(var(--brand-100))]">
                    <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-gradient-to-br from-fuchsia-400 to-purple-600 text-white shadow-md transition group-focus-within:scale-105"><Lock className="h-5 w-5" /></span>
                    <input id="login-password" type={show ? 'text' : 'password'} value={password} onChange={(e) => setPassword(e.target.value)} onKeyUp={capsCheck} onKeyDown={capsCheck}
                      autoComplete="current-password" required placeholder="••••••••" className="min-w-0 flex-1 bg-transparent py-2 text-[16px] font-medium tracking-wide outline-none placeholder:text-ink-300" />
                    <button type="button" onClick={() => setShow((s) => !s)} aria-label={show ? 'Hide password' : 'Show password'} className="rounded-lg p-2 text-ink-400 transition hover:bg-ink-100 hover:text-maroon-700">
                      {show ? <EyeOff className="h-5 w-5" /> : <Eye className="h-5 w-5" />}
                    </button>
                  </span>
                </div>

                {err && <div className="lg-shake flex items-start gap-2 rounded-2xl border border-red-200 bg-red-50 px-3.5 py-2.5 text-sm text-red-700"><AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />{err}</div>}

                <button type="submit" disabled={busy || !loginId.trim() || !password}
                  className="lg-btn group relative flex h-[52px] w-full items-center justify-center gap-2 overflow-hidden rounded-2xl bg-gradient-to-r from-maroon-600 via-rose-600 to-maroon-700 text-[17px] font-bold text-white shadow-lg shadow-maroon-700/30 transition hover:-translate-y-0.5 hover:shadow-xl disabled:translate-y-0 disabled:opacity-60">
                  {busy ? <span className="h-5 w-5 animate-spin rounded-full border-2 border-white/40 border-t-white" /> : <>Sign in <ArrowRight className="h-5 w-5 transition group-hover:translate-x-1" /></>}
                </button>
              </form>

              <div className="mt-6 grid grid-cols-3 gap-2 text-center text-[11.5px]">
                <div className="rounded-xl bg-emerald-50 px-2 py-2 ring-1 ring-emerald-100">
                  <div className="flex items-center justify-center gap-1 font-bold text-emerald-700">
                    <span className="relative flex h-2 w-2"><span className={cx('absolute inline-flex h-full w-full rounded-full opacity-70', cfg === false ? 'bg-red-400' : 'animate-ping bg-emerald-400')} /><span className={cx('relative inline-flex h-2 w-2 rounded-full', cfg === false ? 'bg-red-500' : 'bg-emerald-500')} /></span>
                    {cfg === false ? 'Offline' : 'Online'}
                  </div>
                  <div className="text-ink-500">Server</div>
                </div>
                <div className="rounded-xl bg-sky-50 px-2 py-2 ring-1 ring-sky-100"><div className="flex items-center justify-center gap-1 break-all text-[11px] font-bold leading-tight text-sky-700"><Server className="h-3.5 w-3.5 shrink-0" />{cfg ? `${cfg.server_ip}:${cfg.port}` : '—'}</div><div className="text-ink-500">Server address</div></div>
                <div className="rounded-xl bg-violet-50 px-2 py-2 ring-1 ring-violet-100"><div className="flex items-center justify-center gap-1 truncate font-bold text-violet-700"><Monitor className="h-3.5 w-3.5" />{cfg ? cfg.client_ip : '—'}</div><div className="text-ink-500">This PC</div></div>
              </div>
              <div className="mt-4 flex items-center justify-center gap-1.5 text-xs font-semibold text-maroon-700"><WifiOff className="h-3.5 w-3.5" />LAN Only · No Internet · Forgot password? Contact your administrator.</div>
            </div>
          </div>
          <p className="mt-5 text-center text-xs text-white/70 lg:hidden">{QUOTES[q].text}</p>
        </div>
      </section>
    </div>
  )
}
