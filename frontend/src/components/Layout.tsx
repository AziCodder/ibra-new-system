import { useState, type ReactNode } from 'react'
import { NavLink } from 'react-router-dom'
import { useAuth } from '../contexts/AuthContext'
import Avatar from './Avatar'
import {
  Package,
  CreditCard,
  Truck,
  Database,
  BarChart3,
  Sun,
  Moon,
  LogOut,
  Menu,
} from 'lucide-react'

const ROLE_LABEL: Record<string, string> = {
  admin: 'Администратор',
  manager: 'Менеджер',
  observer: 'Наблюдатель',
}

const NAV_ITEMS: { to: string; icon: typeof Package; label: string; adminOnly?: boolean }[] = [
  { to: '/', icon: Package, label: 'Заказы' },
  { to: '/payment-requests', icon: CreditCard, label: 'Оплаты' },
  { to: '/logistics', icon: Truck, label: 'Логистика' },
  { to: '/database', icon: Database, label: 'База данных', adminOnly: true },
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
      className="flex items-center justify-center cursor-pointer transition-colors"
      style={{
        width: 34,
        height: 34,
        background: 'transparent',
        border: '1px solid var(--sidebar-border)',
        borderRadius: 'var(--radius)',
        color: 'var(--sidebar-muted)',
        flexShrink: 0,
      }}
      title={theme === 'dark' ? 'Светлая тема' : 'Тёмная тема'}
      aria-label="Переключить тему"
    >
      {theme === 'dark' ? <Sun size={14} /> : <Moon size={14} />}
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
        className={`flex flex-col fixed inset-y-0 left-0 z-50 transition-transform md:translate-x-0 ${
          open ? 'translate-x-0' : '-translate-x-full'
        }`}
        style={{
          width: 232,
          background: 'var(--sidebar-bg)',
          borderRight: '1px solid var(--sidebar-border)',
        }}
      >
        <div className="flex items-center gap-2.5" style={{ padding: '18px 18px 16px', flexShrink: 0 }}>
          <div
            className="flex items-center justify-center flex-shrink-0 font-bold"
            style={{
              width: 34,
              height: 34,
              borderRadius: 10,
              background: 'var(--sidebar-active-bg)',
              color: '#fff',
              fontSize: 13,
            }}
          >
            IO
          </div>
          <div className="text-[15px]" style={{ color: 'var(--sidebar-text)', fontWeight: 700, letterSpacing: '-0.01em' }}>
            Ibra Order System
          </div>
        </div>

        <nav style={{ flex: 1, overflowY: 'auto', minHeight: 0, padding: '4px 12px' }} className="flex flex-col gap-1">
          {NAV_ITEMS.filter((item) => !item.adminOnly || user?.role === 'admin').map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.to === '/'}
              onClick={onClose}
              // No transition-colors here: a colour transition freezes these
              // links on the previous theme's palette when data-theme flips
              // (Chrome keeps the old computed colour until the element is
              // recreated), which left the menu unreadable until a reload.
              className={({ isActive }) =>
                `sidebar-link flex items-center gap-2.5 text-sm${isActive ? ' is-active' : ''}`
              }
            >
              <item.icon size={16} />
              {item.label}
            </NavLink>
          ))}
          <div
            className="flex items-center gap-2.5 text-sm opacity-60"
            style={{ color: 'var(--sidebar-muted)', borderRadius: 10, padding: '9px 12px' }}
          >
            <BarChart3 size={16} />
            Аналитика
            <span
              className="ml-auto text-[10px] px-1.5 py-0.5"
              style={{ background: 'var(--sidebar-hover-bg)', color: 'var(--sidebar-muted)', borderRadius: 'var(--radius-sm)' }}
            >
              скоро
            </span>
          </div>
        </nav>

        <div style={{ padding: 14, borderTop: '1px solid var(--sidebar-border)', flexShrink: 0 }}>
          {user && (
            <div className="flex items-center gap-2.5 mb-3">
              <Avatar name={user.full_name} background="var(--sidebar-avatar-bg)" />
              <div className="min-w-0">
                <div className="text-sm truncate" style={{ color: 'var(--sidebar-text)', fontWeight: 600 }}>
                  {user.full_name}
                </div>
                <div className="text-xs truncate" style={{ color: 'var(--sidebar-muted)' }}>
                  {ROLE_LABEL[user.role] ?? user.role}
                </div>
              </div>
            </div>
          )}
          <div className="flex items-center gap-2">
            <ThemeToggle />
            <button
              onClick={() => logout()}
              className="flex items-center justify-center gap-1.5 text-sm cursor-pointer transition-colors flex-1"
              style={{
                height: 34,
                background: 'transparent',
                border: '1px solid var(--sidebar-border)',
                borderRadius: 'var(--radius)',
                color: 'var(--color-danger)',
              }}
              title="Выйти"
              aria-label="Выйти"
            >
              <LogOut size={14} />
              Выйти
            </button>
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
      <div className="flex-1 flex flex-col min-w-0 md:ml-[232px]">
        <header
          className="flex items-center gap-3 px-3 md:hidden"
          style={{
            height: 56,
            borderBottom: '1px solid var(--sidebar-border)',
            background: 'var(--sidebar-bg)',
            position: 'sticky',
            top: 0,
            zIndex: 10,
          }}
        >
          <button
            onClick={() => setSidebarOpen(true)}
            className="cursor-pointer flex items-center justify-center"
            style={{ color: 'var(--sidebar-text)', width: 32, height: 32 }}
            aria-label="Меню"
          >
            <Menu size={18} />
          </button>
          <span className="text-[15px]" style={{ color: 'var(--sidebar-text)', fontWeight: 700, letterSpacing: '-0.01em' }}>
            Ibra Order System
          </span>
        </header>
        <main className="flex-1 min-w-0" style={{ background: 'var(--color-bg)' }}>{children}</main>
      </div>
    </div>
  )
}
