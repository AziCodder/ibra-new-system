import { Navigate } from 'react-router-dom'
import { useAuth } from '../contexts/AuthContext'
import Skeleton from './Skeleton'

export default function RequireAuth({ children }: { children: React.ReactNode }) {
  const { user, isLoading } = useAuth()

  if (isLoading) {
    return (
      <div
        className="flex flex-col items-center justify-center min-h-screen gap-4 p-6"
        style={{ background: 'var(--color-bg)' }}
      >
        <Skeleton width={200} height={24} />
        <Skeleton width={320} height={16} />
        <Skeleton width={280} height={16} />
      </div>
    )
  }

  if (!user) return <Navigate to="/login" replace />

  return <>{children}</>
}
