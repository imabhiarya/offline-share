import { Navigate, Route, Routes, useLocation } from 'react-router-dom'
import { ShieldAlert } from 'lucide-react'
import Layout, { NAV } from './components/Layout'
import { ConfirmProvider, Empty, Loading } from './components/ui'
import { AuthProvider, Perm, useAuth } from './lib/auth'
import { RealtimeProvider } from './lib/realtime'
import { ToastProvider } from './lib/toast'
import Login from './pages/Login'
import Dashboard from './pages/Dashboard'
import SendData from './pages/SendData'
import Receive from './pages/Receive'
import HistoryPage from './pages/History'
import Devices from './pages/Devices'
import UsersPage from './pages/Users'
import Files from './pages/Files'
import SettingsPage from './pages/Settings'

function Guard({ perm, children }: { perm: Perm; children: JSX.Element }) {
  const { can } = useAuth()
  if (!can(perm)) return <Empty icon={ShieldAlert} title="Access denied" body="Your role does not include this page. Contact the administrator if you need access." />
  return children
}

function Protected() {
  const { session, loading, can } = useAuth()
  const loc = useLocation()
  if (loading) return <div className="flex h-screen items-center justify-center"><Loading label="Connecting to OFFLINE SHARE server…" /></div>
  if (!session) return <Navigate to="/login" state={{ from: loc.pathname + loc.search }} replace />
  const home = NAV.find((n) => can(n.perm))?.to || '/receive'
  return (
    <RealtimeProvider>
      <Layout>
        <Routes>
          <Route path="/" element={<Navigate to={home} replace />} />
          <Route path="/dashboard" element={<Guard perm="dashboard"><Dashboard /></Guard>} />
          <Route path="/send" element={<Guard perm="send"><SendData /></Guard>} />
          <Route path="/receive" element={<Guard perm="receive"><Receive /></Guard>} />
          <Route path="/history" element={<Guard perm="history"><HistoryPage /></Guard>} />
          <Route path="/devices" element={<Guard perm="devices"><Devices /></Guard>} />
          <Route path="/users" element={<Guard perm="users"><UsersPage /></Guard>} />
          <Route path="/files" element={<Guard perm="files"><Files /></Guard>} />
          <Route path="/settings" element={<Guard perm="settings"><SettingsPage /></Guard>} />
          <Route path="*" element={<Empty title="Page not found" body="Use the sidebar to navigate." />} />
        </Routes>
      </Layout>
    </RealtimeProvider>
  )
}

export default function App() {
  return (
    <ToastProvider>
      <AuthProvider>
        <ConfirmProvider>
          <Routes>
            <Route path="/login" element={<Login />} />
            <Route path="/*" element={<Protected />} />
          </Routes>
        </ConfirmProvider>
      </AuthProvider>
    </ToastProvider>
  )
}
