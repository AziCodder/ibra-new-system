import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { useNavigate } from 'react-router-dom'
import { fetchOrders, fetchOrderStats, type OrderStatus } from '../api/orders'
import { fetchClients } from '../api/clients'
import CreateOrderModal from '../components/CreateOrderModal'
import { useAuth } from '../contexts/AuthContext'
import { SkeletonCardGrid } from '../components/Skeleton'
import ErrorState from '../components/ErrorState'
import Tag, { type TagColor } from '../components/Tag'
import PageHeader from '../components/PageHeader'
import SearchInput from '../components/SearchInput'
import StatCard from '../components/StatCard'
import { Calendar, User, Plus } from 'lucide-react'

const CURRENCY_SYMBOL: Record<string, string> = { RUB: '₽', USD: '$', CNY: '¥', EUR: '€' }

function formatProfitMonth(profitMonth: Record<string, string>): string {
  const entries = Object.entries(profitMonth)
  if (entries.length === 0) return '—'
  const [currency, amount] = entries.reduce((max, cur) => (parseFloat(cur[1]) > parseFloat(max[1]) ? cur : max))
  const symbol = CURRENCY_SYMBOL[currency] ?? currency
  return `${parseFloat(amount).toLocaleString('ru-RU', { maximumFractionDigits: 0 })} ${symbol}`
}

function StatsRow() {
  const { data: stats } = useQuery({ queryKey: ['orders', 'stats'], queryFn: fetchOrderStats })
  if (!stats) return null

  return (
    <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mb-6">
      <StatCard
        label="Всего заказов"
        value={String(stats.total_count)}
        delta={stats.total_count_delta_month > 0 ? `+${stats.total_count_delta_month} за месяц` : undefined}
        tone="positive"
      />
      <StatCard
        label="В работе"
        value={String(stats.in_progress_count)}
        delta={stats.waiting_payment_count > 0 ? `${stats.waiting_payment_count} ждут оплаты` : undefined}
        tone="warning"
      />
      <StatCard
        label="Завершено"
        value={String(stats.completed_count)}
        delta={stats.completed_pct_month != null ? `${stats.completed_pct_month}% за месяц` : undefined}
        tone="positive"
      />
      <StatCard
        label="Прибыль за месяц"
        value={formatProfitMonth(stats.profit_month)}
        delta={stats.profit_month_delta_pct != null ? `${stats.profit_month_delta_pct > 0 ? '+' : ''}${stats.profit_month_delta_pct}%` : undefined}
        tone={stats.profit_month_delta_pct != null && stats.profit_month_delta_pct < 0 ? 'neutral' : 'positive'}
      />
    </div>
  )
}

const STATUS_CHIPS: { key: OrderStatus | 'all'; label: string }[] = [
  { key: 'in_progress', label: 'В работе' },
  { key: 'completed', label: 'Завершённые' },
  { key: 'all', label: 'Все' },
]

const STATUS_BADGE: Record<OrderStatus, { label: string; color: TagColor }> = {
  in_progress: { label: 'В работе', color: 'green' },
  completed: { label: 'Завершён', color: 'blue' },
  cancelled: { label: 'Отменён', color: 'red' },
}

function SegmentedFilter({
  options,
  value,
  onChange,
}: {
  options: { key: OrderStatus | 'all'; label: string }[]
  value: OrderStatus | 'all'
  onChange: (v: OrderStatus | 'all') => void
}) {
  return (
    <div className="inline-flex">
      {options.map((opt, i) => {
        const active = opt.key === value
        const first = i === 0
        const last = i === options.length - 1
        return (
          <button
            key={opt.key}
            onClick={() => onChange(opt.key)}
            className="text-sm cursor-pointer transition-colors px-[15px]"
            style={{
              height: 32,
              background: active ? 'var(--color-primary)' : 'var(--color-surface)',
              color: active ? '#fff' : 'var(--color-text)',
              border: `1px solid ${active ? 'var(--color-primary)' : 'var(--color-border)'}`,
              marginLeft: first ? 0 : -1,
              borderRadius: first ? 'var(--radius) 0 0 var(--radius)' : last ? '0 var(--radius) var(--radius) 0' : 0,
              position: 'relative',
              zIndex: active ? 1 : 0,
            }}
          >
            {opt.label}
          </button>
        )
      })}
    </div>
  )
}

function PaymentProgress({ order }: { order: import('../api/orders').Order }) {
  if (order.requested_amount == null) {
    return <div className="text-xs" style={{ color: 'var(--color-faint)' }}>ждёт счёт</div>
  }

  const requested = parseFloat(order.requested_amount)
  const paid = parseFloat(order.paid_amount ?? '0')
  const progress = requested > 0 ? Math.min(100, (paid / requested) * 100) : 0

  if (paid >= requested) {
    return <div className="text-xs font-medium" style={{ color: 'var(--color-success)' }}>Оплачено полностью</div>
  }

  const remaining = (requested - paid).toLocaleString('ru-RU', { maximumFractionDigits: 2 })

  return (
    <div className="flex flex-col gap-1.5">
      <div className="rounded-full overflow-hidden" style={{ height: 6, background: 'var(--color-track)' }}>
        <div style={{ width: `${progress}%`, height: '100%', background: 'var(--color-primary)' }} />
      </div>
      <div className="text-xs" style={{ color: 'var(--color-muted)' }}>
        Оплачено {Math.round(progress)}% · остаток {remaining} {order.currency}
      </div>
    </div>
  )
}

function OrderCard({ order }: { order: import('../api/orders').Order }) {
  const navigate = useNavigate()
  const badge = STATUS_BADGE[order.status]
  const date = new Date(order.created_at).toLocaleDateString('ru-RU', { day: '2-digit', month: 'short' })

  return (
    <div
      onClick={() => navigate(`/orders/${order.id}`)}
      className="rounded-[10px] p-4 flex flex-col gap-3 transition-transform cursor-pointer"
      style={{ background: 'var(--color-surface)', border: '1px solid var(--color-card-border)' }}
    >
      <div className="flex items-center justify-between">
        <span className="text-base font-extrabold" style={{ color: 'var(--color-primary)' }}>{order.number}</span>
        <Tag color={badge.color}>{badge.label}</Tag>
      </div>
      <div className="text-sm font-bold" style={{ color: 'var(--color-text)' }}>{order.client_name}</div>
      <div className="flex items-center gap-2 text-xs flex-wrap" style={{ color: 'var(--color-muted)' }}>
        <span className="flex items-center gap-1"><Calendar size={12} /> {date}</span>
        <span>·</span>
        <span className="flex items-center gap-1"><User size={12} /> {order.manager_name}</span>
        <span>·</span>
        <span>{order.currency}</span>
      </div>
      {order.details && (
        <>
          <div style={{ height: 1, background: 'var(--color-border)' }} />
          <div className="text-xs" style={{ color: 'var(--color-muted)' }}>{order.details}</div>
        </>
      )}
      <div style={{ height: 1, background: 'var(--color-border)' }} />
      <PaymentProgress order={order} />
    </div>
  )
}

export default function OrdersPage() {
  const [statusFilter, setStatusFilter] = useState<OrderStatus | 'all'>('all')
  const [clientId, setClientId] = useState<number | undefined>(undefined)
  const [search, setSearch] = useState('')
  const [page, setPage] = useState(1)
  const [showCreate, setShowCreate] = useState(false)
  const pageSize = 12
  const { user } = useAuth()
  const canCreate = user?.role !== 'observer'

  const { data: clients } = useQuery({ queryKey: ['clients'], queryFn: fetchClients })

  const { data, isLoading, isError, refetch } = useQuery({
    queryKey: ['orders', statusFilter, clientId, search, page],
    queryFn: () =>
      fetchOrders({
        status: statusFilter === 'all' ? undefined : statusFilter,
        client_id: clientId,
        search: search || undefined,
        page,
        page_size: pageSize,
      }),
  })

  const totalPages = data ? Math.max(1, Math.ceil(data.total / pageSize)) : 1

  function selectStatus(key: OrderStatus | 'all') {
    setStatusFilter(key)
    setPage(1)
  }

  function selectSearch(v: string) {
    setSearch(v)
    setPage(1)
  }

  return (
    <div className="p-4 sm:p-6">
      <PageHeader title="Заказы" subtitle="Управление заказами клиентов">
        <SearchInput value={search} onChange={selectSearch} placeholder="Поиск по номеру, клиенту..." className="flex-1 sm:flex-initial sm:w-64" />
        {canCreate && (
          <button
            onClick={() => setShowCreate(true)}
            className="flex items-center gap-1.5 text-sm cursor-pointer flex-shrink-0"
            style={{ height: 36, padding: '0 15px', background: 'var(--color-primary)', borderRadius: 'var(--radius)', color: '#fff' }}
          >
            <Plus size={15} /> Создать заказ
          </button>
        )}
      </PageHeader>

      <StatsRow />

      {showCreate && <CreateOrderModal onClose={() => setShowCreate(false)} />}

      <div className="flex items-center gap-3 mb-5 flex-wrap">
        <SegmentedFilter options={STATUS_CHIPS} value={statusFilter} onChange={selectStatus} />

        <select
          value={clientId ?? ''}
          onChange={(e) => { setClientId(e.target.value ? Number(e.target.value) : undefined); setPage(1) }}
          className="text-sm outline-none px-3"
          style={{ height: 32, background: 'var(--color-surface)', border: '1px solid var(--color-border)', borderRadius: 'var(--radius)', color: 'var(--color-text)' }}
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
        <SkeletonCardGrid />
      ) : isError ? (
        <ErrorState message="Не удалось загрузить заказы" onRetry={() => refetch()} />
      ) : !data || data.items.length === 0 ? (
        <div
          className="rounded-[10px] p-12 text-center"
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
            className="text-sm cursor-pointer disabled:opacity-40"
            style={{
              width: 32,
              height: 32,
              background: 'var(--color-surface)',
              border: '1px solid var(--color-border)',
              borderRadius: 'var(--radius)',
              color: 'var(--color-text)',
            }}
          >
            ‹
          </button>
          <span className="text-sm" style={{ color: 'var(--color-muted)' }}>
            {page} / {totalPages}
          </span>
          <button
            onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
            disabled={page >= totalPages}
            className="text-sm cursor-pointer disabled:opacity-40"
            style={{
              width: 32,
              height: 32,
              background: 'var(--color-surface)',
              border: '1px solid var(--color-border)',
              borderRadius: 'var(--radius)',
              color: 'var(--color-text)',
            }}
          >
            ›
          </button>
        </div>
      )}
    </div>
  )
}
