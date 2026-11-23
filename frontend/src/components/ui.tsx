import {
  ButtonHTMLAttributes, createContext, forwardRef, InputHTMLAttributes, ReactNode, SelectHTMLAttributes,
  TextareaHTMLAttributes, useContext, useEffect, useRef, useState,
} from 'react'
import { ChevronLeft, ChevronRight, ChevronsLeft, ChevronsRight, File, Home, Inbox, Loader2, Search, X } from 'lucide-react'

export const cx = (...c: (string | false | null | undefined)[]) => c.filter(Boolean).join(' ')

// ----------------------------------------------------------------------------- buttons
type Variant = 'primary' | 'secondary' | 'ghost' | 'danger' | 'outline'
const VARIANTS: Record<Variant, string> = {
  primary: 'bg-maroon-700 text-white hover:bg-maroon-800 shadow-sm disabled:bg-maroon-300',
  secondary: 'bg-maroon-50 text-maroon-800 hover:bg-maroon-100 disabled:opacity-50',
  outline: 'border border-ink-200 bg-white text-ink-800 hover:border-maroon-300 hover:bg-maroon-50/50 disabled:opacity-50',
  ghost: 'text-ink-700 hover:bg-ink-100 disabled:opacity-40',
  danger: 'bg-red-600 text-white hover:bg-red-700 disabled:bg-red-300',
}

interface BtnProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: Variant
  size?: 'sm' | 'md' | 'lg'
  icon?: any
  loading?: boolean
}

export const Button = forwardRef<HTMLButtonElement, BtnProps>(function Button(
  { variant = 'primary', size = 'md', icon: Icon, loading, className, children, disabled, ...rest }, ref) {
  const sz = size === 'sm' ? 'h-8 px-3 text-[13px] gap-1.5' : size === 'lg' ? 'h-11 px-5 text-[15px] gap-2' : 'h-9.5 px-4 text-sm gap-2'
  return (
    <button ref={ref} disabled={disabled || loading}
      className={cx('inline-flex items-center justify-center whitespace-nowrap rounded-lg font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-maroon-400 focus-visible:ring-offset-1 disabled:cursor-not-allowed',
        sz, VARIANTS[variant], size === 'md' && 'h-[38px]', className)} {...rest}>
      {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : Icon ? <Icon className={size === 'sm' ? 'h-3.5 w-3.5' : 'h-4 w-4'} /> : null}
      {children}
    </button>
  )
})

export function IconButton({ icon: Icon, label, className, tone, ...rest }: ButtonHTMLAttributes<HTMLButtonElement> & { icon: any; label: string; tone?: 'danger' }) {
  return (
    <button title={label} aria-label={label}
      className={cx('inline-flex h-8 w-8 items-center justify-center rounded-lg transition-colors disabled:opacity-40',
        tone === 'danger' ? 'text-ink-500 hover:bg-red-50 hover:text-red-600' : 'text-ink-500 hover:bg-maroon-50 hover:text-maroon-700', className)} {...rest}>
      <Icon className="h-4 w-4" />
    </button>
  )
}

// ----------------------------------------------------------------------------- layout
export function Card({ className, children, ...rest }: { className?: string; children: ReactNode } & React.HTMLAttributes<HTMLDivElement>) {
  return <div className={cx('rounded-2xl border border-ink-100 bg-white shadow-card', className)} {...rest}>{children}</div>
}

export function CardHeader({ title, subtitle, icon: Icon, actions }: { title: ReactNode; subtitle?: ReactNode; icon?: any; actions?: ReactNode }) {
  return (
    <div className="flex items-center justify-between gap-3 border-b border-ink-100 px-5 py-3.5">
      <div className="flex min-w-0 items-center gap-2.5">
        {Icon && <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-maroon-50 text-maroon-700"><Icon className="h-4 w-4" /></span>}
        <div className="min-w-0">
          <h3 className="truncate text-[15px] font-semibold text-ink-900">{title}</h3>
          {subtitle && <p className="truncate text-xs text-ink-500">{subtitle}</p>}
        </div>
      </div>
      {actions && <div className="flex shrink-0 items-center gap-2">{actions}</div>}
    </div>
  )
}

export function PageHeader({ title, subtitle, icon: Icon, actions }: { title: string; subtitle?: string; icon?: any; actions?: ReactNode }) {
  return (
    <div className="mb-4 flex flex-wrap items-center justify-between gap-3 print:mb-3">
      <div className="flex items-center gap-3.5">
        {Icon && <span className="os-page-icon flex shrink-0 items-center justify-center print:hidden"><Icon className="h-11 w-11 text-ink-900" strokeWidth={1.6} /></span>}
        <div>
          <h1 className="os-page-title text-[26px] font-extrabold leading-tight tracking-tight text-ink-900">{title}</h1>
          {subtitle && <p className="text-[15px] text-ink-700">{subtitle}</p>}
        </div>
      </div>
      <div className="flex flex-wrap items-center gap-2 print:hidden">
        {actions}
        <nav className="ml-2 flex items-center gap-2 text-[15px] text-ink-800" aria-label="Breadcrumb">
          <Home className="h-5 w-5 text-ink-900" /><span className="text-ink-400">/</span><span className="font-medium">{title}</span>
        </nav>
      </div>
    </div>
  )
}

const STAT_TONES: Record<string, { bg: string; icon: string }> = {
  maroon: { bg: 'bg-rose-50 border-rose-200', icon: 'text-maroon-700' },
  pink: { bg: 'bg-rose-50 border-rose-200', icon: 'text-maroon-700' },
  green: { bg: 'bg-emerald-50 border-emerald-200', icon: 'text-emerald-600' },
  blue: { bg: 'bg-sky-50 border-sky-200', icon: 'text-sky-700' },
  amber: { bg: 'bg-amber-50 border-amber-200', icon: 'text-amber-500' },
  orange: { bg: 'bg-orange-50 border-orange-200', icon: 'text-orange-500' },
  red: { bg: 'bg-red-50 border-red-200', icon: 'text-red-600' },
  violet: { bg: 'bg-violet-50 border-violet-200', icon: 'text-violet-700' },
  slate: { bg: 'bg-ink-50 border-ink-200', icon: 'text-ink-700' },
}

/** Pastel KPI card: large outline icon left, label + big value right (matches the approved design). */
export function StatCard({ label, value, icon: Icon, tone = 'maroon', hint, onClick, extra }: { label: string; value: ReactNode; icon: any; tone?: string; hint?: ReactNode; onClick?: () => void; extra?: ReactNode }) {
  const t = STAT_TONES[tone] || STAT_TONES.maroon
  return (
    <div onClick={onClick} className={cx('os-stat flex items-center gap-4 rounded-2xl border px-4 py-3.5 shadow-sm transition', t.bg, onClick && 'cursor-pointer hover:-translate-y-0.5 hover:shadow-md')}>
      <Icon className={cx('h-11 w-11 shrink-0', t.icon)} strokeWidth={1.7} />
      <div className="min-w-0 flex-1">
        <div className="text-[15px] font-semibold leading-tight text-ink-800">{label}</div>
        <div className="truncate text-[26px] font-extrabold leading-tight tabular-nums text-ink-900">{value}</div>
        {hint && <div className="truncate text-xs text-ink-600">{hint}</div>}
        {extra}
      </div>
    </div>
  )
}

/** Card with a solid brand-colour header bar, used for the right-hand detail panels. */
export function Panel({ title, icon: Icon, actions, children, className, bodyClassName }: { title: ReactNode; icon?: any; actions?: ReactNode; children: ReactNode; className?: string; bodyClassName?: string }) {
  return (
    <section className={cx('os-panel overflow-hidden rounded-2xl border border-ink-200 bg-white shadow-card', className)}>
      <header className="os-panel-head flex items-center justify-between gap-2 bg-gradient-to-r from-maroon-800 to-maroon-700 px-4 py-2.5 text-white">
        <h3 className="flex min-w-0 items-center gap-2 text-[16px] font-bold">{Icon && <Icon className="h-5 w-5 shrink-0" />}<span className="truncate">{title}</span></h3>
        {actions && <div className="shrink-0 text-sm">{actions}</div>}
      </header>
      <div className={cx('p-4', bodyClassName)}>{children}</div>
    </section>
  )
}

/** "Label : value" rows used inside detail panels. */
export function KV({ rows }: { rows: [ReactNode, ReactNode][] }) {
  return (
    <dl className="grid grid-cols-[auto_auto_1fr] gap-x-2 gap-y-1.5 text-[13.5px]">
      {rows.map(([k, v], i) => (
        <div key={i} className="contents"><dt className="font-semibold text-ink-800">{k}</dt><span className="text-ink-500">:</span><dd className="min-w-0 break-words text-ink-900">{v ?? '—'}</dd></div>
      ))}
    </dl>
  )
}

/** Grey tile button used in "Quick Actions" grids. */
export function ActionTile({ icon: Icon, label, onClick, tone = 'slate', disabled }: { icon: any; label: string; onClick?: () => void; tone?: 'slate' | 'green' | 'blue' | 'amber' | 'red' | 'violet'; disabled?: boolean }) {
  const t = { slate: 'bg-ink-50 text-ink-800 border-ink-200', green: 'bg-emerald-50 text-emerald-800 border-emerald-200', blue: 'bg-sky-50 text-sky-800 border-sky-200',
    amber: 'bg-amber-50 text-amber-800 border-amber-200', red: 'bg-red-50 text-red-700 border-red-200', violet: 'bg-violet-50 text-violet-800 border-violet-200' }[tone]
  return (
    <button onClick={onClick} disabled={disabled} className={cx('flex flex-col items-center justify-center gap-1 rounded-xl border px-2 py-2.5 text-center text-[13px] font-semibold transition hover:-translate-y-0.5 hover:shadow-md disabled:opacity-40 disabled:hover:translate-y-0 disabled:hover:shadow-none', t)}>
      <Icon className="h-6 w-6" />{label}
    </button>
  )
}

const BADGE: Record<string, string> = {
  green: 'bg-emerald-50 text-emerald-700 ring-emerald-600/15', red: 'bg-red-50 text-red-700 ring-red-600/15',
  amber: 'bg-amber-50 text-amber-700 ring-amber-600/20', blue: 'bg-sky-50 text-sky-700 ring-sky-600/15',
  maroon: 'bg-maroon-50 text-maroon-700 ring-maroon-600/15', slate: 'bg-ink-100 text-ink-700 ring-ink-500/10',
  violet: 'bg-violet-50 text-violet-700 ring-violet-600/15',
}

export function Badge({ tone = 'slate', children, dot, className }: { tone?: string; children: ReactNode; dot?: boolean; className?: string }) {
  return (
    <span className={cx('inline-flex items-center gap-1.5 whitespace-nowrap rounded-full px-2 py-0.5 text-xs font-medium ring-1 ring-inset', BADGE[tone], className)}>
      {dot && <span className="h-1.5 w-1.5 rounded-full bg-current" />}{children}
    </span>
  )
}

const STATUS: Record<string, [string, string]> = {
  pending: ['amber', 'Pending'], sent: ['blue', 'Sent'], delivered: ['green', 'Delivered'], read: ['violet', 'Read'],
  failed: ['red', 'Failed'], partial: ['amber', 'Partial'], approved: ['green', 'Approved'], blocked: ['red', 'Blocked'],
  active: ['green', 'Active'], inactive: ['red', 'Inactive'], success: ['green', 'Success'],
  online: ['green', 'Online'], offline: ['red', 'Offline'],
}

export function StatusBadge({ status }: { status: string }) {
  const [tone, label] = STATUS[status] || ['slate', status]
  return <Badge tone={tone} dot>{label}</Badge>
}

export function PriorityBadge({ priority }: { priority: string }) {
  if (priority === 'urgent') return <Badge tone="red">Urgent</Badge>
  if (priority === 'high') return <Badge tone="amber">High</Badge>
  return null
}

export function OnlineDot({ online, label }: { online: boolean; label?: boolean }) {
  return (
    <span className="inline-flex items-center gap-1.5 text-xs font-medium">
      <span className={cx('relative flex h-2.5 w-2.5')}>
        {online && <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-emerald-400 opacity-60" />}
        <span className={cx('relative inline-flex h-2.5 w-2.5 rounded-full', online ? 'bg-emerald-500' : 'bg-ink-300')} />
      </span>
      {label && <span className={online ? 'text-emerald-700' : 'text-ink-500'}>{online ? 'Online' : 'Offline'}</span>}
    </span>
  )
}

// ----------------------------------------------------------------------------- forms
/** Form field. Use `group` when the content is not a single input (editors, button groups, pickers):
 *  a <label> around several controls would forward every click to the first one. */
export function Field({ label, hint, error, children, className, required, group }: { label?: ReactNode; hint?: ReactNode; error?: string; children: ReactNode; className?: string; required?: boolean; group?: boolean }) {
  const Wrap: any = group ? 'div' : 'label'
  return (
    <div className={cx('block', className)} role={group ? 'group' : undefined}>
      <Wrap className="block">
        {label && <span className="mb-1.5 block text-[13px] font-medium text-ink-700">{label}{required && <span className="text-maroon-600"> *</span>}</span>}
        {children}
      </Wrap>
      {hint && !error && <span className="mt-1 block text-xs text-ink-500">{hint}</span>}
      {error && <span className="mt-1 block text-xs text-red-600" role="alert">{error}</span>}
    </div>
  )
}

const inputBase = 'rounded-lg border border-ink-200 bg-white px-3 py-2 text-sm text-ink-900 placeholder:text-ink-400 transition focus:border-maroon-400 focus:outline-none focus:ring-2 focus:ring-maroon-100 disabled:bg-ink-50 disabled:text-ink-500'
/** Width defaults to full unless the caller passes its own w-* class. */
const inputCls = (className?: string) => cx(inputBase, !/(^|\s)!?w-/.test(className || '') && 'w-full', className)

export const Input = forwardRef<HTMLInputElement, InputHTMLAttributes<HTMLInputElement>>(function Input({ className, ...rest }, ref) {
  return <input ref={ref} className={inputCls(className)} {...rest} />
})

export function Textarea({ className, ...rest }: TextareaHTMLAttributes<HTMLTextAreaElement>) {
  return <textarea className={inputCls(cx('min-h-[90px]', className))} {...rest} />
}

export function Select({ className, children, ...rest }: SelectHTMLAttributes<HTMLSelectElement>) {
  return <select className={inputCls(cx('pr-8', className))} {...rest}>{children}</select>
}

export function SearchInput({ value, onChange, placeholder, className, autoFocus }: { value: string; onChange: (v: string) => void; placeholder?: string; className?: string; autoFocus?: boolean }) {
  return (
    <div className={cx('relative', className)}>
      <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-ink-400" />
      <input value={value} autoFocus={autoFocus} onChange={(e) => onChange(e.target.value)} placeholder={placeholder || 'Search…'}
        className={inputCls('pl-9 pr-8')} />
      {value && <button onClick={() => onChange('')} className="absolute right-2 top-1/2 -translate-y-1/2 rounded p-0.5 text-ink-400 hover:text-ink-700" aria-label="Clear"><X className="h-4 w-4" /></button>}
    </div>
  )
}

export function Toggle({ checked, onChange, label, description, disabled }: { checked: boolean; onChange: (v: boolean) => void; label?: ReactNode; description?: ReactNode; disabled?: boolean }) {
  return (
    <label className={cx('flex cursor-pointer items-start justify-between gap-4', disabled && 'cursor-not-allowed opacity-60')}>
      {(label || description) && (
        <span className="min-w-0">
          {label && <span className="block text-sm font-medium text-ink-800">{label}</span>}
          {description && <span className="block text-xs text-ink-500">{description}</span>}
        </span>
      )}
      <button type="button" role="switch" aria-checked={checked} disabled={disabled} onClick={() => onChange(!checked)}
        className={cx('relative mt-0.5 inline-flex h-5.5 h-[22px] w-10 shrink-0 rounded-full transition-colors', checked ? 'bg-maroon-600' : 'bg-ink-200')}>
        <span className={cx('absolute top-0.5 h-[18px] w-[18px] rounded-full bg-white shadow transition-transform', checked ? 'translate-x-[20px]' : 'translate-x-0.5')} />
      </button>
    </label>
  )
}

export function Checkbox({ checked, onChange, label, indeterminate, disabled }: { checked: boolean; onChange: (v: boolean) => void; label?: ReactNode; indeterminate?: boolean; disabled?: boolean }) {
  const ref = useRef<HTMLInputElement>(null)
  useEffect(() => { if (ref.current) ref.current.indeterminate = !!indeterminate }, [indeterminate])
  return (
    <label className={cx('inline-flex cursor-pointer items-center gap-2 text-sm text-ink-800', disabled && 'opacity-50')} onClick={(e) => e.stopPropagation()}>
      <input ref={ref} type="checkbox" disabled={disabled} checked={checked} onChange={(e) => onChange(e.target.checked)}
        className="h-4 w-4 rounded border-ink-300 accent-maroon-700" />
      {label}
    </label>
  )
}

// ----------------------------------------------------------------------------- tabs / pagination
export function Tabs<T extends string>({ tabs, value, onChange, className }: { tabs: { value: T; label: ReactNode; count?: number; icon?: any }[]; value: T; onChange: (v: T) => void; className?: string }) {
  return (
    <div className={cx('flex flex-wrap gap-2', className)} role="tablist">
      {tabs.map((t) => {
        const Icon = t.icon
        const active = value === t.value
        return (
          <button key={t.value} role="tab" aria-selected={active} onClick={() => onChange(t.value)}
            className={cx('inline-flex items-center gap-2 whitespace-nowrap rounded-xl border px-4 py-2 text-[14.5px] font-semibold transition',
              active ? 'border-maroon-700 bg-maroon-700 text-white shadow-md' : 'border-ink-200 bg-ink-50 text-ink-800 hover:border-maroon-300 hover:bg-white')}>
            {Icon && <Icon className="h-[18px] w-[18px]" />}{t.label}
            {t.count !== undefined && <span className={cx('rounded-full px-2 text-[11px] font-bold', active ? 'bg-white/25' : 'bg-ink-200 text-ink-700')}>{t.count}</span>}
          </button>
        )
      })}
    </div>
  )
}

export function Pagination({ page, pageSize, total, onPage, onPageSize, label = 'records' }: { page: number; pageSize: number; total: number; onPage: (p: number) => void; onPageSize?: (n: number) => void; label?: string }) {
  const pages = Math.max(1, Math.ceil(total / pageSize))
  const from = total ? (page - 1) * pageSize + 1 : 0
  const to = Math.min(total, page * pageSize)
  const nums: (number | '…')[] = []
  const win = [1, page - 1, page, page + 1, pages].filter((n) => n >= 1 && n <= pages)
  Array.from(new Set(win)).sort((a, b) => a - b).forEach((n, i, arr) => { if (i && n - (arr[i - 1] as number) > 1) nums.push('…'); nums.push(n) })
  if (pages <= 7) { nums.length = 0; for (let n = 1; n <= pages; n++) nums.push(n) }
  const btn = 'flex h-9 min-w-9 items-center justify-center rounded-lg border px-2.5 text-sm font-medium transition disabled:opacity-40'
  const idle = 'border-ink-200 bg-white text-ink-800 hover:border-maroon-300'
  return (
    <div className="flex flex-wrap items-center justify-between gap-3 border-t border-ink-100 px-4 py-3 text-sm text-ink-700 print:hidden">
      <span>Showing <b className="text-ink-900">{from} – {to}</b> of <b className="text-ink-900">{total}</b> {label}</span>
      <div className="flex items-center gap-1">
        <button className={cx(btn, idle)} disabled={page <= 1} onClick={() => onPage(1)} aria-label="First page"><ChevronsLeft className="h-4 w-4" /></button>
        <button className={cx(btn, idle)} disabled={page <= 1} onClick={() => onPage(page - 1)} aria-label="Previous page"><ChevronLeft className="h-4 w-4" /></button>
        {nums.map((n, i) => n === '…' ? <span key={`e${i}`} className="px-1 text-ink-400">…</span> :
          <button key={n} onClick={() => onPage(n)} aria-current={n === page ? 'page' : undefined} className={cx(btn, n === page ? 'border-maroon-700 bg-maroon-700 font-bold text-white' : idle)}>{n}</button>)}
        <button className={cx(btn, idle)} disabled={page >= pages} onClick={() => onPage(page + 1)} aria-label="Next page"><ChevronRight className="h-4 w-4" /></button>
        <button className={cx(btn, idle)} disabled={page >= pages} onClick={() => onPage(pages)} aria-label="Last page"><ChevronsRight className="h-4 w-4" /></button>
      </div>
      {onPageSize && (
        <label className="flex items-center gap-2">Items per page :
          <select value={pageSize} onChange={(e) => onPageSize(Number(e.target.value))} className="rounded-lg border border-ink-200 bg-white px-2 py-1.5 text-sm">{[10, 25, 50, 100].map((n) => <option key={n}>{n}</option>)}</select>
        </label>
      )}
    </div>
  )
}

export function Spinner({ className }: { className?: string }) {
  return <Loader2 className={cx('h-5 w-5 animate-spin text-maroon-600', className)} />
}

export function Loading({ label = 'Loading…' }: { label?: string }) {
  return <div className="flex items-center justify-center gap-2 py-16 text-sm text-ink-500"><Spinner />{label}</div>
}

export function Empty({ icon: Icon = Inbox, title, body, action }: { icon?: any; title: string; body?: ReactNode; action?: ReactNode }) {
  return (
    <div className="flex flex-col items-center justify-center px-6 py-14 text-center">
      <span className="mb-3 flex h-14 w-14 items-center justify-center rounded-2xl bg-maroon-50 text-maroon-400"><Icon className="h-7 w-7" /></span>
      <div className="font-semibold text-ink-800">{title}</div>
      {body && <div className="mt-1 max-w-sm text-sm text-ink-500">{body}</div>}
      {action && <div className="mt-4">{action}</div>}
    </div>
  )
}

export function ErrorBox({ error, onRetry }: { error: string; onRetry?: () => void }) {
  return (
    <div className="m-4 rounded-xl border border-red-200 bg-red-50 p-4 text-sm text-red-700">
      {error} {onRetry && <button className="ml-2 font-semibold underline" onClick={onRetry}>Retry</button>}
    </div>
  )
}

export function Progress({ value, tone = 'maroon', className }: { value: number; tone?: 'maroon' | 'green' | 'amber' | 'red'; className?: string }) {
  const c = { maroon: 'bg-maroon-600', green: 'bg-emerald-500', amber: 'bg-amber-500', red: 'bg-red-500' }[tone]
  return <div className={cx('h-2 w-full overflow-hidden rounded-full bg-ink-100', className)}><div className={cx('h-full rounded-full transition-all', c)} style={{ width: `${Math.min(100, Math.max(0, value))}%` }} /></div>
}

// ----------------------------------------------------------------------------- modal
export function Modal({ open, onClose, title, subtitle, children, footer, size = 'md', icon: Icon, dismissible = true }: { open: boolean; onClose: () => void; title: ReactNode; subtitle?: ReactNode; children: ReactNode; footer?: ReactNode; size?: 'sm' | 'md' | 'lg' | 'xl'; icon?: any; dismissible?: boolean }) {
  useEffect(() => {
    if (!open) return
    const onKey = (e: KeyboardEvent) => dismissible && e.key === 'Escape' && onClose()
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [open, onClose])
  if (!open) return null
  const w = { sm: 'max-w-md', md: 'max-w-xl', lg: 'max-w-3xl', xl: 'max-w-5xl' }[size]
  return (
    <div className="fixed inset-0 z-50 flex items-start justify-center overflow-y-auto bg-ink-900/40 p-4 pt-[6vh] backdrop-blur-[2px] print:hidden" onMouseDown={(e) => dismissible && e.target === e.currentTarget && onClose()}>
      <div className={cx('w-full rounded-2xl bg-white shadow-pop', w)} role="dialog" aria-modal="true">
        <div className="flex items-start justify-between gap-4 border-b border-ink-100 px-5 py-4">
          <div className="flex items-center gap-3">
            {Icon && <span className="flex h-9 w-9 items-center justify-center rounded-xl bg-maroon-50 text-maroon-700"><Icon className="h-[18px] w-[18px]" /></span>}
            <div>
              <h2 className="text-[17px] font-semibold text-ink-900">{title}</h2>
              {subtitle && <p className="text-sm text-ink-500">{subtitle}</p>}
            </div>
          </div>
          {dismissible && <IconButton icon={X} label="Close" onClick={onClose} />}
        </div>
        <div className="max-h-[70vh] overflow-y-auto px-5 py-4">{children}</div>
        {footer && <div className="flex justify-end gap-2 rounded-b-2xl border-t border-ink-100 bg-ink-50/50 px-5 py-3">{footer}</div>}
      </div>
    </div>
  )
}

// Promise-based confirmation dialog: const ok = await confirm({...})
interface ConfirmOpts { title: string; body?: ReactNode; confirmLabel?: string; danger?: boolean; icon?: any }
const ConfirmCtx = createContext<(o: ConfirmOpts) => Promise<boolean>>(async () => false)

export function ConfirmProvider({ children }: { children: ReactNode }) {
  const [state, setState] = useState<(ConfirmOpts & { resolve: (v: boolean) => void }) | null>(null)
  const confirm = (o: ConfirmOpts) => new Promise<boolean>((resolve) => setState({ ...o, resolve }))
  const close = (v: boolean) => { state?.resolve(v); setState(null) }
  return (
    <ConfirmCtx.Provider value={confirm}>
      {children}
      <Modal open={!!state} onClose={() => close(false)} title={state?.title} size="sm" icon={state?.icon}
        footer={<>
          <Button variant="outline" onClick={() => close(false)}>Cancel</Button>
          <Button variant={state?.danger ? 'danger' : 'primary'} onClick={() => close(true)} autoFocus>{state?.confirmLabel || 'Confirm'}</Button>
        </>}>
        <div className="text-sm text-ink-700">{state?.body}</div>
      </Modal>
    </ConfirmCtx.Provider>
  )
}
export const useConfirm = () => useContext(ConfirmCtx)

// ----------------------------------------------------------------------------- tables
export function Table({ children, className }: { children: ReactNode; className?: string }) {
  return <div className={cx('overflow-x-auto', className)}><table className="w-full border-collapse text-left text-sm">{children}</table></div>
}
export function Th({ children, className }: { children?: ReactNode; className?: string }) {
  return <th className={cx('whitespace-nowrap border-b border-ink-200 bg-ink-100/70 px-3 py-2.5 text-[13px] font-bold text-ink-800 first:pl-4 last:pr-4', className)}>{children}</th>
}
export function Td({ children, className, ...rest }: { children?: ReactNode; className?: string } & React.TdHTMLAttributes<HTMLTableCellElement>) {
  return <td className={cx('border-b border-ink-100 px-3 py-2 align-middle text-[13.5px] text-ink-900 first:pl-4 last:pr-4', className)} {...rest}>{children}</td>
}

// ----------------------------------------------------------------------------- file icon
export function FileIcon({ ext, className }: { ext?: string; className?: string }) {
  const e = (ext || '').toLowerCase()
  const [bg, label] =
    e === 'pdf' ? ['bg-red-600', 'PDF'] :
    ['doc', 'docx', 'rtf'].includes(e) ? ['bg-blue-600', 'W'] :
    ['xls', 'xlsx', 'csv'].includes(e) ? ['bg-emerald-600', 'X'] :
    ['ppt', 'pptx'].includes(e) ? ['bg-orange-500', 'P'] :
    ['jpg', 'jpeg', 'png', 'gif', 'bmp', 'webp'].includes(e) ? ['bg-teal-600', 'IMG'] :
    ['zip', 'rar', '7z'].includes(e) ? ['bg-amber-500', 'ZIP'] :
    e === 'txt' ? ['bg-ink-500', 'TXT'] : ['', '']
  if (!bg) return <span className={cx('flex h-8 w-8 shrink-0 items-center justify-center rounded-md bg-ink-100 text-ink-600', className)}><File className="h-4 w-4" /></span>
  return <span className={cx('flex h-8 w-8 shrink-0 items-center justify-center rounded-md text-[9.5px] font-extrabold tracking-tight text-white shadow-sm', bg, className)}>{label}</span>
}

export function Avatar({ name, size = 'md', online }: { name: string; size?: 'sm' | 'md' | 'lg'; online?: boolean }) {
  const s = size === 'sm' ? 'h-7 w-7 text-[11px]' : size === 'lg' ? 'h-11 w-11 text-sm' : 'h-9 w-9 text-xs'
  const init = name.split(/\s+/).filter(Boolean).slice(0, 2).map((p) => p[0]?.toUpperCase()).join('')
  return (
    <span className={cx('relative inline-flex shrink-0 items-center justify-center rounded-full bg-gradient-to-br from-maroon-500 to-maroon-800 font-semibold text-white', s)}>
      {init || '?'}
      {online !== undefined && <span className={cx('absolute -bottom-0.5 -right-0.5 h-3 w-3 rounded-full border-2 border-white', online ? 'bg-emerald-500' : 'bg-ink-300')} />}
    </span>
  )
}
