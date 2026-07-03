import { useState } from 'react'
import { Link } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { fetchAllLogistics, type LogisticsSummary, type LogisticsStatus } from '../api/logistics'
import { fetchClients } from '../api/clients'
import { fetchUsers } from '../api/users'
import { useAuth } from '../contexts/AuthContext'
import LogisticsDetailPanel from '../components/LogisticsDetailPanel'

const STATUS_LABEL: Record<LogisticsStatus, string> = {
  in_transit: 'В пути',
  accepted: 'Принято',
  cancelled: 'Отменено',
}

const STATUS_STYLE: Record<LogisticsStatus, { bg: string; color: string }> = {
  in_transit: { bg: 'var(--color-warning-bg)', color: 'var(--color-warning)' },
  accepted: { bg: 'var(--color-success-bg)', color: 'var(--color-success)' },
  cancelled: { bg: 'var(--color-surface-3)', color: 'var(--color-muted)' },
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

  const { data: items, isLoading } = useQuery({
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
    <div className="p-6 max-w-screen-xl mx-auto">
      <div className="flex items-center justify-between mb-6 flex-wrap gap-3">
        <h1 className="text-xl font-extrabold" style={{ color: 'var(--color-text)' }}>
          Логистика
        </h1>

        <div className="flex items-center gap-3 flex-wrap">
          <input
            type="text"
            placeholder="Поиск по трекингу, заказу, товару..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="rounded-lg px-3 py-2 text-sm outline-none"
            style={{
              background: 'var(--color-surface-2)',
              border: '1px solid var(--color-border)',
              color: 'var(--color-text)',
              width: 240,
            }}
          />

          <select
            value={status}
            onChange={(e) => setStatus(e.target.value as LogisticsStatus | '')}
            className="rounded-lg px-3 py-2 text-sm outline-none"
            style={{ background: 'var(--color-surface-2)', border: '1px solid var(--color-border)', color: 'var(--color-text)' }}
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

      {!isLoading && (!items || items.length === 0) && (
        <div
          className="rounded-2xl p-12 text-center"
          style={{ background: 'var(--color-surface)', border: '1px solid var(--color-border)' }}
        >
          <div className="text-4xl mb-3">🚚</div>
          <div className="text-sm" style={{ color: 'var(--color-muted)' }}>Логистики нет</div>
        </div>
      )}

      {!isLoading && items && items.length > 0 && (
        <div className="rounded-2xl overflow-x-auto" style={{ border: '1px solid var(--color-border)' }}>
          <table className="w-full text-sm border-collapse">
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
                const st = STATUS_STYLE[lg.status]
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
                    <td className="px-4 py-3">
                      <span
                        className="text-xs font-semibold rounded-full px-2.5 py-1 whitespace-nowrap"
                        style={{ background: st.bg, color: st.color }}
                      >
                        {STATUS_LABEL[lg.status]}
                      </span>
                    </td>
                    <td className="px-4 py-3 font-mono text-xs" style={{ color: 'var(--color-text)' }}>
                      {lg.tracking || '—'}
                    </td>
                    <td className="px-4 py-3 font-bold" onClick={(e) => e.stopPropagation()}>
                      <Link to={`/orders/${lg.order_id}`} style={{ color: 'var(--color-primary)' }}>
                        {lg.order_number}
                      </Link>
                    </td>
                    <td className="px-4 py-3" style={{ color: 'var(--color-text)' }}>{lg.client_name}</td>
                    <td className="px-4 py-3" style={{ color: 'var(--color-muted)' }}>{lg.manager_name}</td>
                    <td className="px-4 py-3 max-w-[140px] truncate" style={{ color: 'var(--color-muted)' }} title={lg.product_name}>
                      {lg.product_name}
                    </td>
                    <td className="px-4 py-3 whitespace-nowrap" style={{ color: 'var(--color-text)', fontVariantNumeric: 'tabular-nums' }}>
                      {formatNum(lg.quantity)}
                    </td>
                    <td className="px-4 py-3 whitespace-nowrap" style={{ color: 'var(--color-muted)' }}>
                      {new Date(lg.ship_date).toLocaleDateString('ru-RU', { day: '2-digit', month: 'short', year: '2-digit' })}
                    </td>
                    <td className="px-4 py-3 whitespace-nowrap" style={{ color: lg.received_date ? 'var(--color-success)' : 'var(--color-faint)' }}>
                      {lg.received_date
                        ? new Date(lg.received_date).toLocaleDateString('ru-RU', { day: '2-digit', month: 'short', year: '2-digit' })
                        : '—'}
                    </td>
                    <td className="px-4 py-3 whitespace-nowrap" style={{ color: 'var(--color-text)', fontVariantNumeric: 'tabular-nums' }}>
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
