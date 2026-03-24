import { BrowserRouter, Routes, Route } from 'react-router-dom'
import { AuthContext, useAuthState } from './hooks/useAuth'
import { ScansContext, useScansState } from './hooks/useScans'
import { PrivateRoute } from './components/PrivateRoute'
import { Navbar } from './components/Navbar'
import { OperatorView } from './pages/OperatorView'
import { AuditPage } from './pages/AuditPage'
import { StatsPage } from './pages/StatsPage'

function Layout() {
  const scansState = useScansState()

  return (
    <ScansContext.Provider value={scansState}>
      <div className="min-h-screen bg-gray-900">
        <Navbar connected={scansState.connected} />
        <main className="max-w-7xl mx-auto">
          <Routes>
            <Route path="/"       element={<OperatorView />} />
            <Route path="/audit"  element={<AuditPage />} />
            <Route path="/stats"  element={<StatsPage />} />
          </Routes>
        </main>
      </div>
    </ScansContext.Provider>
  )
}

export default function App() {
  const authState = useAuthState()

  return (
    <AuthContext.Provider value={authState}>
      <BrowserRouter>
        <PrivateRoute>
          <Layout />
        </PrivateRoute>
      </BrowserRouter>
    </AuthContext.Provider>
  )
}
