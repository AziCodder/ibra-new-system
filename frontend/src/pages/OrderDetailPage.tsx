import { useParams, useNavigate } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { fetchOrder, type OrderStatus } from '../api/orders'

const STATUS_BADGE: Record<OrderStatus, { label: string; bg: string; color: string }> = {
  in_progress: { label: 'В работе', bg: 'var(--color-success-bg)', color: 'var(--color-success)' },
  completed: { label: 'Завершён', bg: 'var(--color-primary-bg)', color: 'var(--color-primary)' },
  cancelled: { label: 'Отменён', bg: 'var(--color-danger-bg)', color: 'var(--color-danger)' },
}

export default function OrderDetailPage() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const orderId = Number(id)

  const { data: order, isLoading, isError } = useQuery({
    queryKey: ['order', orderId],
    queryFn: () => fetchOrder(orderId),
    enabled: !Number.isNaN(orderId),
  })

  if (isLoading) {
    return <div className="p-6" style={{ color: 'var(--color-muted)' }}>Загрузка...</div>
  }

  if (isError || !order) {
    return (
      <div className="p-6">
        <p style={{ color: 'var(--color-danger)' }}>Заказ не найден</p>
        <button onClick={() => navigate('/')} className="mt-3 text-sm cursor-pointer" style={{ color: 'var(--color-primary)' }}>
          ← Назад к заказам
        </button>
      </div>
    )
  }

  const badge = STATUS_BADGE[order.status]
  const date = new Date(order.created_at).toLocaleDateString('ru-RU', { day: '2-digit', month: 'long', year: 'numeric' })

  return (
    <div className="p-6">
      <button onClick={() => navigate('/')} className="text-sm mb-4 cursor-pointer" style={{ color: 'var(--color-primary)' }}>
        ← Назад к заказам
      </button>

      <div className="flex items-center justify-between mb-2">
        <div className="flex items-center gap-3">
          <span className="text-xs" style={{ color: 'var(--color-faint)' }}>№{order.id}</span>
          <h2 className="text-xl font-bold" style={{ color: 'var(--color-text)' }}>{order.number}</h2>
        </div>
        <span className="text-xs font-semibold rounded-full px-2.5 py-1" style={{ background: badge.bg, color: badge.color }}>
          {badge.label}
        </span>
      </div>

      <div className="flex gap-3 text-sm flex-wrap mb-6" style={{ color: 'var(--color-muted)' }}>
        <span>{order.client_name}</span>
        <span>·</span>
        <span>{order.manager_name}</span>
        <span>·</span>
        <span>{date}</span>
        <span>·</span>
        <span>{order.currency}</span>
      </div>

      {order.details && (
        <div
          className="rounded-xl p-4 text-sm"
          style={{ background: 'var(--color-surface)', border: '1px solid var(--color-border)', color: 'var(--color-text)' }}
        >
          {order.details}
        </div>
      )}
    </div>
  )
}
