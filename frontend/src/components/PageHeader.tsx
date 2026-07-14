import type { ReactNode } from 'react'
import { useAuth } from '../contexts/AuthContext'
import Avatar from './Avatar'

const ROLE_LABEL: Record<string, string> = {
  admin: 'Администратор',
  manager: 'Менеджер',
  observer: 'Наблюдатель',
}

export default function PageHeader({
  title,
  subtitle,
  children,
}: {
  title: string
  subtitle?: string
  children?: ReactNode
}) {
  const { user } = useAuth()

  return (
    <div className="flex items-start justify-between gap-4 flex-wrap mb-6">
      <div>
        <h1 className="text-xl sm:text-2xl font-bold" style={{ color: 'var(--color-text)' }}>
          {title}
        </h1>
        {subtitle && (
          <div className="text-sm mt-1" style={{ color: 'var(--color-muted)' }}>
            {subtitle}
          </div>
        )}
      </div>

      <div className="flex items-center gap-3 flex-wrap w-full sm:w-auto justify-end sm:justify-start">
        {children}
        {user && (
          <Avatar name={user.full_name} title={ROLE_LABEL[user.role] ?? user.role} />
        )}
      </div>
    </div>
  )
}
