import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { fetchOrders, type OrderStatus } from '../api/orders'
import { fetchClients } from '../api/clients'

const STATUS_CHIPS: { key: OrderStatus | 'all'; label: string }[] = [
  { key: 'in_progress', label: 'В работе' },
  { key: 'completed', label: 'Завершённые' },
  { key: 'all', label: 'Все' },
]

const STATUS_BADGE: Record<OrderStatus, { label: string; bg: string; color: string }> = {
  in_progress: { label: 'В работе', bg: 'var(--color-success-bg)', color: 'var(--color-success)' },
  completed: { label: 'Завершён', bg: 'var(--color-primary-bg)', color: 'var(--color-primary)' },
  cancelled: { label: 'Отменён', bg: 'var(--color-danger-bg)', color: 'var(--color-danger)' },
}

function OrderCard({ order }: { order: import('../api/orders').Order }) {
  const badge = STATUS_BADGE[order.status]
  const date = new Date(order.created_at).toLocaleDateString('ru-RU', { day: '2-digit', month: 'short' })

  return (
    <div
      className="rounded-2xl p-4 flex flex-col gap-3 transition-transform"
      style={{ background: 'var(--color-surface)', border: '1px solid var(--color-border)' }}
    >
      <div className="flex items-center justify-between">
        <span className="text-base font-extrabold" style={{ color: 'var(--color-primary)' }}>{order.number}</span>
        <span
          className="text-xs font-semibold rounded-full px-2.5 py-1"
          style={{ background: badge.bg, color: badge.color }}
        >
          {badge.label}
        </span>
      </div>
      <div className="text-sm font-bold" style={{ color: 'var(--color-text)' }}>{order.client_name}</div>
      <div className="flex gap-2 text-xs flex-wrap" style={{ color: 'var(--color-muted)' }}>
        <span>📅 {date}</span>
        <span>·</span>
        <span>👤 {order.manager_name}</span>
        <span>·</span>
        <span>{order.currency}</span>
      </div>
      {order.details && (
        <>
          <div style={{ height: 1, background: 'var(--color-border)' }} />
          <div className="text-xs" style={{ color: 'var(--color-muted)' }}>{order.details}</div>
        </>
      )}
    </div>
  )
}

export default function OrdersPage() {
  const [statusFilter, setStatusFilter] = useState<OrderStatus | 'all'>('all')
  const [clientId, setClientId] = useState<number | undefined>(undefined)
  const [page, setPage] = useState(1)
  const pageSize = 12

  const { data: clients } = useQuery({ queryKey: ['clients'], queryFn: fetchClients })

  const { data, isLoading } = useQuery({
    queryKey: ['orders', statusFilter, clientId, page],
    queryFn: () =>
      fetchOrders({
        status: statusFilter === 'all' ? undefined : statusFilter,
        client_id: clientId,
        page,
        page_size: pageSize,
      }),
  })

  const totalPages = data ? Math.max(1, Math.ceil(data.total / pageSize)) : 1

  function selectStatus(key: OrderStatus | 'all') {
    setStatusFilter(key)
    setPage(1)
  }

  return (
    <div className="p-6">
      <div className="flex items-center justify-between mb-6">
        <h2 className="text-lg font-semibold" style={{ color: 'var(--color-text)' }}>Заказы</h2>
      </div>

      <div className="flex items-center gap-3 mb-5 flex-wrap">
        <div className="flex gap-1 p-1 rounded-lg" style={{ background: 'var(--color-surface-2)' }}>
          {STATUS_CHIPS.map((chip) => (
            <button
              key={chip.key}
              onClick={() => selectStatus(chip.key)}
              className="px-3 py-1.5 text-sm rounded-md cursor-pointer transition-colors"
              style={{
                background: statusFilter === chip.key ? 'var(--color-primary)' : 'transparent',
                color: statusFilter === chip.key ? '#fff' : 'var(--color-muted)',
                fontWeight: statusFilter === chip.key ? 600 : 400,
              }}
            >
              {chip.label}
            </button>
          ))}
        </div>

        <select
          value={clientId ?? ''}
          onChange={(e) => { setClientId(e.target.value ? Number(e.target.value) : undefined); setPage(1) }}
          className="rounded-lg px-3 py-2 text-sm outline-none"
          style={{ background: 'var(--color-surface-2)', border: '1px solid var(--color-border)', color: 'var(--color-text)' }}
        >
          <option value="">Клиент: все</option>
          {clients?.map((c) => (
            <option key={c.id} value={c.id}>{c.code} — {c.full_name}</option>
          ))}
        </select>

        {data && (
          <span className="ml-auto text-xs" style={{ color: 'var(--color-muted)' }}>
            Показано {data.items.length} из {data.total}
          </span>
        )}
      </div>

      {isLoading ? (
        <p style={{ color: 'var(--color-muted)' }}>Загрузка...</p>
      ) : !data || data.items.length === 0 ? (
        <div
          className="rounded-2xl p-12 text-center"
          style={{ background: 'var(--color-surface)', border: '1px dashed var(--color-border)', color: 'var(--color-muted)' }}
        >
          Заказов не найдено
        </div>
      ) : (
        <div
          className="grid gap-4"
          style={{ gridTemplateColumns: 'repeat(auto-fill, minmax(300px, 1fr))' }}
        >
          {data.items.map((order) => (
            <OrderCard key={order.id} order={order} />
          ))}
        </div>
      )}

      {totalPages > 1 && (
        <div className="flex items-center justify-center gap-2 mt-6">
          <button
            onClick={() => setPage((p) => Math.max(1, p - 1))}
            disabled={page <= 1}
            className="rounded-lg px-3 py-1.5 text-sm cursor-pointer disabled:opacity-40"
            style={{ background: 'var(--color-surface-2)', color: 'var(--color-text)' }}
          >
            ‹
          </button>
          <span className="text-sm" style={{ color: 'var(--color-muted)' }}>
            {page} / {totalPages}
          </span>
          <button
            onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
            disabled={page >= totalPages}
            className="rounded-lg px-3 py-1.5 text-sm cursor-pointer disabled:opacity-40"
            style={{ background: 'var(--color-surface-2)', color: 'var(--color-text)' }}
          >
            ›
          </button>
        </div>
      )}
    </div>
  )
}
