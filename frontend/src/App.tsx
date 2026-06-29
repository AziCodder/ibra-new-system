import { useEffect } from 'react'
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { AuthProvider } from './contexts/AuthContext'
import RequireAuth from './components/RequireAuth'
import LoginPage from './pages/LoginPage'

const queryClient = new QueryClient()

function Dashboard() {
  return (
    <div
      className="flex items-center justify-center min-h-screen"
      style={{ background: 'var(--color-bg)' }}
    >
      <div
        className="rounded-2xl p-8 text-center"
        style={{
          background: 'var(--color-surface)',
          border: '1px solid var(--color-border)',
        }}
      >
        <h1 className="text-2xl font-bold mb-4" style={{ color: 'var(--color-text)' }}>
          Ibra Order System
        </h1>
        <p className="text-sm" style={{ color: 'var(--color-muted)' }}>
          Добро пожаловать! Панель управления будет здесь.
        </p>
      </div>
    </div>
  )
}

function App() {
  useEffect(() => {
    const saved = localStorage.getItem('theme') || 'dark'
    document.documentElement.setAttribute('data-theme', saved)
  }, [])

  return (
    <QueryClientProvider client={queryClient}>
      <AuthProvider>
        <BrowserRouter>
          <Routes>
            <Route path="/login" element={<LoginPage />} />
            <Route
              path="/"
              element={
                <RequireAuth>
                  <Dashboard />
                </RequireAuth>
              }
            />
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </BrowserRouter>
      </AuthProvider>
    </QueryClientProvider>
  )
}

export default App
