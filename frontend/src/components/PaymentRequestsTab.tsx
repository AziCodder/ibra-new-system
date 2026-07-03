import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { fetchPaymentRequests, type PaymentRequestPriority } from '../api/paymentRequests'
import CreatePaymentRequestModal from './CreatePaymentRequestModal'
import PaymentRequestDetailPanel from './PaymentRequestDetailPanel'
import ErrorState from './ErrorState'
import Skeleton from './Skeleton'

const PRIORITY_BADGE: Record<PaymentRequestPriority, { label: string; bg: string; color: string }> = {
  low: { label: 'Низкий', bg: 'var(--color-surface-3)', color: 'var(--color-muted)' },
  normal: { label: 'Обычно', bg: 'var(--color-info-bg)', color: 'var(--color-info)' },
  urgent: { label: 'Срочно', bg: 'var(--color-danger-bg)', color: 'var(--color-danger)' },
}

function formatNumber(value: number): string {
  return value.toLocaleString('ru-RU', { maximumFractionDigits: 2 })
}

export default function PaymentRequestsTab({
  orderId,
  canEdit,
  orderCurrency,
}: {
  orderId: number
  canEdit: boolean
  orderCurrency: string
}) {
  const [showCreateModal, setShowCreateModal] = useState(false)
  const [selectedRequestId, setSelectedRequestId] = useState<number | null>(null)

  const { data: requests, isLoading, isError, refetch } = useQuery({
    queryKey: ['payment-requests', orderId],
    queryFn: () => fetchPaymentRequests(orderId),
  })

  const selectedRequest = requests?.find((r) => r.id === selectedRequestId) ?? null

  return (
    <div>
      {canEdit && (
        <div className="flex justify-end mb-3">
          <button
            onClick={() => setShowCreateModal(true)}
            className="rounded-lg px-4 py-2 text-sm font-medium cursor-pointer"
            style={{ background: 'var(--color-primary)', color: '#fff' }}
          >
            + Создать запрос
          </button>
        </div>
      )}

      {isLoading && (
        <div className="grid gap-3" style={{ gridTemplateColumns: 'repeat(auto-fill, minmax(260px, 1fr))' }}>
          {Array.from({ length: 3 }).map((_, i) => (
            <Skeleton key={i} height={140} radius={16} />
          ))}
        </div>
      )}

      {!isLoading && isError && (
        <ErrorState message="Не удалось загрузить запросы на оплату" onRetry={() => refetch()} />
      )}

      {!isLoading && !isError && (!requests || requests.length === 0) && (
        <div
          className="rounded-2xl p-12 text-center"
          style={{ background: 'var(--color-surface)', border: '1px dashed var(--color-border)', color: 'var(--color-muted)' }}
        >
          Запросов на оплату пока нет
        </div>
      )}

      {!isLoading && !isError && requests && requests.length > 0 && (
        <div className="grid gap-3" style={{ gridTemplateColumns: 'repeat(auto-fill, minmax(260px, 1fr))' }}>
          {requests.map((request) => {
            const badge = PRIORITY_BADGE[request.priority]
            const total = Number(request.total_amount)
            const paid = Number(request.paid_amount)
            const progress = total > 0 ? Math.min(100, (paid / total) * 100) : 0
            return (
              <div
                key={request.id}
                onClick={() => setSelectedRequestId(request.id)}
                className="rounded-2xl p-4 cursor-pointer"
                style={{ background: 'var(--color-surface)', border: '1px solid var(--color-border)' }}
              >
                <div className="flex items-center justify-between mb-3">
                  <span
                    className="text-xs font-semibold rounded px-2 py-0.5"
                    style={{ background: 'var(--color-surface-3)', color: 'var(--color-text)' }}
                  >
                    {request.currency}
                  </span>
                  <span className="text-xs font-semibold rounded-full px-2.5 py-1" style={{ background: badge.bg, color: badge.color }}>
                    {badge.label}
                  </span>
                </div>

                <div className="space-y-1 text-sm mb-3">
                  <div className="flex justify-between" style={{ color: 'var(--color-muted)' }}>
                    <span>Всего</span>
                    <span style={{ color: 'var(--color-text)', fontVariantNumeric: 'tabular-nums' }}>
                      {formatNumber(total)} {request.currency}
                    </span>
                  </div>
                  <div className="flex justify-between" style={{ color: 'var(--color-muted)' }}>
                    <span>Оплачено</span>
                    <span style={{ color: 'var(--color-text)', fontVariantNumeric: 'tabular-nums' }}>
                      {formatNumber(paid)} {orderCurrency}
                    </span>
                  </div>
                  <div className="flex justify-between" style={{ color: 'var(--color-muted)' }}>
                    <span>Остаток</span>
                    <span style={{ color: 'var(--color-text)', fontVariantNumeric: 'tabular-nums' }}>
                      {formatNumber(Number(request.remaining_amount))} {request.currency}
                    </span>
                  </div>
                </div>

                <div className="rounded-full overflow-hidden" style={{ height: 6, background: 'var(--color-track)' }}>
                  <div
                    style={{
                      width: `${progress}%`,
                      height: '100%',
                      background: progress >= 100 ? 'var(--color-success)' : 'var(--color-primary)',
                    }}
                  />
                </div>
              </div>
            )
          })}
        </div>
      )}

      {showCreateModal && <CreatePaymentRequestModal orderId={orderId} onClose={() => setShowCreateModal(false)} />}

      {selectedRequest && (
        <PaymentRequestDetailPanel
          orderId={orderId}
          request={selectedRequest}
          canEdit={canEdit}
          orderCurrency={orderCurrency}
          onClose={() => setSelectedRequestId(null)}
        />
      )}
    </div>
  )
}
