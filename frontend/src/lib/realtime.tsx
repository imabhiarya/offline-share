// Live channel to the server. Receives new transfers, acknowledges them (proof of delivery),
// sends a heartbeat at the configured interval and reconnects automatically.
import { createContext, ReactNode, useContext, useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuth } from './auth'
import { useToast } from './toast'

type Listener = (msg: any) => void

interface RealtimeCtx {
  connected: boolean
  subscribe: (fn: Listener) => () => void
  unread: number
  setUnread: (n: number) => void
  notifTick: number
}

const Ctx = createContext<RealtimeCtx>(null as any)

export function RealtimeProvider({ children }: { children: ReactNode }) {
  const { session, refresh } = useAuth()
  const toast = useToast()
  const nav = useNavigate()
  const [connected, setConnected] = useState(false)
  const [unread, setUnread] = useState(0)
  const [notifTick, setNotifTick] = useState(0)
  const listeners = useRef(new Set<Listener>())
  const wsRef = useRef<WebSocket | null>(null)

  useEffect(() => {
    if (!session) return
    let stopped = false
    let retry = 1000
    let pingTimer: number | undefined
    let reconnectTimer: number | undefined
    const interval = Math.max(10, session.branding.heartbeat_interval_seconds || 30) * 1000

    const connect = () => {
      const proto = location.protocol === 'https:' ? 'wss' : 'ws'
      const ws = new WebSocket(`${proto}://${location.host}/ws`)
      wsRef.current = ws
      ws.onopen = () => {
        setConnected(true)
        retry = 1000
        pingTimer = window.setInterval(() => {
          if (ws.readyState === WebSocket.OPEN) ws.send(JSON.stringify({ type: 'ping' }))
        }, interval)
      }
      ws.onmessage = (ev) => {
        let msg: any
        try { msg = JSON.parse(ev.data) } catch { return }
        if (msg.type === 'transfer.new') {
          // acknowledge receipt immediately – this is what marks the transfer Delivered
          ws.send(JSON.stringify({ type: 'ack', recipient_ids: [msg.transfer.recipient_id] }))
          setUnread((n) => n + 1)
          const t = msg.transfer
          const br = session.branding
          const wanted = t.file_count ? br.notify_new_file !== false : br.notify_new_message !== false
          if (msg.notify !== false && wanted) {
            if (br.sound_notifications !== false) chime(t.priority === 'urgent')
            toast.push({
              kind: t.priority === 'urgent' ? 'warning' : 'info',
              title: `${t.priority === 'urgent' ? 'URGENT: ' : ''}New ${t.file_count ? 'file' : 'message'} from ${t.sender_name}`,
              body: t.subject,
              action: { label: 'Open inbox', onClick: () => nav(`/receive?open=${t.recipient_id}`) },
            }, 9000)
            desktopNotify(session.branding.desktop_notifications, `New ${t.file_count ? 'file' : 'message'} from ${t.sender_name}`,
              `${t.subject}${t.sender_pc ? ` · ${t.sender_pc}` : ''}`, () => nav(`/receive?open=${t.recipient_id}`))
          }
        }
        if (msg.type === 'notification') setNotifTick((n) => n + 1)
        if (msg.type === 'transfer.status' && msg.recipient?.status === 'failed') setNotifTick((n) => n + 1)
        if (msg.type === 'settings.changed') refresh()
        if (msg.type === 'system.restored') toast.warning('Server data was restored from a backup', 'Reload the page if anything looks out of date.')
        listeners.current.forEach((fn) => fn(msg))
      }
      ws.onclose = (ev) => {
        setConnected(false)
        window.clearInterval(pingTimer)
        if (stopped) return
        if (ev.code === 4401) { refresh(); return }
        reconnectTimer = window.setTimeout(connect, retry)
        retry = Math.min(retry * 2, 15000)
      }
      ws.onerror = () => ws.close()
    }
    connect()
    return () => {
      stopped = true
      window.clearInterval(pingTimer)
      window.clearTimeout(reconnectTimer)
      wsRef.current?.close()
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [session?.user.id])

  const subscribe = (fn: Listener) => {
    listeners.current.add(fn)
    return () => { listeners.current.delete(fn) }
  }

  return <Ctx.Provider value={{ connected, subscribe, unread, setUnread, notifTick }}>{children}</Ctx.Provider>
}

let audioCtx: AudioContext | null = null
/** Short two-tone chime generated locally with Web Audio (no sound files, works offline). */
function chime(urgent: boolean) {
  try {
    audioCtx = audioCtx || new (window.AudioContext || (window as any).webkitAudioContext)()
    const ctx = audioCtx
    const notes = urgent ? [880, 660, 880] : [660, 880]
    notes.forEach((f, i) => {
      const o = ctx.createOscillator(), g = ctx.createGain()
      o.type = 'sine'; o.frequency.value = f
      const t0 = ctx.currentTime + i * 0.16
      g.gain.setValueAtTime(0.0001, t0); g.gain.exponentialRampToValueAtTime(0.18, t0 + 0.02); g.gain.exponentialRampToValueAtTime(0.0001, t0 + 0.15)
      o.connect(g).connect(ctx.destination); o.start(t0); o.stop(t0 + 0.16)
    })
  } catch { /* audio blocked until the user interacts with the page */ }
}

function desktopNotify(enabled: boolean, title: string, body: string, onClick: () => void) {
  if (!enabled || !('Notification' in window) || document.hasFocus()) return
  if (Notification.permission === 'granted') {
    const n = new Notification(title, { body, icon: '/favicon.svg', tag: 'offline-share' })
    n.onclick = () => { window.focus(); onClick(); n.close() }
  }
}

export function requestDesktopPermission() {
  if ('Notification' in window && Notification.permission === 'default') Notification.requestPermission()
}

export const useRealtime = () => useContext(Ctx)

/** Subscribe to realtime events inside a component. */
export function useRealtimeEvent(fn: Listener, deps: any[] = []) {
  const { subscribe } = useRealtime()
  // eslint-disable-next-line react-hooks/exhaustive-deps
  useEffect(() => subscribe(fn), deps)
}
