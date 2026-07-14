import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { fetchLogistics, type LogisticsStatus } from '../api/logistics'
import CreateLogisticsModal from './CreateLogisticsModal'
import LogisticsDetailPanel from './LogisticsDetailPanel'
import ErrorState from './ErrorState'
import Skeleton from './Skeleton'
import Tag, { type TagColor } from './Tag'

const STATUS_LABELS: Record<LogisticsStatus, string> = {
  in_transit: 'В дороге',
  accepted: 'Принят',
  cancelled: 'Отменён',
}

const STATUS_COLOR: Record<LogisticsStatus, TagColor> = {
  in_transit: 'orange',
  accepted: 'green',
  cancelled: 'red',
}

function formatNumber(value: number): string {
  return value.toLocaleString('ru-RU', { maximumFractionDigits: 2 })
}

function formatDate(value: string | null): string {
  return value ? new Date(value).toLocaleDateString('ru-RU') : '—'
}

export default function LogisticsTab({
  orderId,
  orderNumber,
  canEdit,
  isAdmin,
}: {
  orderId: number
  orderNumber: string
  canEdit: boolean
  isAdmin: boolean
}) {
  const [showCreateModal, setShowCreateModal] = useState(false)
  const [selectedId, setSelectedId] = useState<number | null>(null)

  const { data: logisticsList, isLoading, isError, refetch } = useQuery({
    queryKey: ['logistics', orderId],
    queryFn: () => fetchLogistics(orderId),
  })

  const selected = logisticsList?.find((l) => l.id === selectedId) ?? null

  return (
    <div>
      {canEdit && (
        <div className="flex justify-end mb-3">
          <button
            onClick={() => setShowCreateModal(true)}
            className="text-sm font-medium cursor-pointer px-[15px]"
            style={{ height: 36, background: 'var(--color-primary)', borderRadius: 'var(--radius)', color: '#fff' }}
          >
            + Создать логистику
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
        <ErrorState message="Не удалось загрузить логистику" onRetry={() => refetch()} />
      )}

      {!isLoading && !isError && (!logisticsList || logisticsList.length === 0) && (
        <div
          className="rounded-[10px] p-12 text-center"
          style={{ background: 'var(--color-surface)', border: '1px dashed var(--color-border)', color: 'var(--color-muted)' }}
        >
          Записей логистики пока нет
        </div>
      )}

      {!isLoading && !isError && logisticsList && logisticsList.length > 0 && (
        <div className="rounded-[10px] overflow-x-auto" style={{ border: '1px solid var(--color-card-border)', background: 'var(--color-surface)' }}>
          <table className="rtable w-full text-sm" style={{ borderCollapse: 'collapse' }}>
            <thead>
              <tr style={{ background: 'var(--color-surface-2)' }}>
                <th className="text-left px-4 py-2.5 text-xs font-semibold uppercase tracking-wide" style={{ color: 'var(--color-muted)' }}>Статус</th>
                <th className="text-left px-4 py-2.5 text-xs font-semibold uppercase tracking-wide" style={{ color: 'var(--color-muted)' }}>Трекинг</th>
                <th className="text-left px-4 py-2.5 text-xs font-semibold uppercase tracking-wide" style={{ color: 'var(--color-muted)' }}>Товар</th>
                <th className="text-right px-4 py-2.5 text-xs font-semibold uppercase tracking-wide" style={{ color: 'var(--color-muted)' }}>Дата отправки</th>
                <th className="text-right px-4 py-2.5 text-xs font-semibold uppercase tracking-wide" style={{ color: 'var(--color-muted)' }}>Дата приёмки</th>
                <th className="text-right px-4 py-2.5 text-xs font-semibold uppercase tracking-wide" style={{ color: 'var(--color-muted)' }}>Расход</th>
              </tr>
            </thead>
            <tbody>
              {logisticsList.map((l) => {
                return (
                  <tr
                    key={l.id}
                    onClick={() => setSelectedId(l.id)}
                    className="cursor-pointer transition-colors"
                    style={{ borderTop: '1px solid var(--color-border)' }}
                    onMouseEnter={(e) => { e.currentTarget.style.background = 'var(--color-surface-2)' }}
                    onMouseLeave={(e) => { e.currentTarget.style.background = 'transparent' }}
                  >
                    <td className="px-4 py-2.5" data-label="Статус">
                      <Tag color={STATUS_COLOR[l.status]}>{STATUS_LABELS[l.status]}</Tag>
                    </td>
                    <td className="px-4 py-2.5" data-label="Трекинг" style={{ color: 'var(--color-text)' }}>{l.tracking || '—'}</td>
                    <td className="px-4 py-2.5" data-label="Товар" style={{ color: 'var(--color-text)' }}>
                      {l.product_name} · {formatNumber(Number(l.quantity))}
                    </td>
                    <td className="px-4 py-2.5 text-right" data-label="Дата отправки" style={{ color: 'var(--color-text)', fontVariantNumeric: 'tabular-nums' }}>
                      {formatDate(l.ship_date)}
                    </td>
                    <td className="px-4 py-2.5 text-right" data-label="Дата приёмки" style={{ color: 'var(--color-text)', fontVariantNumeric: 'tabular-nums' }}>
                      {formatDate(l.received_date)}
                    </td>
                    <td className="px-4 py-2.5 text-right" data-label="Расход" style={{ color: 'var(--color-text)', fontVariantNumeric: 'tabular-nums' }}>
                      {l.expense_amount ? `${formatNumber(Number(l.expense_amount))} ${l.currency}` : '—'}
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      )}

      {showCreateModal && <CreateLogisticsModal orderId={orderId} onClose={() => setShowCreateModal(false)} />}

      {selected && (
        <LogisticsDetailPanel
          key={selected.id}
          orderId={orderId}
          orderNumber={orderNumber}
          logistics={selected}
          canEdit={canEdit}
          isAdmin={isAdmin}
          onClose={() => setSelectedId(null)}
        />
      )}
    </div>
  )
}
