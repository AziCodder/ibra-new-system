import { useState, type FormEvent } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuth } from '../contexts/AuthContext'
import { User, Lock, Eye, EyeOff, Sun, Moon } from 'lucide-react'

function LoginThemeToggle() {
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
      type="button"
      className="absolute top-4 right-4 w-9 h-9 rounded-full flex items-center justify-center cursor-pointer transition-colors"
      style={{ color: 'var(--color-muted)', background: 'var(--color-surface-2)' }}
      title={theme === 'dark' ? 'Светлая тема' : 'Тёмная тема'}
      aria-label={theme === 'dark' ? 'Светлая тема' : 'Тёмная тема'}
    >
      {theme === 'dark' ? <Sun size={16} /> : <Moon size={16} />}
    </button>
  )
}

export default function LoginPage() {
  const { login } = useAuth()
  const navigate = useNavigate()
  const [loginStr, setLoginStr] = useState('')
  const [password, setPassword] = useState('')
  const [showPassword, setShowPassword] = useState(false)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  async function handleSubmit(e: FormEvent) {
    e.preventDefault()
    setError('')
    setLoading(true)
    try {
      await login(loginStr, password)
      navigate('/', { replace: true })
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Неверный логин или пароль')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div
      className="relative flex items-center justify-center min-h-screen px-4"
      style={{ background: 'var(--color-bg)' }}
    >
      <LoginThemeToggle />

      <form
        onSubmit={handleSubmit}
        className="w-full p-6 sm:p-8"
        style={{
          maxWidth: 400,
          background: 'var(--color-surface)',
          border: '1px solid var(--color-border-soft)',
          borderRadius: 16,
          boxShadow: 'var(--shadow-lg)',
        }}
      >
        {/* Logo + title */}
        <div className="flex flex-col items-center mb-8 text-center">
          <div
            className="flex items-center justify-center font-bold mb-4"
            style={{
              width: 48,
              height: 48,
              borderRadius: 14,
              background: 'var(--sidebar-active-bg)',
              color: '#fff',
              fontSize: 15,
              letterSpacing: '0.02em',
            }}
          >
            IO
          </div>
          <h1
            className="text-xl font-semibold mb-1"
            style={{ color: 'var(--color-text)', letterSpacing: '-0.01em' }}
          >
            Ibragim Flow
          </h1>
          <p className="text-[13px]" style={{ color: 'var(--color-muted)' }}>
            Войдите, чтобы продолжить
          </p>
        </div>

        {error && (
          <div
            className="flex items-center gap-2 px-3 py-2.5 mb-5 text-sm rounded-lg"
            style={{
              background: 'var(--color-danger-bg)',
              border: '1px solid var(--color-danger)',
              color: 'var(--color-danger)',
            }}
          >
            {error}
          </div>
        )}

        <div className="flex flex-col gap-3 mb-6">
          <div
            className="flex items-center gap-2.5 px-3"
            style={{
              height: 42,
              background: 'var(--color-surface)',
              border: '1px solid var(--color-border)',
              borderRadius: 10,
            }}
          >
            <User size={14} style={{ color: 'var(--color-faint)', flexShrink: 0 }} />
            <input
              type="text"
              value={loginStr}
              onChange={(e) => setLoginStr(e.target.value)}
              placeholder="Логин"
              autoFocus
              required
              className="flex-1 text-sm outline-none bg-transparent"
              style={{ color: 'var(--color-text)' }}
            />
          </div>

          <div
            className="flex items-center gap-2.5 px-3"
            style={{
              height: 42,
              background: 'var(--color-surface)',
              border: '1px solid var(--color-border)',
              borderRadius: 10,
            }}
          >
            <Lock size={14} style={{ color: 'var(--color-faint)', flexShrink: 0 }} />
            <input
              type={showPassword ? 'text' : 'password'}
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="Пароль"
              required
              className="flex-1 text-sm outline-none bg-transparent"
              style={{ color: 'var(--color-text)' }}
            />
            <button
              type="button"
              onClick={() => setShowPassword(!showPassword)}
              className="cursor-pointer"
              style={{ color: 'var(--color-faint)' }}
              tabIndex={-1}
            >
              {showPassword ? <EyeOff size={16} /> : <Eye size={16} />}
            </button>
          </div>
        </div>

        <button
          type="submit"
          disabled={loading}
          className="w-full text-sm font-semibold transition-colors cursor-pointer disabled:opacity-50"
          style={{
            height: 42,
            background: 'var(--color-primary)',
            borderRadius: 10,
            color: '#fff',
          }}
        >
          {loading ? 'Вход...' : 'Войти'}
        </button>
      </form>
    </div>
  )
}
