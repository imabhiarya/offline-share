import { createContext, ReactNode, useCallback, useContext, useState } from 'react'
import { AlertTriangle, CheckCircle2, Info, X, XCircle } from 'lucide-react'

type Kind = 'success' | 'error' | 'info' | 'warning'
interface Toast { id: number; kind: Kind; title: string; body?: string; action?: { label: string; onClick: () => void } }

interface ToastCtx {
  push: (t: Omit<Toast, 'id'>, ms?: number) => void
  success: (title: string, body?: string) => void
  error: (title: string, body?: string) => void
  info: (title: string, body?: string) => void
  warning: (title: string, body?: string) => void
}

const Ctx = createContext<ToastCtx>(null as any)
let seq = 1

const ICON = { success: CheckCircle2, error: XCircle, info: Info, warning: AlertTriangle }
const TONE = {
  success: 'text-emerald-600', error: 'text-red-600', info: 'text-maroon-600', warning: 'text-amber-600',
}

export function ToastProvider({ children }: { children: ReactNode }) {
  const [items, setItems] = useState<Toast[]>([])
  const remove = (id: number) => setItems((xs) => xs.filter((x) => x.id !== id))
  const push = useCallback((t: Omit<Toast, 'id'>, ms = 5000) => {
    const id = seq++
    setItems((xs) => [...xs.slice(-4), { ...t, id }])
    if (ms > 0) setTimeout(() => remove(id), ms)
  }, [])
  const v: ToastCtx = {
    push,
    success: (title, body) => push({ kind: 'success', title, body }),
    error: (title, body) => push({ kind: 'error', title, body }, 8000),
    info: (title, body) => push({ kind: 'info', title, body }),
    warning: (title, body) => push({ kind: 'warning', title, body }, 7000),
  }
  return (
    <Ctx.Provider value={v}>
      {children}
      <div className="fixed bottom-5 right-5 z-[100] flex w-96 max-w-[calc(100vw-2rem)] flex-col gap-2 print:hidden" aria-live="polite">
        {items.map((t) => {
          const Icon = ICON[t.kind]
          return (
            <div key={t.id} className="flex gap-3 rounded-xl border border-ink-100 bg-white p-3.5 shadow-pop animate-[fadein_.2s_ease-out]">
              <Icon className={`mt-0.5 h-5 w-5 shrink-0 ${TONE[t.kind]}`} />
              <div className="min-w-0 flex-1">
                <div className="text-sm font-semibold text-ink-900">{t.title}</div>
                {t.body && <div className="mt-0.5 break-words text-sm text-ink-600">{t.body}</div>}
                {t.action && (
                  <button className="mt-1.5 text-sm font-semibold text-maroon-700 hover:underline"
                    onClick={() => { t.action!.onClick(); remove(t.id) }}>{t.action.label}</button>
                )}
              </div>
              <button onClick={() => remove(t.id)} className="text-ink-400 hover:text-ink-700" aria-label="Dismiss">
                <X className="h-4 w-4" />
              </button>
            </div>
          )
        })}
      </div>
    </Ctx.Provider>
  )
}

export const useToast = () => useContext(Ctx)
