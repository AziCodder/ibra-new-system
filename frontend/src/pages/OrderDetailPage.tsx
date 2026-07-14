import { useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { fetchOrder, setOrderStatus, type OrderStatus } from '../api/orders'
import NotesSection from '../components/NotesSection'
import ProductsTable from '../components/ProductsTable'
import PaymentRequestsTab from '../components/PaymentRequestsTab'
import LogisticsTab from '../components/LogisticsTab'
import LedgerTab from '../components/LedgerTab'
import { useAuth } from '../contexts/AuthContext'
import ProfitBlock from '../components/ProfitBlock'
import Skeleton from '../components/Skeleton'
import ErrorState from '../components/ErrorState'
import Tag, { type TagColor } from '../components/Tag'

const STATUS_BADGE: Record<OrderStatus, { label: string; color: TagColor }> = {
  in_progress: { label: 'В работе', color: 'green' },
  completed: { label: 'Завершён', color: 'blue' },
  cancelled: { label: 'Отменён', color: 'red' },
}

type TabKey = 'items' | 'payments' | 'logistics' | 'finance'

const TABS: { key: TabKey; label: string }[] = [
  { key: 'items', label: 'Товары' },
  { key: 'payments', label: 'Запросы на оплату' },
  { key: 'logistics', label: 'Логистика' },
  { key: 'finance', label: 'ДиР' },
]

export default function OrderDetailPage() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const { user } = useAuth()
  const orderId = Number(id)
  const [activeTab, setActiveTab] = useState<TabKey>('items')
  const queryClient = useQueryClient()

  const { data: order, isLoading, isError, refetch } = useQuery({
    queryKey: ['order', orderId],
    queryFn: () => fetchOrder(orderId),
    enabled: !Number.isNaN(orderId),
  })

  const statusMutation = useMutation({
    mutationFn: (status: OrderStatus) => setOrderStatus(orderId, status),
    onMutate: async (status) => {
      await queryClient.cancelQueries({ queryKey: ['order', orderId] })
      const previous = queryClient.getQueryData<Awaited<ReturnType<typeof fetchOrder>>>(['order', orderId])
      if (previous) {
        queryClient.setQueryData(['order', orderId], { ...previous, status })
      }
      return { previous }
    },
    onError: (_err, _status, ctx) => {
      if (ctx?.previous) queryClient.setQueryData(['order', orderId], ctx.previous)
    },
    onSuccess: (updated) => {
      queryClient.setQueryData(['order', orderId], updated)
    },
  })

  if (isLoading) {
    return (
      <div className="p-6 flex flex-col gap-4">
        <Skeleton width={140} height={14} />
        <Skeleton width="60%" height={28} />
        <Skeleton width="45%" height={14} />
        <div className="flex gap-3 mt-2">
          <Skeleton width={90} height={32} />
          <Skeleton width={90} height={32} />
          <Skeleton width={90} height={32} />
        </div>
        <Skeleton width="100%" height={180} radius={14} style={{ marginTop: 12 }} />
      </div>
    )
  }

  if (isError || !order) {
    return (
      <div className="p-4 sm:p-6">
        <ErrorState
          message={isError ? 'Не удалось загрузить заказ' : 'Заказ не найден'}
          onRetry={isError ? () => refetch() : undefined}
        />
        <button onClick={() => navigate('/')} className="mt-3 text-sm cursor-pointer" style={{ color: 'var(--color-primary)' }}>
          ← Назад к заказам
        </button>
      </div>
    )
  }

  const badge = STATUS_BADGE[order.status]
  const date = new Date(order.created_at).toLocaleDateString('ru-RU', { day: '2-digit', month: 'long', year: 'numeric' })
  const canEdit = !!user && (user.role === 'admin' || (user.role === 'manager' && user.id === order.manager_id))

  return (
    <div className="p-4 sm:p-6">
      <button onClick={() => navigate('/')} className="text-sm mb-4 cursor-pointer" style={{ color: 'var(--color-primary)' }}>
        ← Назад к заказам
      </button>

      <div className="flex items-center justify-between gap-3 flex-wrap mb-2">
        <div className="flex items-center gap-3 min-w-0">
          <span className="text-xs flex-shrink-0" style={{ color: 'var(--color-faint)' }}>№{order.id}</span>
          <h1 className="text-xl sm:text-2xl font-bold truncate" style={{ color: 'var(--color-text)' }}>{order.number}</h1>
        </div>
        <Tag color={badge.color}>{badge.label}</Tag>
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

      {/* Status actions */}
      {user && user.role !== 'observer' && (() => {
        const isAdmin = user.role === 'admin'
        const isOwner = user.role === 'manager' && user.id === order.manager_id
        const busy = statusMutation.isPending
        const actions: { label: string; status: OrderStatus; style: 'danger' | 'success' | 'ghost' }[] = []

        if (order.status === 'in_progress') {
          if (isAdmin) actions.push({ label: 'Завершить', status: 'completed', style: 'success' })
          if (isAdmin || isOwner) actions.push({ label: 'Отменить', status: 'cancelled', style: 'danger' })
        }
        if (order.status === 'cancelled' && isAdmin) {
          actions.push({ label: 'Вернуть в работу', status: 'in_progress', style: 'ghost' })
        }
        if (order.status === 'completed' && isAdmin) {
          actions.push({ label: 'Вернуть в работу', status: 'in_progress', style: 'ghost' })
        }

        if (actions.length === 0) return null
        return (
          <div className="flex items-center gap-2 flex-wrap mb-4">
            {actions.map((a) => (
              <button
                key={a.status}
                disabled={busy}
                onClick={() => statusMutation.mutate(a.status)}
                className="text-xs font-medium px-3 py-1.5 rounded-lg cursor-pointer transition-opacity disabled:opacity-50"
                style={{
                  background: a.style === 'success' ? 'var(--color-success-bg)' : a.style === 'danger' ? 'var(--color-danger-bg)' : 'var(--color-surface-2)',
                  color: a.style === 'success' ? 'var(--color-success)' : a.style === 'danger' ? 'var(--color-danger)' : 'var(--color-muted)',
                  border: '1px solid transparent',
                }}
              >
                {a.label}
              </button>
            ))}
          </div>
        )
      })()}

      {order.details && (
        <div
          className="rounded-[8px] p-4 text-sm mb-6"
          style={{ background: 'var(--color-surface)', border: '1px solid var(--color-border)', color: 'var(--color-text)' }}
        >
          {order.details}
        </div>
      )}

      <ProfitBlock orderId={orderId} />

      <div className="flex gap-1 overflow-x-auto mb-5" style={{ borderBottom: '1px solid var(--color-border)' }}>
        {TABS.map((tab) => (
          <button
            key={tab.key}
            onClick={() => setActiveTab(tab.key)}
            className="px-4 py-3 text-sm font-medium cursor-pointer whitespace-nowrap transition-colors"
            style={{
              color: activeTab === tab.key ? 'var(--color-primary)' : 'var(--color-muted)',
              borderBottom: activeTab === tab.key ? '2px solid var(--color-primary)' : '2px solid transparent',
              marginBottom: -1,
            }}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {activeTab === 'items' && <ProductsTable orderId={order.id} canEdit={canEdit} />}
      {activeTab === 'payments' && <PaymentRequestsTab orderId={order.id} canEdit={canEdit} orderCurrency={order.currency} />}
      {activeTab === 'logistics' && (
        <LogisticsTab orderId={order.id} orderNumber={order.number} canEdit={canEdit} isAdmin={user?.role === 'admin'} />
      )}
      {activeTab === 'finance' && <LedgerTab orderId={order.id} canEdit={canEdit} orderCurrency={order.currency} />}

      <NotesSection orderId={order.id} />
    </div>
  )
}
