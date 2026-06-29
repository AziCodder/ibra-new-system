import { useEffect, useState } from 'react'
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'

const queryClient = new QueryClient()

function HealthCheck() {
  const [status, setStatus] = useState<string>('loading...')

  useEffect(() => {
    fetch('/api/health')
      .then((r) => r.json())
      .then((d) => setStatus(d.status))
      .catch(() => setStatus('error'))
  }, [])

  return (
    <div className="flex items-center justify-center min-h-screen" style={{ background: 'var(--color-bg)' }}>
      <div className="rounded-2xl p-8 text-center" style={{ background: 'var(--color-surface)', border: '1px solid var(--color-border)' }}>
        <h1 className="text-2xl font-bold mb-4" style={{ color: 'var(--color-text)' }}>
          Ibra Order System
        </h1>
        <p className="text-sm" style={{ color: 'var(--color-muted)' }}>
          API: <span style={{ color: status === 'ok' ? 'var(--color-success)' : 'var(--color-danger)' }}>{status}</span>
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
      <BrowserRouter>
        <Routes>
          <Route path="/" element={<HealthCheck />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </BrowserRouter>
    </QueryClientProvider>
  )
}

export default App
