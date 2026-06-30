import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { fetchLogistics, type LogisticsStatus } from '../api/logistics'
import CreateLogisticsModal from './CreateLogisticsModal'
import LogisticsDetailPanel from './LogisticsDetailPanel'

const STATUS_LABELS: Record<LogisticsStatus, string> = {
  in_transit: 'В дороге',
  accepted: 'Принят',
  cancelled: 'Отменён',
}

const STATUS_BADGE: Record<LogisticsStatus, { bg: string; color: string }> = {
  in_transit: { bg: 'var(--color-info-bg)', color: 'var(--color-info)' },
  accepted: { bg: 'var(--color-success-bg)', color: 'var(--color-success)' },
  cancelled: { bg: 'var(--color-danger-bg)', color: 'var(--color-danger)' },
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

  const { data: logisticsList, isLoading } = useQuery({
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
            className="rounded-lg px-4 py-2 text-sm font-medium cursor-pointer"
            style={{ background: 'var(--color-primary)', color: '#fff' }}
          >
            + Создать логистику
          </button>
        </div>
      )}

      {isLoading && <div style={{ color: 'var(--color-muted)' }}>Загрузка...</div>}

      {!isLoading && (!logisticsList || logisticsList.length === 0) && (
        <div
          className="rounded-2xl p-12 text-center"
          style={{ background: 'var(--color-surface)', border: '1px dashed var(--color-border)', color: 'var(--color-muted)' }}
        >
          Записей логистики пока нет
        </div>
      )}

      {!isLoading && logisticsList && logisticsList.length > 0 && (
        <div className="rounded-2xl overflow-hidden" style={{ border: '1px solid var(--color-border)' }}>
          <table className="w-full text-sm" style={{ borderCollapse: 'collapse' }}>
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
                const badge = STATUS_BADGE[l.status]
                return (
                  <tr
                    key={l.id}
                    onClick={() => setSelectedId(l.id)}
                    className="cursor-pointer transition-colors"
                    style={{ borderTop: '1px solid var(--color-border)' }}
                    onMouseEnter={(e) => { e.currentTarget.style.background = 'var(--color-surface-2)' }}
                    onMouseLeave={(e) => { e.currentTarget.style.background = 'transparent' }}
                  >
                    <td className="px-4 py-2.5">
                      <span className="text-xs font-semibold rounded-full px-2.5 py-1" style={{ background: badge.bg, color: badge.color }}>
                        {STATUS_LABELS[l.status]}
                      </span>
                    </td>
                    <td className="px-4 py-2.5" style={{ color: 'var(--color-text)' }}>{l.tracking || '—'}</td>
                    <td className="px-4 py-2.5" style={{ color: 'var(--color-text)' }}>
                      {l.product_name} · {formatNumber(Number(l.quantity))}
                    </td>
                    <td className="px-4 py-2.5 text-right" style={{ color: 'var(--color-text)', fontVariantNumeric: 'tabular-nums' }}>
                      {formatDate(l.ship_date)}
                    </td>
                    <td className="px-4 py-2.5 text-right" style={{ color: 'var(--color-text)', fontVariantNumeric: 'tabular-nums' }}>
                      {formatDate(l.received_date)}
                    </td>
                    <td className="px-4 py-2.5 text-right" style={{ color: 'var(--color-text)', fontVariantNumeric: 'tabular-nums' }}>
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
