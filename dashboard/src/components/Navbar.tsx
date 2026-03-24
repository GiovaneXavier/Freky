import { NavLink } from 'react-router-dom'
import { useAuth } from '../hooks/useAuth'

const links = [
  { to: '/',       label: 'Ao Vivo' },
  { to: '/audit',  label: 'Auditoria' },
  { to: '/stats',  label: 'Estatísticas' },
]

export function Navbar({ connected }: { connected: boolean }) {
  const { user, logout } = useAuth()

  return (
    <nav className="bg-gray-900 border-b border-gray-700 px-6 py-3 flex items-center justify-between">
      <div className="flex items-center gap-8">
        <span className="text-white font-bold tracking-widest text-lg">FREKY</span>
        <div className="flex gap-1">
          {links.map(({ to, label }) => (
            <NavLink
              key={to}
              to={to}
              end={to === '/'}
              className={({ isActive }) =>
                `px-4 py-1.5 rounded-md text-sm font-medium transition-colors ${
                  isActive
                    ? 'bg-gray-700 text-white'
                    : 'text-gray-400 hover:text-white hover:bg-gray-800'
                }`
              }
            >
              {label}
            </NavLink>
          ))}
        </div>
      </div>

      <div className="flex items-center gap-4">
        <div className="flex items-center gap-2">
          <span className={`w-2 h-2 rounded-full ${connected ? 'bg-green-400' : 'bg-red-400'}`} />
          <span className="text-xs text-gray-400">{connected ? 'Conectado' : 'Reconectando...'}</span>
        </div>

        {user && (
          <div className="flex items-center gap-3 border-l border-gray-700 pl-4">
            <div className="text-right">
              <p className="text-sm text-white font-medium">{user.username}</p>
              <p className="text-xs text-gray-500 capitalize">{user.role}</p>
            </div>
            <button
              onClick={logout}
              className="text-xs text-gray-400 hover:text-white bg-gray-800 hover:bg-gray-700 px-3 py-1.5 rounded-md transition-colors"
            >
              Sair
            </button>
          </div>
        )}
      </div>
    </nav>
  )
}
