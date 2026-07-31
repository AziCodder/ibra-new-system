import { useEffect, useRef, useState, type CSSProperties } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { useNavigate } from 'react-router-dom'
import { DndContext, PointerSensor, closestCenter, useSensor, useSensors, type DragEndEvent } from '@dnd-kit/core'
import { SortableContext, arrayMove, rectSortingStrategy, useSortable } from '@dnd-kit/sortable'
import { CSS } from '@dnd-kit/utilities'
import {
  fetchOrders,
  fetchOrderStats,
  reorderOrders,
  type Order,
  type OrderListResponse,
  type OrderSortBy,
  type OrderSortOrder,
  type OrderStatus,
} from '../api/orders'
import { fetchClients } from '../api/clients'
import CreateOrderModal from '../components/CreateOrderModal'
import { useAuth } from '../contexts/AuthContext'
import { SkeletonCardGrid } from '../components/Skeleton'
import ErrorState from '../components/ErrorState'
import Tag, { type TagColor } from '../components/Tag'
import PageHeader from '../components/PageHeader'
import SearchInput from '../components/SearchInput'
import StatCard from '../components/StatCard'
import { useToast } from '../components/Toast'
import { Calendar, User, Plus } from 'lucide-react'

const SORT_OPTIONS = [
  { value: 'created_at:desc', label: 'Дата ↓ (новые)' },
  { value: 'created_at:asc', label: 'Дата ↑ (старые)' },
  { value: 'number:asc', label: 'Номер ↑ (А–Я)' },
  { value: 'number:desc', label: 'Номер ↓ (Я–А)' },
  { value: 'manual:asc', label: 'Вручную (перетаскивание)' },
]

const SORT_STORAGE_KEY = 'ibra_orders_sort'

type SortState = { sortBy: OrderSortBy; sortOrder: OrderSortOrder }

const DEFAULT_SORT: SortState = { sortBy: 'created_at', sortOrder: 'desc' }

/** Выбранная сортировка живёт в localStorage — переживает перезагрузку страницы. */
function readSortFromStorage(): SortState {
  try {
    const raw = localStorage.getItem(SORT_STORAGE_KEY)
    if (!raw) return DEFAULT_SORT
    const parsed = JSON.parse(raw) as SortState
    if (
      (parsed.sortBy === 'created_at' || parsed.sortBy === 'number' || parsed.sortBy === 'manual') &&
      (parsed.sortOrder === 'asc' || parsed.sortOrder === 'desc')
    ) {
      return parsed
    }
  } catch {
    /* повреждённое значение — берём порядок по умолчанию */
  }
  return DEFAULT_SORT
}

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

function PaymentProgress({ order }: { order: Order }) {
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

function OrderCard({ order }: { order: Order }) {
  const navigate = useNavigate()
  const badge = STATUS_BADGE[order.status]
  const date = new Date(order.created_at).toLocaleDateString('ru-RU', { day: '2-digit', month: 'short' })

  return (
    // h-full + grid-auto-rows: 1fr у сетки => все карточки одной высоты
    // независимо от длины описания и вида блока оплаты.
    <div
      onClick={() => navigate(`/orders/${order.id}`)}
      className="rounded-[10px] p-4 flex flex-col gap-3 transition-transform cursor-pointer h-full"
      style={{ background: 'var(--color-surface)', border: '1px solid var(--color-card-border)', boxShadow: 'var(--shadow-card)' }}
    >
      <div className="flex items-center justify-between gap-2">
        <span className="text-base font-extrabold truncate" style={{ color: 'var(--color-primary)' }}>{order.number}</span>
        <Tag color={badge.color}>{badge.label}</Tag>
      </div>
      <div className="text-sm font-bold line-clamp-2" style={{ color: 'var(--color-text)' }}>{order.client_name}</div>
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
          <div className="text-xs line-clamp-2" style={{ color: 'var(--color-muted)' }}>{order.details}</div>
        </>
      )}
      {/* Блок оплаты прижат к низу, слот фиксированной высоты — разделители
          и суммы стоят на одной линии во всех карточках. */}
      <div className="mt-auto flex flex-col gap-3">
        <div style={{ height: 1, background: 'var(--color-border)' }} />
        <div className="flex flex-col justify-end" style={{ minHeight: 28 }}>
          <PaymentProgress order={order} />
        </div>
      </div>
    </div>
  )
}

/** Карточка заказа с перетаскиванием (активация — удержание ~0.5 с). */
function SortableOrderCard({ order }: { order: Order }) {
  const { attributes, listeners, setNodeRef, transform, transition, isDragging } = useSortable({ id: order.id })
  // После перетаскивания браузер всё равно шлёт click — он открыл бы заказ.
  const draggedRef = useRef(false)

  useEffect(() => {
    if (isDragging) draggedRef.current = true
  }, [isDragging])

  const style: CSSProperties = {
    transform: isDragging ? `${CSS.Transform.toString(transform)} scale(1.03)` : CSS.Transform.toString(transform),
    transition,
    touchAction: 'manipulation',
    cursor: 'grab',
    height: '100%',
    ...(isDragging ? { opacity: 0.6, zIndex: 999, position: 'relative' } : {}),
  }

  return (
    <div
      ref={setNodeRef}
      style={style}
      {...attributes}
      {...listeners}
      onPointerDownCapture={() => { draggedRef.current = false }}
      onClickCapture={(e) => {
        if (draggedRef.current) {
          draggedRef.current = false
          e.preventDefault()
          e.stopPropagation()
        }
      }}
    >
      <OrderCard order={order} />
    </div>
  )
}

export default function OrdersPage() {
  const [statusFilter, setStatusFilter] = useState<OrderStatus | 'all'>('all')
  const [clientId, setClientId] = useState<number | undefined>(undefined)
  const [search, setSearch] = useState('')
  const [page, setPage] = useState(1)
  const [showCreate, setShowCreate] = useState(false)
  const [sort, setSort] = useState<SortState>(readSortFromStorage)
  const pageSize = 12
  const { user } = useAuth()
  const canCreate = user?.role !== 'observer'
  const queryClient = useQueryClient()
  const showToast = useToast()

  const { data: clients } = useQuery({ queryKey: ['clients'], queryFn: fetchClients })

  const queryKey = ['orders', statusFilter, clientId, search, page, sort.sortBy, sort.sortOrder]

  const { data, isLoading, isError, refetch } = useQuery({
    queryKey,
    queryFn: () =>
      fetchOrders({
        status: statusFilter === 'all' ? undefined : statusFilter,
        client_id: clientId,
        search: search || undefined,
        sort_by: sort.sortBy,
        sort_order: sort.sortOrder,
        page,
        page_size: pageSize,
      }),
  })

  const totalPages = data ? Math.max(1, Math.ceil(data.total / pageSize)) : 1

  // Перетаскивание — только в режиме «Вручную». Карточка открывается по клику,
  // поэтому drag начинается после удержания ~0.5 с, а не с первого движения.
  const isManual = sort.sortBy === 'manual'
  const sensors = useSensors(useSensor(PointerSensor, { activationConstraint: { delay: 500, tolerance: 8 } }))

  function selectStatus(key: OrderStatus | 'all') {
    setStatusFilter(key)
    setPage(1)
  }

  function selectSearch(v: string) {
    setSearch(v)
    setPage(1)
  }

  function selectSort(value: string) {
    const [sortBy, sortOrder] = value.split(':') as [OrderSortBy, OrderSortOrder]
    const next = { sortBy, sortOrder }
    setSort(next)
    localStorage.setItem(SORT_STORAGE_KEY, JSON.stringify(next))
    setPage(1)
  }

  async function handleDragEnd(event: DragEndEvent) {
    const { active, over } = event
    if (!over || active.id === over.id) return

    const current = data?.items ?? []
    const oldIndex = current.findIndex((o) => o.id === active.id)
    const newIndex = current.findIndex((o) => o.id === over.id)
    if (oldIndex === -1 || newIndex === -1) return

    const previous = data
    const next = arrayMove(current, oldIndex, newIndex)
    // Оптимистично показываем новый порядок, при ошибке откатываем.
    queryClient.setQueryData<OrderListResponse>(queryKey, (old) => (old ? { ...old, items: next } : old))

    try {
      await reorderOrders(next.map((o) => o.id))
      queryClient.invalidateQueries({ queryKey: ['orders'] })
    } catch (err) {
      queryClient.setQueryData(queryKey, previous)
      showToast(err instanceof Error ? err.message : 'Не удалось изменить порядок заказов', 'error')
    }
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
          className="text-sm outline-none px-3 w-full sm:w-auto"
          style={{ height: 32, background: 'var(--color-surface)', border: '1px solid var(--color-border)', borderRadius: 'var(--radius)', color: 'var(--color-text)' }}
        >
          <option value="">Клиент: все</option>
          {clients?.map((c) => (
            <option key={c.id} value={c.id}>{c.code} — {c.full_name}</option>
          ))}
        </select>

        <select
          value={`${sort.sortBy}:${sort.sortOrder}`}
          onChange={(e) => selectSort(e.target.value)}
          aria-label="Сортировка заказов"
          className="text-sm outline-none px-3 w-full sm:w-auto"
          style={{ height: 32, background: 'var(--color-surface)', border: '1px solid var(--color-border)', borderRadius: 'var(--radius)', color: 'var(--color-text)' }}
        >
          {SORT_OPTIONS.map((opt) => (
            <option key={opt.value} value={opt.value}>{opt.label}</option>
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
      ) : isManual ? (
        <DndContext sensors={sensors} collisionDetection={closestCenter} onDragEnd={handleDragEnd}>
          <SortableContext items={data.items.map((o) => o.id)} strategy={rectSortingStrategy}>
            <div
              className="grid gap-4"
              style={{ gridTemplateColumns: 'repeat(auto-fill, minmax(300px, 1fr))', gridAutoRows: '1fr' }}
            >
              {data.items.map((order) => (
                <SortableOrderCard key={order.id} order={order} />
              ))}
            </div>
          </SortableContext>
        </DndContext>
      ) : (
        <div
          className="grid gap-4"
          style={{ gridTemplateColumns: 'repeat(auto-fill, minmax(300px, 1fr))', gridAutoRows: '1fr' }}
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
