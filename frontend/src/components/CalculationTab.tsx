import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { cancelCalculation, fetchCalculation, type Calculation } from '../api/calculation'
import CalculationModal from './CalculationModal'
import ErrorState from './ErrorState'
import Skeleton from './Skeleton'
import Tag from './Tag'

function formatMoney(value: string | number): string {
  return Number(value).toLocaleString('ru-RU', { maximumFractionDigits: 2 })
}

const cardStyle = {
  background: 'var(--color-surface)',
  border: '1px solid var(--color-border)',
  boxShadow: 'var(--shadow-card)',
}

export default function CalculationTab({
  orderId,
  orderNumber,
  isAdmin,
}: {
  orderId: number
  orderNumber: string
  isAdmin: boolean
}) {
  const queryClient = useQueryClient()
  const [showModal, setShowModal] = useState(false)
  const [error, setError] = useState('')

  const { data, isLoading, isError, refetch } = useQuery({
    queryKey: ['calculation', orderId],
    queryFn: () => fetchCalculation(orderId),
  })

  const cancelMutation = useMutation({
    mutationFn: () => cancelCalculation(orderId),
    onSuccess: () => window.location.reload(),
    onError: (err: Error) => setError(err.message),
  })

  function confirmCancel() {
    if (window.confirm('Отменить расчёт? Данные расчёта будут удалены, а заказ снова станет доступен для изменений.')) {
      cancelMutation.mutate()
    }
  }

  function handleSaved(calculation: Calculation) {
    queryClient.setQueryData(['calculation', orderId], calculation)
    queryClient.invalidateQueries({ queryKey: ['order', orderId] })
    queryClient.invalidateQueries({ queryKey: ['orders'] })
    setShowModal(false)
  }

  if (isLoading) return <Skeleton height={160} radius={10} />
  if (isError || !data) return <ErrorState message="Не удалось загрузить расчёт" onRetry={() => refetch()} />

  if (!data.is_calculated) {
    return (
      <div className="rounded-[10px] p-6" style={cardStyle}>
        <div className="text-sm font-semibold mb-1" style={{ color: 'var(--color-text)' }}>Заказ пока не рассчитан</div>
        {isAdmin && (
          data.is_ready && data.profit != null ? (
            <>
              <div className="text-sm mb-4" style={{ color: 'var(--color-muted)' }}>
                Общая прибыль — {formatMoney(data.profit)} {data.currency}. Распределите её между участниками,
                после сохранения заказ будет заморожен.
              </div>
              <button
                onClick={() => setShowModal(true)}
                className="rounded-lg px-4 py-2 text-sm font-medium cursor-pointer"
                style={{ background: 'var(--color-primary)', color: '#fff' }}
              >
                Рассчитать
              </button>
            </>
          ) : (
            <div className="text-sm" style={{ color: 'var(--color-warning)' }}>
              Рассчитать можно после приёмки всей логистики и полной оплаты всех товаров.
            </div>
          )
        )}

        {showModal && data.profit != null && (
          <CalculationModal
            orderId={orderId}
            orderNumber={orderNumber}
            profit={data.profit}
            currency={data.currency}
            onClose={() => setShowModal(false)}
            onSaved={handleSaved}
          />
        )}
      </div>
    )
  }

  const calculatedAt = data.calculated_at
    ? new Date(data.calculated_at).toLocaleString('ru-RU', { day: '2-digit', month: 'long', year: 'numeric', hour: '2-digit', minute: '2-digit' })
    : ''

  return (
    <div>
      {error && (
        <div className="rounded-lg px-3 py-2 mb-3 text-sm" style={{ background: 'var(--color-danger-bg)', color: 'var(--color-danger)' }}>
          {error}
        </div>
      )}

      <div className="rounded-[10px] overflow-hidden" style={cardStyle}>
        <div className="flex items-start justify-between gap-3 flex-wrap p-4" style={{ borderBottom: '1px solid var(--color-border)' }}>
          <div>
            <div className="text-xs mb-1" style={{ color: 'var(--color-faint)' }}>Общая прибыль</div>
            <div className="text-lg font-semibold" style={{ color: 'var(--color-success)', fontVariantNumeric: 'tabular-nums' }}>
              {formatMoney(data.profit ?? 0)} {data.currency}
            </div>
          </div>
          <div className="flex flex-col items-end gap-1">
            <Tag color="green">Рассчитан</Tag>
            {calculatedAt && <span className="text-xs" style={{ color: 'var(--color-muted)' }}>{calculatedAt}</span>}
          </div>
        </div>

        <table className="rtable w-full text-sm" style={{ borderCollapse: 'collapse' }}>
          <thead>
            <tr style={{ background: 'var(--color-surface-2)' }}>
              <th className="text-left px-4 py-2.5 text-xs font-semibold uppercase tracking-wide" style={{ color: 'var(--color-muted)' }}>Участник</th>
              <th className="text-right px-4 py-2.5 text-xs font-semibold uppercase tracking-wide" style={{ color: 'var(--color-muted)' }}>Доля</th>
              <th className="text-right px-4 py-2.5 text-xs font-semibold uppercase tracking-wide" style={{ color: 'var(--color-muted)' }}>Сумма</th>
            </tr>
          </thead>
          <tbody>
            {data.participants.map((p) => (
              <tr key={p.user_id} style={{ borderTop: '1px solid var(--color-border)' }}>
                <td className="px-4 py-2.5" data-label="Участник" style={{ color: 'var(--color-text)' }}>{p.full_name}</td>
                <td className="px-4 py-2.5 text-right" data-label="Доля" style={{ color: 'var(--color-text)', fontVariantNumeric: 'tabular-nums' }}>
                  {formatMoney(p.percent)}%
                </td>
                <td className="px-4 py-2.5 text-right font-medium" data-label="Сумма" style={{ color: 'var(--color-text)', fontVariantNumeric: 'tabular-nums' }}>
                  {formatMoney(p.amount)} {data.currency}
                </td>
              </tr>
            ))}
          </tbody>
          <tfoot>
            <tr style={{ borderTop: '2px solid var(--color-border)', background: 'var(--color-surface-2)' }}>
              <td className="px-4 py-2.5 font-semibold" style={{ color: 'var(--color-text)' }}>Итого</td>
              <td className="px-4 py-2.5 text-right font-semibold" data-label="Доля" style={{ color: 'var(--color-text)' }}>100%</td>
              <td className="px-4 py-2.5 text-right font-semibold" data-label="Сумма" style={{ color: 'var(--color-text)', fontVariantNumeric: 'tabular-nums' }}>
                {formatMoney(data.profit ?? 0)} {data.currency}
              </td>
            </tr>
          </tfoot>
        </table>
      </div>

      {isAdmin && (
        <div className="flex justify-end mt-3">
          <button
            onClick={confirmCancel}
            disabled={cancelMutation.isPending}
            className="rounded-lg px-4 py-2 text-sm font-medium cursor-pointer disabled:opacity-50"
            style={{ background: 'var(--color-danger-bg)', color: 'var(--color-danger)' }}
          >
            {cancelMutation.isPending ? 'Отмена расчёта...' : 'Отменить расчёт'}
          </button>
        </div>
      )}
    </div>
  )
}
