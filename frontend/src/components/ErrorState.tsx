/**
 * Clear, consistent error panel for failed data loads (ДИЗАЙН_СИСТЕМА.md).
 * Distinguishes a genuine failure from an empty result so users never see a
 * "nothing found" message when the request actually errored (Итог 13.3).
 */
export default function ErrorState({
  message = 'Не удалось загрузить данные',
  onRetry,
}: {
  message?: string
  onRetry?: () => void
}) {
  return (
    <div
      className="rounded-2xl p-8 text-center flex flex-col items-center gap-3"
      style={{
        background: 'var(--color-danger-bg)',
        border: '1px solid var(--color-danger)',
        color: 'var(--color-danger)',
      }}
    >
      <div className="text-2xl">⚠</div>
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
