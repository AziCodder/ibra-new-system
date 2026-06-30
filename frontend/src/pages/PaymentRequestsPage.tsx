import { useState } from 'react'
import { Link } from 'react-router-dom'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import {
  fetchAllPaymentRequests,
  type PaymentRequestSummary,
  type PaymentRequestPriority,
} from '../api/paymentRequests'
import { fetchClients } from '../api/clients'
import { fetchUsers } from '../api/users'
import { useAuth } from '../contexts/AuthContext'
import PaymentRequestDetailPanel from '../components/PaymentRequestDetailPanel'
const PRIORITY_LABELS: Record<PaymentRequestPriority, string> = {
  low: 'Низкий',
  normal: 'Обычно',
  urgent: 'Срочно',
}

const PRIORITY_STYLE: Record<PaymentRequestPriority, { bg: string; color: string }> = {
  low: { bg: 'var(--color-surface-3)', color: 'var(--color-muted)' },
  normal: { bg: 'var(--color-primary-bg)', color: 'var(--color-primary)' },
  urgent: { bg: 'var(--color-danger-bg)', color: 'var(--color-danger)' },
}

function formatNum(v: string | number) {
  return Number(v).toLocaleString('ru-RU', { maximumFractionDigits: 2 })
}

export default function PaymentRequestsPage() {
  const { user } = useAuth()
  const queryClient = useQueryClient()

  const [clientId, setClientId] = useState<number | undefined>()
  const [managerId, setManagerId] = useState<number | undefined>()
  const [sort, setSort] = useState<'asc' | 'desc'>('desc')
  const [selected, setSelected] = useState<PaymentRequestSummary | null>(null)

  const { data: requests, isLoading } = useQuery({
    queryKey: ['all-payment-requests', clientId, managerId, sort],
    queryFn: () => fetchAllPaymentRequests({ client_id: clientId, manager_id: managerId, sort }),
  })

  const { data: clients } = useQuery({
    queryKey: ['clients'],
    queryFn: fetchClients,
  })

  const { data: users } = useQuery({
    queryKey: ['users'],
    queryFn: fetchUsers,
    enabled: user?.role === 'admin' || user?.role === 'observer',
  })

  const managers = users?.filter((u) => u.role === 'manager' || u.role === 'admin') ?? []

  function canEdit(req: PaymentRequestSummary): boolean {
    if (!user) return false
    if (user.role === 'admin') return true
    if (user.role === 'manager') return user.id === req.manager_id
    return false
  }

  return (
    <div className="p-6 max-w-screen-xl mx-auto">
      <div className="flex items-center justify-between mb-6 flex-wrap gap-3">
        <h1 className="text-xl font-extrabold" style={{ color: 'var(--color-text)' }}>
          Запросы на оплату
        </h1>

        <div className="flex items-center gap-3 flex-wrap">
          {(user?.role === 'admin' || user?.role === 'observer') && (
            <select
              value={managerId ?? ''}
              onChange={(e) => setManagerId(e.target.value ? Number(e.target.value) : undefined)}
              className="rounded-lg px-3 py-2 text-sm outline-none"
              style={{ background: 'var(--color-surface-2)', border: '1px solid var(--color-border)', color: 'var(--color-text)' }}
            >
              <option value="">Все менеджеры</option>
              {managers.map((m) => (
                <option key={m.id} value={m.id}>{m.full_name}</option>
              ))}
            </select>
          )}

          <select
            value={clientId ?? ''}
            onChange={(e) => setClientId(e.target.value ? Number(e.target.value) : undefined)}
            className="rounded-lg px-3 py-2 text-sm outline-none"
            style={{ background: 'var(--color-surface-2)', border: '1px solid var(--color-border)', color: 'var(--color-text)' }}
          >
            <option value="">Все клиенты</option>
            {clients?.map((c) => (
              <option key={c.id} value={c.id}>{c.full_name}</option>
            ))}
          </select>

          <button
            onClick={() => setSort((s) => (s === 'desc' ? 'asc' : 'desc'))}
            className="rounded-lg px-3 py-2 text-sm cursor-pointer"
            style={{ background: 'var(--color-surface-2)', border: '1px solid var(--color-border)', color: 'var(--color-text)' }}
          >
            Дата {sort === 'desc' ? '↓' : '↑'}
          </button>
        </div>
      </div>

      {isLoading && (
        <div className="text-sm" style={{ color: 'var(--color-muted)' }}>Загрузка...</div>
      )}

      {!isLoading && (!requests || requests.length === 0) && (
        <div
          className="rounded-2xl p-12 text-center"
          style={{ background: 'var(--color-surface)', border: '1px solid var(--color-border)' }}
        >
          <div className="text-4xl mb-3">💳</div>
          <div className="text-sm" style={{ color: 'var(--color-muted)' }}>Запросов на оплату нет</div>
        </div>
      )}

      {!isLoading && requests && requests.length > 0 && (
        <div
          className="rounded-2xl overflow-hidden"
          style={{ border: '1px solid var(--color-border)' }}
        >
          <table className="w-full text-sm border-collapse">
            <thead>
              <tr style={{ background: 'var(--color-surface-2)' }}>
                {['№ заказа', 'Клиент', 'Менеджер', 'Дата', 'Сумма', 'Остаток', 'Приоритет'].map((h) => (
                  <th
                    key={h}
                    className="px-4 py-3 text-left font-semibold"
                    style={{ color: 'var(--color-muted)', borderBottom: '1px solid var(--color-border)' }}
                  >
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {requests.map((req) => {
                const isSelected = selected?.id === req.id
                const priorityStyle = PRIORITY_STYLE[req.priority]
                return (
                  <tr
                    key={req.id}
                    onClick={() => setSelected(isSelected ? null : req)}
                    className="cursor-pointer transition-colors"
                    style={{
                      background: isSelected ? 'var(--color-primary-bg)' : 'var(--color-surface)',
                      borderBottom: '1px solid var(--color-border)',
                    }}
                    onMouseEnter={(e) => {
                      if (!isSelected) (e.currentTarget as HTMLTableRowElement).style.background = 'var(--color-surface-2)'
                    }}
                    onMouseLeave={(e) => {
                      if (!isSelected) (e.currentTarget as HTMLTableRowElement).style.background = 'var(--color-surface)'
                    }}
                  >
                    <td className="px-4 py-3 font-bold" style={{ color: 'var(--color-primary)' }}>
                      <Link
                        to={`/orders/${req.order_id}`}
                        onClick={(e) => e.stopPropagation()}
                        style={{ color: 'var(--color-primary)' }}
                      >
                        {req.order_number}
                      </Link>
                    </td>
                    <td className="px-4 py-3" style={{ color: 'var(--color-text)' }}>{req.client_name}</td>
                    <td className="px-4 py-3" style={{ color: 'var(--color-muted)' }}>{req.manager_name}</td>
                    <td className="px-4 py-3 whitespace-nowrap" style={{ color: 'var(--color-muted)' }}>
                      {new Date(req.created_at).toLocaleDateString('ru-RU', { day: '2-digit', month: 'short', year: '2-digit' })}
                    </td>
                    <td className="px-4 py-3 whitespace-nowrap" style={{ color: 'var(--color-text)', fontVariantNumeric: 'tabular-nums' }}>
                      {formatNum(req.total_amount)} {req.currency}
                    </td>
                    <td className="px-4 py-3 whitespace-nowrap" style={{ color: Number(req.remaining_amount) > 0 ? 'var(--color-danger)' : 'var(--color-success)', fontVariantNumeric: 'tabular-nums' }}>
                      {formatNum(req.remaining_amount)} {req.currency}
                    </td>
                    <td className="px-4 py-3">
                      <span
                        className="text-xs font-semibold rounded-full px-2.5 py-1"
                        style={{ background: priorityStyle.bg, color: priorityStyle.color }}
                      >
                        {PRIORITY_LABELS[req.priority]}
                      </span>
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      )}

      {selected && (
        <PaymentRequestDetailPanel
          orderId={selected.order_id}
          request={selected}
          canEdit={canEdit(selected)}
          orderCurrency={selected.order_currency}
          onClose={() => setSelected(null)}
          onMutate={() => {
            queryClient.invalidateQueries({ queryKey: ['all-payment-requests'] })
            setSelected(null)
          }}
        />
      )}
    </div>
  )
}