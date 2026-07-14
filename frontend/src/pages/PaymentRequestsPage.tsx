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
import ErrorState from '../components/ErrorState'
import Skeleton from '../components/Skeleton'
import Tag, { type TagColor } from '../components/Tag'
import PageHeader from '../components/PageHeader'
import SearchInput from '../components/SearchInput'

const PRIORITY_LABELS: Record<PaymentRequestPriority, string> = {
  low: 'Низкий',
  normal: 'Обычно',
  urgent: 'Срочно',
}

const PRIORITY_COLOR: Record<PaymentRequestPriority, TagColor> = {
  low: 'default',
  normal: 'blue',
  urgent: 'red',
}

function formatNum(v: string | number) {
  return Number(v).toLocaleString('ru-RU', { maximumFractionDigits: 2 })
}

export default function PaymentRequestsPage() {
  const { user } = useAuth()
  const queryClient = useQueryClient()

  const [clientId, setClientId] = useState<number | undefined>()
  const [managerId, setManagerId] = useState<number | undefined>()
  const [search, setSearch] = useState('')
  const [sort, setSort] = useState<'asc' | 'desc'>('desc')
  const [selected, setSelected] = useState<PaymentRequestSummary | null>(null)

  const { data: requests, isLoading, isError, refetch } = useQuery({
    queryKey: ['all-payment-requests', clientId, managerId, search, sort],
    queryFn: () => fetchAllPaymentRequests({ client_id: clientId, manager_id: managerId, search: search || undefined, sort }),
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
    <div className="p-4 sm:p-6 max-w-screen-xl mx-auto">
      <PageHeader title="Запросы на оплату" subtitle="Все запросы по всем заказам">
        <SearchInput
          value={search}
          onChange={setSearch}
          placeholder="Поиск по номеру заказа, клиенту..."
          className="flex-1 sm:flex-initial sm:w-64"
        />
      </PageHeader>

      <div className="flex flex-col sm:flex-row items-stretch sm:items-center flex-wrap gap-3 mb-6">
          {(user?.role === 'admin' || user?.role === 'observer') && (
            <select
              value={managerId ?? ''}
              onChange={(e) => setManagerId(e.target.value ? Number(e.target.value) : undefined)}
              className="text-sm outline-none w-full sm:w-auto px-3"
              style={{ height: 32, background: 'var(--color-surface)', border: '1px solid var(--color-border)', borderRadius: 'var(--radius)', color: 'var(--color-text)' }}
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
            className="text-sm outline-none w-full sm:w-auto px-3"
            style={{ height: 32, background: 'var(--color-surface)', border: '1px solid var(--color-border)', borderRadius: 'var(--radius)', color: 'var(--color-text)' }}
          >
            <option value="">Все клиенты</option>
            {clients?.map((c) => (
              <option key={c.id} value={c.id}>{c.full_name}</option>
            ))}
          </select>

          <button
            onClick={() => setSort((s) => (s === 'desc' ? 'asc' : 'desc'))}
            className="text-sm cursor-pointer w-full sm:w-auto px-3"
            style={{ height: 32, background: 'var(--color-surface)', border: '1px solid var(--color-border)', borderRadius: 'var(--radius)', color: 'var(--color-text)' }}
          >
            Дата {sort === 'desc' ? '↓' : '↑'}
          </button>
      </div>

      {isLoading && (
        <div className="flex flex-col gap-2">
          {Array.from({ length: 5 }).map((_, i) => (
            <Skeleton key={i} height={72} radius={14} />
          ))}
        </div>
      )}

      {!isLoading && isError && (
        <ErrorState message="Не удалось загрузить запросы на оплату" onRetry={() => refetch()} />
      )}

      {!isLoading && !isError && (!requests || requests.length === 0) && (
        <div
          className="rounded-[10px] p-12 text-center"
          style={{ background: 'var(--color-surface)', border: '1px solid var(--color-card-border)' }}
        >
          <div className="mb-3" style={{ color: 'var(--color-faint)' }}><svg xmlns="http://www.w3.org/2000/svg" width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"><rect width="20" height="14" x="2" y="5" rx="2"/><line x1="2" x2="22" y1="10" y2="10"/></svg></div>
          <div className="text-sm" style={{ color: 'var(--color-muted)' }}>Запросов на оплату нет</div>
        </div>
      )}

      {!isLoading && requests && requests.length > 0 && (
        <div
          className="rounded-[10px] overflow-x-auto"
          style={{ border: '1px solid var(--color-card-border)', background: 'var(--color-surface)' }}
        >
          <table className="rtable w-full text-sm border-collapse">
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
                    <td className="px-4 py-3 font-bold" data-label="№ заказа" style={{ color: 'var(--color-primary)' }}>
                      <Link
                        to={`/orders/${req.order_id}`}
                        onClick={(e) => e.stopPropagation()}
                        style={{ color: 'var(--color-primary)' }}
                      >
                        {req.order_number}
                      </Link>
                    </td>
                    <td className="px-4 py-3" data-label="Клиент" style={{ color: 'var(--color-text)' }}>{req.client_name}</td>
                    <td className="px-4 py-3" data-label="Менеджер" style={{ color: 'var(--color-muted)' }}>{req.manager_name}</td>
                    <td className="px-4 py-3 whitespace-nowrap" data-label="Дата" style={{ color: 'var(--color-muted)' }}>
                      {new Date(req.created_at).toLocaleDateString('ru-RU', { day: '2-digit', month: 'short', year: '2-digit' })}
                    </td>
                    <td className="px-4 py-3 whitespace-nowrap" data-label="Сумма" style={{ color: 'var(--color-text)', fontVariantNumeric: 'tabular-nums' }}>
                      {formatNum(req.total_amount)} {req.currency}
                    </td>
                    <td className="px-4 py-3 whitespace-nowrap" data-label="Остаток" style={{ color: Number(req.remaining_amount) > 0 ? 'var(--color-danger)' : 'var(--color-success)', fontVariantNumeric: 'tabular-nums' }}>
                      {formatNum(req.remaining_amount)} {req.currency}
                    </td>
                    <td className="px-4 py-3" data-label="Приоритет">
                      <Tag color={PRIORITY_COLOR[req.priority]}>{PRIORITY_LABELS[req.priority]}</Tag>
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