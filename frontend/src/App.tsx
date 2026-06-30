import { useEffect } from 'react'
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { AuthProvider } from './contexts/AuthContext'
import RequireAuth from './components/RequireAuth'
import Layout from './components/Layout'
import LoginPage from './pages/LoginPage'
import OrdersPage from './pages/OrdersPage'
import OrderDetailPage from './pages/OrderDetailPage'
import DatabasePage from './pages/DatabasePage'

const queryClient = new QueryClient()

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
                  <Layout>
                    <OrdersPage />
                  </Layout>
                </RequireAuth>
              }
            />
            <Route
              path="/orders/:id"
              element={
                <RequireAuth>
                  <Layout>
                    <OrderDetailPage />
                  </Layout>
                </RequireAuth>
              }
            />
            <Route
              path="/database"
              element={
                <RequireAuth>
                  <Layout>
                    <DatabasePage />
                  </Layout>
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
