import { useState } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { deleteLedgerEntry, type LedgerEntry } from '../api/ledgerEntries'
import Tag from './Tag'

function formatNumber(value: number): string {
  return value.toLocaleString('ru-RU', { maximumFractionDigits: 2 })
}

function formatDate(value: string): string {
  return new Date(value).toLocaleString('ru-RU')
}

function SummaryRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex justify-between text-sm py-1.5">
      <span style={{ color: 'var(--color-muted)' }}>{label}</span>
      <span style={{ color: 'var(--color-text)', fontVariantNumeric: 'tabular-nums' }}>{value}</span>
    </div>
  )
}

export default function LedgerEntryDetailPanel({
  orderId,
  entry,
  canEdit,
  onClose,
}: {
  orderId: number
  entry: LedgerEntry
  canEdit: boolean
  onClose: () => void
}) {
  const queryClient = useQueryClient()
  const [error, setError] = useState('')

  const deleteMutation = useMutation({
    mutationFn: () => deleteLedgerEntry(orderId, entry.id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['ledger-entries', orderId] })
      onClose()
    },
    onError: (err: Error) => setError(err.message),
  })

  function handleDelete() {
    if (window.confirm('Удалить запись?')) {
      deleteMutation.mutate()
    }
  }

  const badge =
    entry.type === 'income'
      ? { color: 'green' as const, label: 'Доход' }
      : { color: 'red' as const, label: 'Расход' }

  return (
    <div className="fixed inset-0 z-50" onClick={onClose}>
      <div className="absolute inset-0" style={{ background: 'rgba(0,0,0,0.5)' }} />
      <div
        onClick={(e) => e.stopPropagation()}
        className="absolute right-0 top-0 h-full w-full sm:w-[420px] overflow-y-auto p-6"
        style={{ background: 'var(--color-surface)', borderLeft: '1px solid var(--color-border)' }}
      >
        <div className="flex items-center justify-between mb-5">
          <h3 className="text-base font-semibold" style={{ color: 'var(--color-text)' }}>
            Запись ДиР #{entry.id}
          </h3>
          <button onClick={onClose} className="text-sm cursor-pointer" style={{ color: 'var(--color-muted)' }}>
            ✕
          </button>
        </div>

        {error && (
          <div
            className="rounded-lg px-3 py-2 mb-4 text-sm"
            style={{ background: 'var(--color-danger-bg)', color: 'var(--color-danger)' }}
          >
            {error}
          </div>
        )}

        <div className="rounded-[8px] p-4 mb-4" style={{ background: 'var(--color-surface-2)' }}>
          <div className="flex items-center justify-between mb-2">
            <Tag color={badge.color}>{badge.label}</Tag>
          </div>
          <SummaryRow label="Сумма" value={`${formatNumber(Number(entry.amount))} ${entry.currency}`} />
          <SummaryRow label="Курс" value={entry.exchange_rate} />
          <SummaryRow label="Автор" value={entry.author_name} />
          <SummaryRow label="Дата" value={formatDate(entry.created_at)} />
          {entry.details && (
            <p className="text-sm mt-2" style={{ color: 'var(--color-text)' }}>{entry.details}</p>
          )}
        </div>

        {canEdit && (
          <div className="flex gap-2">
            <button
              onClick={handleDelete}
              disabled={deleteMutation.isPending}
              className="rounded-lg px-4 py-2 text-sm font-medium cursor-pointer disabled:opacity-50"
              style={{ background: 'var(--color-danger-bg)', color: 'var(--color-danger)' }}
            >
              {deleteMutation.isPending ? 'Удаление...' : 'Удалить'}
            </button>
          </div>
        )}
      </div>
    </div>
  )
}
