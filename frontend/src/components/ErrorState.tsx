import { AlertTriangle } from 'lucide-react'

export default function ErrorState({
  message = 'Не удалось загрузить данные',
  onRetry,
}: {
  message?: string
  onRetry?: () => void
}) {
  return (
    <div
      className="rounded-[10px] p-8 text-center flex flex-col items-center gap-3"
      style={{
        background: 'var(--color-danger-bg)',
        border: '1px solid var(--color-danger)',
        color: 'var(--color-danger)',
      }}
    >
      <AlertTriangle size={28} />
      <div className="text-sm font-medium">{message}</div>
      {onRetry && (
        <button
          onClick={onRetry}
          className="rounded-lg px-4 py-2 text-sm font-medium cursor-pointer"
          style={{ background: 'var(--color-surface-2)', color: 'var(--color-text)' }}
        >
          Повторить
        </button>
      )}
    </div>
  )
}
