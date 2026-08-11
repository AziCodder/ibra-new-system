import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { fetchLedgerEntries, type LedgerEntryType } from '../api/ledgerEntries'
import CreateLedgerEntryModal from './CreateLedgerEntryModal'
import LedgerEntryDetailPanel from './LedgerEntryDetailPanel'
import ErrorState from './ErrorState'
import Skeleton from './Skeleton'
import Tag, { type TagColor } from './Tag'

const TYPE_LABELS: Record<LedgerEntryType, string> = {
  income: 'Доход',
  expense: 'Расход',
}

const TYPE_COLOR: Record<LedgerEntryType, TagColor> = {
  income: 'green',
  expense: 'red',
}

function formatNumber(value: number): string {
  return value.toLocaleString('ru-RU', { maximumFractionDigits: 2 })
}

function formatDate(value: string): string {
  return new Date(value).toLocaleDateString('ru-RU')
}

export default function LedgerTab({
  orderId,
  canEdit,
  orderCurrency,
}: {
  orderId: number
  canEdit: boolean
  orderCurrency: string
}) {
  const [createType, setCreateType] = useState<LedgerEntryType | null>(null)
  const [selectedId, setSelectedId] = useState<number | null>(null)

  const { data: entries, isLoading, isError, refetch } = useQuery({
    queryKey: ['ledger-entries', orderId],
    queryFn: () => fetchLedgerEntries(orderId),
  })

  const selected = entries?.find((e) => e.id === selectedId) ?? null

  const totalsByCurrency = new Map<string, { income: number; expense: number }>()
  for (const entry of entries ?? []) {
    const bucket = totalsByCurrency.get(entry.currency) ?? { income: 0, expense: 0 }
    if (entry.type === 'income') {
      bucket.income += Number(entry.amount)
    } else {
      bucket.expense += Number(entry.amount)
    }
    totalsByCurrency.set(entry.currency, bucket)
  }

  return (
    <div>
      {canEdit && (
        <div className="flex justify-end gap-2 mb-3">
          <button
            onClick={() => setCreateType('income')}
            className="rounded-lg px-4 py-2 text-sm font-medium cursor-pointer"
            style={{ background: 'var(--color-success-bg)', color: 'var(--color-success)' }}
          >
            + Добавить доход
          </button>
          <button
            onClick={() => setCreateType('expense')}
            className="rounded-lg px-4 py-2 text-sm font-medium cursor-pointer"
            style={{ background: 'var(--color-danger-bg)', color: 'var(--color-danger)' }}
          >
            + Добавить расход
          </button>
        </div>
      )}

      {isLoading && (
        <div className="flex flex-col gap-2">
          {Array.from({ length: 4 }).map((_, i) => (
            <Skeleton key={i} height={48} radius={10} />
          ))}
        </div>
      )}

      {!isLoading && isError && (
        <ErrorState message="Не удалось загрузить записи ДиР" onRetry={() => refetch()} />
      )}

      {!isLoading && !isError && (!entries || entries.length === 0) && (
        <div
          className="rounded-[10px] p-12 text-center"
          style={{ background: 'var(--color-surface)', border: '1px dashed var(--color-border)', color: 'var(--color-muted)' }}
        >
          Записей ДиР пока нет
        </div>
      )}

      {!isLoading && !isError && entries && entries.length > 0 && (
        <div className="rounded-[10px] overflow-x-auto" style={{ border: '1px solid var(--color-card-border)', background: 'var(--color-surface)', boxShadow: 'var(--shadow-card)' }}>
          <table className="rtable w-full text-sm" style={{ borderCollapse: 'collapse' }}>
            <thead>
              <tr style={{ background: 'var(--color-surface-2)' }}>
                <th className="text-left px-4 py-2.5 text-xs font-semibold uppercase tracking-wide" style={{ color: 'var(--color-muted)' }}>Тип</th>
                <th className="text-right px-4 py-2.5 text-xs font-semibold uppercase tracking-wide" style={{ color: 'var(--color-muted)' }}>Сумма</th>
                <th className="text-left px-4 py-2.5 text-xs font-semibold uppercase tracking-wide" style={{ color: 'var(--color-muted)' }}>Валюта</th>
                <th className="text-right px-4 py-2.5 text-xs font-semibold uppercase tracking-wide" style={{ color: 'var(--color-muted)' }}>Курс</th>
                <th className="text-right px-4 py-2.5 text-xs font-semibold uppercase tracking-wide" style={{ color: 'var(--color-muted)' }}>Дата</th>
              </tr>
            </thead>
            <tbody>
              {entries.map((entry) => {
                return (
                  <tr
                    key={entry.id}
                    onClick={() => setSelectedId(entry.id)}
                    className="cursor-pointer transition-colors"
                    style={{ borderTop: '1px solid var(--color-border)' }}
                    onMouseEnter={(e) => { e.currentTarget.style.background = 'var(--color-surface-2)' }}
                    onMouseLeave={(e) => { e.currentTarget.style.background = 'transparent' }}
                  >
                    <td className="px-4 py-2.5" data-label="Тип">
                      <Tag color={TYPE_COLOR[entry.type]}>{TYPE_LABELS[entry.type]}</Tag>
                    </td>
                    <td className="px-4 py-2.5 text-right" data-label="Сумма" style={{ color: 'var(--color-text)', fontVariantNumeric: 'tabular-nums' }}>
                      {formatNumber(Number(entry.amount))}
                    </td>
                    <td className="px-4 py-2.5" data-label="Валюта" style={{ color: 'var(--color-text)' }}>{entry.currency}</td>
                    <td className="px-4 py-2.5 text-right" data-label="Курс" style={{ color: 'var(--color-text)', fontVariantNumeric: 'tabular-nums' }}>
                      {entry.currency === orderCurrency
                        ? entry.exchange_rate
                        : `1 ${orderCurrency} = ${entry.exchange_rate} ${entry.currency}`}
                    </td>
                    <td className="px-4 py-2.5 text-right" data-label="Дата" style={{ color: 'var(--color-text)', fontVariantNumeric: 'tabular-nums' }}>
                      {formatDate(entry.created_at)}
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>

          <div className="px-4 py-3 flex flex-wrap gap-x-6 gap-y-1.5 text-sm" style={{ background: 'var(--color-surface-2)', borderTop: '1px solid var(--color-border)' }}>
            {[...totalsByCurrency.entries()].map(([currency, totals]) => (
              <div key={currency} className="flex gap-4">
                <span style={{ color: 'var(--color-muted)' }}>{currency}:</span>
                <span style={{ color: 'var(--color-success)' }}>Доходы {formatNumber(totals.income)}</span>
                <span style={{ color: 'var(--color-danger)' }}>Расходы {formatNumber(totals.expense)}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {createType && (
        <CreateLedgerEntryModal
          orderId={orderId}
          type={createType}
          orderCurrency={orderCurrency}
          onClose={() => setCreateType(null)}
        />
      )}

      {selected && (
        <LedgerEntryDetailPanel
          key={selected.id}
          orderId={orderId}
          entry={selected}
          canEdit={canEdit}
          orderCurrency={orderCurrency}
          onClose={() => setSelectedId(null)}
        />
      )}
    </div>
  )
}
