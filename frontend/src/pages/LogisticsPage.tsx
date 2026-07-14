import { useState } from 'react'
import { Link } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { fetchAllLogistics, type LogisticsSummary, type LogisticsStatus } from '../api/logistics'
import { fetchClients } from '../api/clients'
import { fetchUsers } from '../api/users'
import { useAuth } from '../contexts/AuthContext'
import LogisticsDetailPanel from '../components/LogisticsDetailPanel'
import ErrorState from '../components/ErrorState'
import Skeleton from '../components/Skeleton'
import Tag, { type TagColor } from '../components/Tag'
import PageHeader from '../components/PageHeader'
import SearchInput from '../components/SearchInput'

const STATUS_LABEL: Record<LogisticsStatus, string> = {
  in_transit: 'В пути',
  accepted: 'Принято',
  cancelled: 'Отменено',
}

const STATUS_COLOR: Record<LogisticsStatus, TagColor> = {
  in_transit: 'orange',
  accepted: 'green',
  cancelled: 'default',
}

function formatNum(v: string | number | null | undefined) {
  if (v == null) return '—'
  return Number(v).toLocaleString('ru-RU', { maximumFractionDigits: 2 })
}

export default function LogisticsPage() {
  const { user } = useAuth()

  const [status, setStatus] = useState<LogisticsStatus | ''>('')
  const [clientId, setClientId] = useState<number | undefined>()
  const [managerId, setManagerId] = useState<number | undefined>()
  const [search, setSearch] = useState('')
  const [sort, setSort] = useState<'asc' | 'desc'>('desc')
  const [selectedId, setSelectedId] = useState<number | null>(null)

  const filters = {
    status: status || undefined,
    client_id: clientId,
    manager_id: managerId,
    search: search || undefined,
    sort,
  }

  const { data: items, isLoading, isError, refetch } = useQuery({
    queryKey: ['all-logistics', filters],
    queryFn: () => fetchAllLogistics(filters),
  })

  const selected = items?.find((lg) => lg.id === selectedId) ?? null

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
  const isAdmin = user?.role === 'admin'

  function canEdit(lg: LogisticsSummary): boolean {
    if (!user) return false
    if (user.role === 'admin') return true
    if (user.role === 'manager') return user.id === lg.manager_id
    return false
  }

  return (
    <div className="p-4 sm:p-6 max-w-screen-xl mx-auto">
      <PageHeader title="Логистика" subtitle="Все отправки по всем заказам">
        <SearchInput
          value={search}
          onChange={setSearch}
          placeholder="Поиск по трекингу, заказу, товару..."
          className="flex-1 sm:flex-initial sm:w-64"
        />
      </PageHeader>

      <div className="flex flex-col sm:flex-row items-stretch sm:items-center flex-wrap gap-3 mb-6">
        <select
            value={status}
            onChange={(e) => setStatus(e.target.value as LogisticsStatus | '')}
            className="text-sm outline-none w-full sm:w-auto px-3"
            style={{ height: 32, background: 'var(--color-surface)', border: '1px solid var(--color-border)', borderRadius: 'var(--radius)', color: 'var(--color-text)' }}
          >
            <option value="">Все статусы</option>
            <option value="in_transit">В пути</option>
            <option value="accepted">Принято</option>
            <option value="cancelled">Отменено</option>
          </select>

          {(isAdmin || user?.role === 'observer') && (
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
          {Array.from({ length: 6 }).map((_, i) => (
            <Skeleton key={i} height={44} radius={10} />
          ))}
        </div>
      )}

      {!isLoading && isError && (
        <ErrorState message="Не удалось загрузить логистику" onRetry={() => refetch()} />
      )}

      {!isLoading && !isError && (!items || items.length === 0) && (
        <div
          className="rounded-[10px] p-12 text-center"
          style={{ background: 'var(--color-surface)', border: '1px solid var(--color-card-border)' }}
        >
          <div className="mb-3" style={{ color: 'var(--color-faint)' }}><svg xmlns="http://www.w3.org/2000/svg" width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"><path d="M14 18V6a2 2 0 0 0-2-2H4a2 2 0 0 0-2 2v11a1 1 0 0 0 1 1h2"/><path d="M15 18H9"/><path d="M19 18h2a1 1 0 0 0 1-1v-3.65a1 1 0 0 0-.22-.624l-3.48-4.35A1 1 0 0 0 17.52 8H14"/><circle cx="17" cy="18" r="2"/><circle cx="7" cy="18" r="2"/></svg></div>
          <div className="text-sm" style={{ color: 'var(--color-muted)' }}>Логистики нет</div>
        </div>
      )}

      {!isLoading && items && items.length > 0 && (
        <div className="rounded-[10px] overflow-x-auto" style={{ border: '1px solid var(--color-card-border)', background: 'var(--color-surface)' }}>
          <table className="rtable w-full text-sm border-collapse">
            <thead>
              <tr style={{ background: 'var(--color-surface-2)' }}>
                {['Статус', 'Трекинг', '№ заказа', 'Клиент', 'Менеджер', 'Товар', 'Кол-во', 'Отправлено', 'Принято', 'Расход'].map((h) => (
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
              {items.map((lg) => {
                const isSelected = selectedId === lg.id
                return (
                  <tr
                    key={lg.id}
                    onClick={() => setSelectedId(isSelected ? null : lg.id)}
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
                    <td className="px-4 py-3" data-label="Статус">
                      <Tag color={STATUS_COLOR[lg.status]}>{STATUS_LABEL[lg.status]}</Tag>
                    </td>
                    <td className="px-4 py-3 font-mono text-xs" data-label="Трекинг" style={{ color: 'var(--color-text)' }}>
                      {lg.tracking || '—'}
                    </td>
                    <td className="px-4 py-3 font-bold" data-label="№ заказа" onClick={(e) => e.stopPropagation()}>
                      <Link to={`/orders/${lg.order_id}`} style={{ color: 'var(--color-primary)' }}>
                        {lg.order_number}
                      </Link>
                    </td>
                    <td className="px-4 py-3" data-label="Клиент" style={{ color: 'var(--color-text)' }}>{lg.client_name}</td>
                    <td className="px-4 py-3" data-label="Менеджер" style={{ color: 'var(--color-muted)' }}>{lg.manager_name}</td>
                    <td className="px-4 py-3 max-w-[140px] truncate" data-label="Товар" style={{ color: 'var(--color-muted)' }} title={lg.product_name}>
                      {lg.product_name}
                    </td>
                    <td className="px-4 py-3 whitespace-nowrap" data-label="Кол-во" style={{ color: 'var(--color-text)', fontVariantNumeric: 'tabular-nums' }}>
                      {formatNum(lg.quantity)}
                    </td>
                    <td className="px-4 py-3 whitespace-nowrap" data-label="Отправлено" style={{ color: 'var(--color-muted)' }}>
                      {new Date(lg.ship_date).toLocaleDateString('ru-RU', { day: '2-digit', month: 'short', year: '2-digit' })}
                    </td>
                    <td className="px-4 py-3 whitespace-nowrap" data-label="Принято" style={{ color: lg.received_date ? 'var(--color-success)' : 'var(--color-faint)' }}>
                      {lg.received_date
                        ? new Date(lg.received_date).toLocaleDateString('ru-RU', { day: '2-digit', month: 'short', year: '2-digit' })
                        : '—'}
                    </td>
                    <td className="px-4 py-3 whitespace-nowrap" data-label="Расход" style={{ color: 'var(--color-text)', fontVariantNumeric: 'tabular-nums' }}>
                      {lg.expense_amount ? `${formatNum(lg.expense_amount)} ${lg.currency ?? ''}` : '—'}
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      )}

      {selected && (
        <LogisticsDetailPanel
          orderId={selected.order_id}
          orderNumber={selected.order_number}
          logistics={selected}
          canEdit={canEdit(selected)}
          isAdmin={isAdmin ?? false}
          onClose={() => setSelectedId(null)}
        />
      )}
    </div>
  )
}
