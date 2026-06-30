import { useQuery } from '@tanstack/react-query'
import { fetchProducts } from '../api/products'

function formatNumber(value: number): string {
  return value.toLocaleString('ru-RU', { maximumFractionDigits: 2 })
}

export default function ProductsTable({ orderId }: { orderId: number }) {
  const { data: products, isLoading } = useQuery({
    queryKey: ['products', orderId],
    queryFn: () => fetchProducts(orderId),
  })

  if (isLoading) {
    return <div style={{ color: 'var(--color-muted)' }}>Загрузка...</div>
  }

  if (!products || products.length === 0) {
    return (
      <div
        className="rounded-2xl p-12 text-center"
        style={{ background: 'var(--color-surface)', border: '1px dashed var(--color-border)', color: 'var(--color-muted)' }}
      >
        Товаров пока нет
      </div>
    )
  }

  const totalsByCurrency = new Map<string, { quantity: number; sum: number }>()
  for (const product of products) {
    const quantity = Number(product.quantity)
    const sum = quantity * Number(product.price)
    const existing = totalsByCurrency.get(product.currency) ?? { quantity: 0, sum: 0 }
    totalsByCurrency.set(product.currency, {
      quantity: existing.quantity + quantity,
      sum: existing.sum + sum,
    })
  }

  return (
    <div className="rounded-2xl overflow-hidden" style={{ border: '1px solid var(--color-border)' }}>
      <table className="w-full text-sm" style={{ borderCollapse: 'collapse' }}>
        <thead>
          <tr style={{ background: 'var(--color-surface-2)' }}>
            <th className="text-left px-4 py-2.5 text-xs font-semibold uppercase tracking-wide" style={{ color: 'var(--color-muted)' }}>
              Наименование
            </th>
            <th className="text-right px-4 py-2.5 text-xs font-semibold uppercase tracking-wide" style={{ color: 'var(--color-muted)' }}>
              Кол-во
            </th>
            <th className="text-right px-4 py-2.5 text-xs font-semibold uppercase tracking-wide" style={{ color: 'var(--color-muted)' }}>
              Цена
            </th>
            <th className="text-right px-4 py-2.5 text-xs font-semibold uppercase tracking-wide" style={{ color: 'var(--color-muted)' }}>
              Сумма
            </th>
          </tr>
        </thead>
        <tbody>
          {products.map((product) => {
            const quantity = Number(product.quantity)
            const price = Number(product.price)
            return (
              <tr key={product.id} style={{ borderTop: '1px solid var(--color-border)' }}>
                <td className="px-4 py-2.5" style={{ color: 'var(--color-text)' }}>
                  {product.name}
                </td>
                <td className="px-4 py-2.5 text-right" style={{ color: 'var(--color-text)', fontVariantNumeric: 'tabular-nums' }}>
                  {formatNumber(quantity)}
                </td>
                <td className="px-4 py-2.5 text-right" style={{ color: 'var(--color-text)', fontVariantNumeric: 'tabular-nums' }}>
                  {formatNumber(price)} {product.currency}
                </td>
                <td className="px-4 py-2.5 text-right" style={{ color: 'var(--color-text)', fontVariantNumeric: 'tabular-nums' }}>
                  {formatNumber(quantity * price)} {product.currency}
                </td>
              </tr>
            )
          })}
        </tbody>
        <tfoot>
          {[...totalsByCurrency.entries()].map(([currency, totals]) => (
            <tr key={currency} style={{ borderTop: '2px solid var(--color-border)', background: 'var(--color-surface-2)' }}>
              <td className="px-4 py-2.5 font-semibold" style={{ color: 'var(--color-text)' }}>
                Итого {currency}
              </td>
              <td className="px-4 py-2.5 text-right font-semibold" style={{ color: 'var(--color-text)', fontVariantNumeric: 'tabular-nums' }}>
                {formatNumber(totals.quantity)}
              </td>
              <td className="px-4 py-2.5" />
              <td className="px-4 py-2.5 text-right font-semibold" style={{ color: 'var(--color-text)', fontVariantNumeric: 'tabular-nums' }}>
                {formatNumber(totals.sum)} {currency}
              </td>
            </tr>
          ))}
        </tfoot>
      </table>
    </div>
  )
}
