import { useNavigate } from 'react-router-dom'
import { SearchX } from 'lucide-react'

export default function NotFound({
  title = 'Страница не найдена',
  message = 'Такой страницы нет, либо у вас нет к ней доступа.',
  backTo = '/',
  backLabel = '← На главную',
}: {
  title?: string
  message?: string
  backTo?: string
  backLabel?: string
}) {
  const navigate = useNavigate()

  return (
    <div className="flex items-center justify-center" style={{ minHeight: '60vh' }}>
      <div className="flex flex-col items-center text-center gap-4 px-6 py-10 max-w-md">
        <div
          className="flex items-center justify-center rounded-full"
          style={{ width: 72, height: 72, background: 'var(--color-surface-2, var(--color-surface))', border: '1px solid var(--color-border)' }}
        >
          <SearchX size={32} style={{ color: 'var(--color-faint)' }} />
        </div>

        <div className="text-xs font-bold tracking-widest" style={{ color: 'var(--color-faint)' }}>404</div>

        <h1 className="text-xl font-bold" style={{ color: 'var(--color-text)' }}>{title}</h1>

        <p className="text-sm" style={{ color: 'var(--color-muted)' }}>{message}</p>

        <button
          onClick={() => navigate(backTo)}
          className="mt-2 rounded-lg px-4 py-2 text-sm font-medium cursor-pointer"
          style={{ background: 'var(--color-primary)', color: '#fff' }}
        >
          {backLabel}
        </button>
      </div>
    </div>
  )
}
