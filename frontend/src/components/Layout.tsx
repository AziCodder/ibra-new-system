import { useState, type ReactNode } from 'react'
import { NavLink } from 'react-router-dom'
import { useAuth } from '../contexts/AuthContext'

const ROLE_LABELS: Record<string, string> = {
  admin: 'Администратор',
  manager: 'Менеджер',
  observer: 'Наблюдатель',
}

const NAV_ITEMS = [
  { to: '/', icon: '📦', label: 'Заказы' },
  { to: '/payment-requests', icon: '💳', label: 'Оплаты' },
  { to: '/logistics', icon: '🚚', label: 'Логистика' },
  { to: '/database', icon: '🗄️', label: 'База данных' },
]

function ThemeToggle() {
  const [theme, setTheme] = useState(() => localStorage.getItem('theme') || 'dark')

  function toggle() {
    const next = theme === 'dark' ? 'light' : 'dark'
    setTheme(next)
    localStorage.setItem('theme', next)
    document.documentElement.setAttribute('data-theme', next)
  }

  return (
    <button
      onClick={toggle}
      className="w-full rounded-lg px-3 py-2 text-sm text-left cursor-pointer"
      style={{ background: 'var(--color-surface-2)', color: 'var(--color-text)' }}
    >
      {theme === 'dark' ? '☀ Светлая' : '🌙 Тёмная'}
    </button>
  )
}

function Sidebar({ open, onClose }: { open: boolean; onClose: () => void }) {
  const { user, logout } = useAuth()

  return (
    <>
      {open && (
        <div
          className="fixed inset-0 z-40 md:hidden"
          style={{ background: 'rgba(0,0,0,0.5)' }}
          onClick={onClose}
        />
      )}
      <aside
        className="flex flex-col fixed md:static inset-y-0 left-0 z-50 transition-transform md:translate-x-0"
        style={{
          width: 248,
          background: 'var(--color-sidebar)',
          borderRight: '1px solid var(--color-border)',
          transform: open ? 'translateX(0)' : undefined,
        }}
      >
        <div className="px-5 py-5">
          <div className="text-base font-extrabold" style={{ color: 'var(--color-text)' }}>
            Ibra Order System
          </div>
        </div>

        <nav className="flex-1 px-3 flex flex-col gap-1">
          {NAV_ITEMS.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.to === '/'}
              onClick={onClose}
              className="flex items-center gap-2.5 rounded-lg px-3 py-2.5 text-sm font-medium transition-colors"
              style={({ isActive }) => ({
                background: isActive ? 'var(--color-primary-bg)' : 'transparent',
                color: isActive ? 'var(--color-primary)' : 'var(--color-muted)',
              })}
            >
              <span>{item.icon}</span>
              {item.label}
            </NavLink>
          ))}
          <div
            className="flex items-center gap-2.5 rounded-lg px-3 py-2.5 text-sm font-medium opacity-50"
            style={{ color: 'var(--color-faint)' }}
          >
            <span>📊</span>
            Аналитика
            <span
              className="ml-auto text-[10px] rounded-full px-1.5 py-0.5"
              style={{ background: 'var(--color-surface-3)' }}
            >
              скоро
            </span>
          </div>
        </nav>

        <div className="px-3 py-4 flex flex-col gap-2" style={{ borderTop: '1px solid var(--color-border)' }}>
          <ThemeToggle />
          <button
            onClick={() => logout()}
            className="w-full rounded-lg px-3 py-2 text-sm text-left cursor-pointer"
            style={{ background: 'var(--color-surface-2)', color: 'var(--color-danger)' }}
          >
            Выйти
          </button>
          <div className="flex items-center gap-2.5 px-1 pt-1">
            <div
              className="w-8 h-8 rounded-full flex items-center justify-center text-xs font-bold"
              style={{ background: 'var(--color-primary)', color: '#fff' }}
            >
              {user?.full_name?.[0] || user?.login?.[0]?.toUpperCase() || '?'}
            </div>
            <div className="min-w-0">
              <div className="text-sm truncate" style={{ color: 'var(--color-text)' }}>
                {user?.full_name || user?.login}
              </div>
              <div className="text-xs" style={{ color: 'var(--color-muted)' }}>
                {user ? ROLE_LABELS[user.role] : ''}
              </div>
            </div>
          </div>
        </div>
      </aside>
    </>
  )
}

export default function Layout({ children }: { children: ReactNode }) {
  const [sidebarOpen, setSidebarOpen] = useState(false)

  return (
    <div className="flex min-h-screen" style={{ background: 'var(--color-bg)' }}>
      <Sidebar open={sidebarOpen} onClose={() => setSidebarOpen(false)} />
      <div className="flex-1 flex flex-col min-w-0">
        <header
          className="flex items-center gap-3 px-4 py-3 md:hidden"
          style={{ borderBottom: '1px solid var(--color-border)' }}
        >
          <button
            onClick={() => setSidebarOpen(true)}
            className="cursor-pointer text-lg"
            style={{ color: 'var(--color-text)' }}
            aria-label="Меню"
          >
            ☰
          </button>
        </header>
        <main className="flex-1 min-w-0">{children}</main>
      </div>
    </div>
  )
}
