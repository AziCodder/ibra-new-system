import { useState, type FormEvent } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuth } from '../contexts/AuthContext'

export default function LoginPage() {
  const { login } = useAuth()
  const navigate = useNavigate()
  const [loginStr, setLoginStr] = useState('')
  const [password, setPassword] = useState('')
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
      setError(err instanceof Error ? err.message : 'Login failed')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div
      className="flex items-center justify-center min-h-screen"
      style={{ background: 'var(--color-bg)' }}
    >
      <form
        onSubmit={handleSubmit}
        className="w-full max-w-sm rounded-2xl p-8"
        style={{
          background: 'var(--color-surface)',
          border: '1px solid var(--color-border)',
        }}
      >
        <h1
          className="text-2xl font-bold mb-6 text-center"
          style={{ color: 'var(--color-text)' }}
        >
          Ibra Order System
        </h1>

        {error && (
          <div
            className="rounded-lg px-4 py-2.5 mb-4 text-sm"
            style={{
              background: 'var(--color-danger-bg)',
              color: 'var(--color-danger)',
            }}
          >
            {error}
          </div>
        )}

        <label className="block mb-4">
          <span className="block text-sm mb-1.5" style={{ color: 'var(--color-muted)' }}>
            Логин
          </span>
          <input
            type="text"
            value={loginStr}
            onChange={(e) => setLoginStr(e.target.value)}
            autoFocus
            required
            className="w-full rounded-lg px-3 py-2.5 text-sm outline-none transition-colors"
            style={{
              background: 'var(--color-surface-2)',
              border: '1px solid var(--color-border)',
              color: 'var(--color-text)',
            }}
          />
        </label>

        <label className="block mb-6">
          <span className="block text-sm mb-1.5" style={{ color: 'var(--color-muted)' }}>
            Пароль
          </span>
          <input
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            required
            className="w-full rounded-lg px-3 py-2.5 text-sm outline-none transition-colors"
            style={{
              background: 'var(--color-surface-2)',
              border: '1px solid var(--color-border)',
              color: 'var(--color-text)',
            }}
          />
        </label>

        <button
          type="submit"
          disabled={loading}
          className="w-full rounded-lg py-2.5 text-sm font-medium transition-colors cursor-pointer disabled:opacity-50"
          style={{
            background: 'var(--color-primary)',
            color: '#fff',
          }}
        >
          {loading ? 'Вход...' : 'Войти'}
        </button>
      </form>
    </div>
  )
}
