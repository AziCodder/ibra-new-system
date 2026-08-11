import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { fetchProducts } from '../api/products'
import AddProductModal from './AddProductModal'
import ProductDetailPanel from './ProductDetailPanel'
import ErrorState from './ErrorState'
import Skeleton from './Skeleton'

function formatNumber(value: number): string {
  return value.toLocaleString('ru-RU', { maximumFractionDigits: 2 })
}

export default function ProductsTable({ orderId, orderCurrency, canEdit }: { orderId: number; orderCurrency: string; canEdit: boolean }) {
  const [showAddModal, setShowAddModal] = useState(false)
  const [selectedProductId, setSelectedProductId] = useState<number | null>(null)

  const { data: products, isLoading, isError, refetch } = useQuery({
    queryKey: ['products', orderId],
    queryFn: () => fetchProducts(orderId),
  })

  const selectedProduct = products?.find((p) => p.id === selectedProductId) ?? null

  const totalsByCurrency = new Map<string, { quantity: number; sum: number }>()
  // Products may be priced in different currencies; each carries its rate from the
  // order's ("1 CNY = 11.5 RUB" -> 11.5, so divide), which keeps a single
  // comparable grand total available.
  let grandTotalInOrderCurrency = 0
  for (const product of products ?? []) {
    const quantity = Number(product.quantity)
    const sum = quantity * Number(product.price)
    const existing = totalsByCurrency.get(product.currency) ?? { quantity: 0, sum: 0 }
    totalsByCurrency.set(product.currency, {
      quantity: existing.quantity + quantity,
      sum: existing.sum + sum,
    })
    grandTotalInOrderCurrency += sum / Number(product.exchange_rate || 1)
  }
  const hasForeignCurrency = [...totalsByCurrency.keys()].some((c) => c !== orderCurrency)

  return (
    <div>
      {canEdit && (
        <div className="flex justify-end mb-3">
          <button
            onClick={() => setShowAddModal(true)}
            className="rounded-lg px-4 py-2 text-sm font-medium cursor-pointer"
            style={{ background: 'var(--color-primary)', color: '#fff' }}
          >
            + Добавить
          </button>
        </div>
      )}

      {isLoading && (
        <div className="flex flex-col gap-2">
          {Array.from({ length: 3 }).map((_, i) => (
            <Skeleton key={i} height={48} radius={10} />
          ))}
        </div>
      )}

      {!isLoading && isError && (
        <ErrorState message="Не удалось загрузить товары" onRetry={() => refetch()} />
      )}

      {!isLoading && !isError && (!products || products.length === 0) && (
        <div
          className="rounded-[10px] p-12 text-center"
          style={{ background: 'var(--color-surface)', border: '1px dashed var(--color-border)', color: 'var(--color-muted)' }}
        >
          Товаров пока нет
        </div>
      )}

      {!isLoading && products && products.length > 0 && (
        <div className="rounded-[10px] overflow-x-auto" style={{ border: '1px solid var(--color-border)', background: 'var(--color-surface)', boxShadow: 'var(--shadow-card)' }}>
          <table className="rtable w-full text-sm" style={{ borderCollapse: 'collapse' }}>
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
                  <tr
                    key={product.id}
                    onClick={() => setSelectedProductId(product.id)}
                    className="cursor-pointer transition-colors"
                    style={{ borderTop: '1px solid var(--color-border)' }}
                    onMouseEnter={(e) => { e.currentTarget.style.background = 'var(--color-surface-2)' }}
                    onMouseLeave={(e) => { e.currentTarget.style.background = 'transparent' }}
                  >
                    <td className="px-4 py-2.5" data-label="Наименование" style={{ color: 'var(--color-text)' }}>
                      {product.name}
                    </td>
                    <td className="px-4 py-2.5 text-right" data-label="Кол-во" style={{ color: 'var(--color-text)', fontVariantNumeric: 'tabular-nums' }}>
                      {formatNumber(quantity)}
                    </td>
                    <td className="px-4 py-2.5 text-right" data-label="Цена" style={{ color: 'var(--color-text)', fontVariantNumeric: 'tabular-nums' }}>
                      {formatNumber(price)} {product.currency}
                    </td>
                    <td className="px-4 py-2.5 text-right" data-label="Сумма" style={{ color: 'var(--color-text)', fontVariantNumeric: 'tabular-nums' }}>
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
                  <td className="px-4 py-2.5 text-right font-semibold" data-label="Кол-во" style={{ color: 'var(--color-text)', fontVariantNumeric: 'tabular-nums' }}>
                    {formatNumber(totals.quantity)}
                  </td>
                  <td className="px-4 py-2.5" />
                  <td className="px-4 py-2.5 text-right font-semibold" data-label="Сумма" style={{ color: 'var(--color-text)', fontVariantNumeric: 'tabular-nums' }}>
                    {formatNumber(totals.sum)} {currency}
                  </td>
                </tr>
              ))}
              {hasForeignCurrency && (
                <tr style={{ borderTop: '1px solid var(--color-border)', background: 'var(--color-surface-2)' }}>
                  <td className="px-4 py-2.5 font-semibold" style={{ color: 'var(--color-text)' }}>
                    Всего в валюте заказа
                  </td>
                  <td className="px-4 py-2.5" />
                  <td className="px-4 py-2.5" />
                  <td className="px-4 py-2.5 text-right font-semibold" data-label="Сумма" style={{ color: 'var(--color-text)', fontVariantNumeric: 'tabular-nums' }}>
                    {formatNumber(grandTotalInOrderCurrency)} {orderCurrency}
                  </td>
                </tr>
              )}
            </tfoot>
          </table>
        </div>
      )}

      {showAddModal && <AddProductModal orderId={orderId} orderCurrency={orderCurrency} onClose={() => setShowAddModal(false)} />}

      {selectedProduct && (
        <ProductDetailPanel
          key={selectedProduct.id}
          orderId={orderId}
          orderCurrency={orderCurrency}
          product={selectedProduct}
          canEdit={canEdit}
          onClose={() => setSelectedProductId(null)}
        />
      )}
    </div>
  )
}
