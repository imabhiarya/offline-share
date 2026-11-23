import { createContext, ReactNode, useCallback, useContext, useEffect, useState } from 'react'
import { api, setCsrf, setUnauthorisedHandler } from './api'
import { configureFormats } from './format'

export type Perm = 'dashboard' | 'send' | 'receive' | 'history' | 'devices' | 'users' | 'files' | 'settings'

export interface Me {
  id: number
  full_name: string
  login_id: string
  role: 'super_admin' | 'admin' | 'user' | 'readonly'
  role_name: string
  section: string
  section_id: number | null
  email: string
  mobile: string
  assigned_device: string
  must_change_password: boolean
  permissions: Perm[]
  last_login_at: string | null
}

export interface Branding {
  app_name: string
  app_subtitle: string
  organisation_name: string
  organisation_slogan: string
  logo_data_url: string
  date_format: string
  time_format: string
  theme: string
  layout_style: string
  desktop_notifications: boolean
  sound_notifications: boolean
  notify_new_message: boolean
  notify_new_file: boolean
  heartbeat_interval_seconds: number
  max_file_size_mb: number
  max_files_per_transfer: number
  allowed_extensions: string[]
  delivery_confirmation_default: boolean
  read_receipt_default: boolean
  file_whitelist_enforced: boolean
}

export interface Session {
  user: Me
  branding: Branding
  server_ip: string
  port: number
  https: boolean
  version: string
  client_ip: string
  device: { id: number; pc_name: string; status: string } | null
  session_timeout_minutes: number
}

interface AuthCtx {
  session: Session | null
  loading: boolean
  login: (login_id: string, password: string) => Promise<Session>
  logout: () => Promise<void>
  refresh: () => Promise<void>
  can: (p: Perm) => boolean
  isAdmin: boolean
  isSuper: boolean
  readOnly: boolean
}

const Ctx = createContext<AuthCtx>(null as any)

export function AuthProvider({ children }: { children: ReactNode }) {
  const [session, setSession] = useState<Session | null>(null)
  const [loading, setLoading] = useState(true)

  const apply = (s: Session) => {
    setCsrf((s as any).csrf_token || '')
    configureFormats(s.branding.date_format, s.branding.time_format)
    document.title = s.branding.app_name || 'OFFLINE SHARE'
    applyTheme(s.branding.theme)
    setSession(s)
  }

  const refresh = useCallback(async () => {
    try {
      apply(await api.get<Session>('/api/auth/me'))
    } catch {
      setSession(null)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    setUnauthorisedHandler(() => setSession(null))
    refresh()
  }, [refresh])

  const login = async (login_id: string, password: string) => {
    await api.post('/api/auth/login', { login_id, password })
    const s = await api.get<Session>('/api/auth/me')
    apply(s)
    return s
  }

  const logout = async () => {
    try {
      await api.post('/api/auth/logout')
    } finally {
      setSession(null)
    }
  }

  const role = session?.user.role
  const value: AuthCtx = {
    session, loading, login, logout, refresh,
    can: (p) => !!session?.user.permissions.includes(p),
    isAdmin: role === 'super_admin' || role === 'admin',
    isSuper: role === 'super_admin',
    readOnly: role === 'readonly',
  }
  return <Ctx.Provider value={value}>{children}</Ctx.Provider>
}

export const useAuth = () => useContext(Ctx)

export const THEMES = ['maroon', 'blue', 'green', 'navy', 'purple'] as const
export function applyTheme(t?: string) {
  document.documentElement.dataset.theme = (THEMES as readonly string[]).includes(t || '') ? t : 'maroon'
}
