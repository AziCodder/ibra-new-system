import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { X } from 'lucide-react'
import { fetchOrders } from '../api/orders'
import CreateLogisticsModal from './CreateLogisticsModal'
import SearchInput from './SearchInput'

/** "Создать логистику" from the global Logistics page: pick an in-progress order first, then reuse the per-order create form. */
export default function CreateLogisticsFlow({ onClose }: { onClose: () => void }) {
  const [search, setSearch] = useState('')
  const [orderId, setOrderId] = useState<number | null>(null)

  const { data, isLoading } = useQuery({
    queryKey: ['orders-for-logistics-pick', search],
    queryFn: () => fetchOrders({ status: 'in_progress', search: search || undefined, page_size: 20 }),
  })

  if (orderId !== null) {
    return <CreateLogisticsModal orderId={orderId} onClose={onClose} />
  }

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4"
      style={{ background: 'rgba(0,0,0,0.5)' }}
      onClick={onClose}
    >
      <div
        onClick={(e) => e.stopPropagation()}
        className="w-full max-w-lg rounded-[10px] p-6 max-h-[90vh] overflow-y-auto"
        style={{ background: 'var(--color-surface)', border: '1px solid var(--color-border)' }}
      >
        <div className="flex items-center justify-between mb-5">
          <h3 className="text-base font-semibold" style={{ color: 'var(--color-text)' }}>Выберите заказ</h3>
          <button onClick={onClose} className="cursor-pointer" style={{ color: 'var(--color-muted)' }}><X size={18} /></button>
        </div>

        <SearchInput value={search} onChange={setSearch} placeholder="Поиск по номеру, клиенту..." className="w-full mb-4" />

        {isLoading && <div style={{ color: 'var(--color-muted)' }}>Загрузка...</div>}

        {!isLoading && data && data.items.length === 0 && (
          <div className="text-sm text-center py-6" style={{ color: 'var(--color-muted)' }}>
            {search
              ? 'Ничего не найдено. Логистику можно добавить только к заказу в статусе «В работе».'
              : 'Нет заказов в работе — логистику можно добавить только к заказу в статусе «В работе».'}
          </div>
        )}

        {!isLoading && data && data.items.length > 0 && (
          <div className="flex flex-col gap-1.5 max-h-80 overflow-y-auto">
            {data.items.map((o) => (
              <button
                key={o.id}
                onClick={() => setOrderId(o.id)}
                className="text-left rounded-lg px-3 py-2.5 cursor-pointer transition-colors w-full"
                style={{ background: 'transparent', border: '1px solid var(--color-border)' }}
                onMouseEnter={(e) => { (e.currentTarget as HTMLButtonElement).style.background = 'var(--color-surface-2, var(--color-bg))' }}
                onMouseLeave={(e) => { (e.currentTarget as HTMLButtonElement).style.background = 'transparent' }}
              >
                <div className="text-sm font-medium" style={{ color: 'var(--color-text)' }}>{o.number}</div>
                <div className="text-xs" style={{ color: 'var(--color-muted)' }}>{o.client_name} · {o.currency}</div>
              </button>
            ))}
            {data.total > data.items.length && (
              <div className="text-xs text-center pt-1" style={{ color: 'var(--color-faint)' }}>
                Показаны первые {data.items.length} из {data.total} — уточните поиск
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  )
}
