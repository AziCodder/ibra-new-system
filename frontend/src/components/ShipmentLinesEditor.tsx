import { Trash2 } from 'lucide-react'
import type { Logistics } from '../api/logistics'
import type { Product } from '../api/products'

export interface ShipmentLine {
  productId: number | ''
  quantity: string
}

function formatNumber(value: number): string {
  return value.toLocaleString('ru-RU', { maximumFractionDigits: 2 })
}

/**
 * How much of each product is still free to ship, i.e. its purchased quantity
 * minus everything already committed to a non-cancelled shipment.
 *
 * `excludeLogisticsId` leaves out one shipment's own lines, so editing it doesn't
 * see its saved quantities as somebody else's commitment — this mirrors
 * `exclude_logistics_id` in the backend's logistics_validation.
 */
export function remainingByProduct(
  products: Product[],
  shipments: Logistics[],
  excludeLogisticsId?: number,
): Map<number, number> {
  const remaining = new Map<number, number>()
  for (const product of products) {
    const shipped = shipments
      .filter((l) => l.status !== 'cancelled' && l.id !== excludeLogisticsId)
      .flatMap((l) => l.items)
      .filter((item) => item.product_id === product.id)
      .reduce((sum, item) => sum + Number(item.quantity), 0)
    remaining.set(product.id, Number(product.quantity) - shipped)
  }
  return remaining
}

/** Headroom for one line: its product's remaining, minus the other lines' claims on it. */
function lineHeadroom(lines: ShipmentLine[], index: number, remaining: Map<number, number>): number {
  const { productId } = lines[index]
  if (productId === '') return 0
  const claimedElsewhere = lines
    .filter((l, i) => i !== index && l.productId === productId)
    .reduce((sum, l) => sum + (Number(l.quantity) || 0), 0)
  return (remaining.get(productId) ?? 0) - claimedElsewhere
}

export function validateLines(lines: ShipmentLine[], remaining: Map<number, number>): boolean {
  if (lines.length === 0) return false
  const productIds = lines.map((l) => l.productId)
  if (productIds.some((id) => id === '')) return false
  if (new Set(productIds).size !== productIds.length) return false
  return lines.every((line, i) => {
    const quantity = Number(line.quantity)
    return quantity > 0 && quantity <= lineHeadroom(lines, i, remaining)
  })
}

const inputStyle = {
  background: 'var(--color-surface)',
  border: '1px solid var(--color-border)',
  color: 'var(--color-text)',
}

/** Repeatable product + quantity rows for one shipment. */
export default function ShipmentLinesEditor({
  products,
  remaining,
  lines,
  onChange,
}: {
  products: Product[]
  remaining: Map<number, number>
  lines: ShipmentLine[]
  onChange: (next: ShipmentLine[]) => void
}) {
  const chosen = new Set(lines.map((l) => l.productId).filter((id) => id !== ''))
  // Only products with headroom left are worth offering as a new row.
  const addable = products.filter((p) => !chosen.has(p.id) && (remaining.get(p.id) ?? 0) > 0)

  function update(index: number, patch: Partial<ShipmentLine>) {
    onChange(lines.map((line, i) => (i === index ? { ...line, ...patch } : line)))
  }

  return (
    <div className="mb-4">
      <div className="flex items-center justify-between mb-1.5">
        <span className="text-sm" style={{ color: 'var(--color-muted)' }}>Позиции</span>
        <button
          type="button"
          onClick={() => onChange([...lines, { productId: '', quantity: '' }])}
          disabled={addable.length === 0}
          className="text-sm cursor-pointer disabled:opacity-40"
          style={{ color: 'var(--color-primary)' }}
        >
          + Добавить позицию
        </button>
      </div>

      <div className="flex flex-col gap-2">
        {lines.map((line, index) => {
          const headroom = lineHeadroom(lines, index, remaining)
          const quantity = Number(line.quantity)
          const overCommitted = line.productId !== '' && line.quantity !== '' && quantity > headroom
          const duplicate =
            line.productId !== '' && lines.filter((l) => l.productId === line.productId).length > 1

          return (
            <div key={index} className="flex items-start gap-2">
              <div className="flex-1 min-w-0">
                <select
                  value={line.productId}
                  onChange={(e) => update(index, { productId: e.target.value ? Number(e.target.value) : '' })}
                  className="w-full rounded-lg px-3 py-2.5 text-sm outline-none"
                  style={{
                    ...inputStyle,
                    border: duplicate ? '1px solid var(--color-danger)' : inputStyle.border,
                  }}
                >
                  <option value="">— выберите товар —</option>
                  {products.map((p) => (
                    <option key={p.id} value={p.id}>{p.name}</option>
                  ))}
                </select>
                {line.productId !== '' && (
                  <span className="block text-xs mt-1" style={{ color: overCommitted || duplicate ? 'var(--color-danger)' : 'var(--color-muted)' }}>
                    {duplicate
                      ? 'Этот товар уже добавлен в отправку'
                      : `остаток отправки: ${formatNumber(headroom)}`}
                  </span>
                )}
              </div>

              <input
                type="number"
                min="0.000001"
                step="any"
                placeholder="Кол-во"
                value={line.quantity}
                onChange={(e) => update(index, { quantity: e.target.value })}
                className="w-28 rounded-lg px-3 py-2.5 text-sm text-right outline-none"
                style={{
                  ...inputStyle,
                  border: overCommitted ? '1px solid var(--color-danger)' : inputStyle.border,
                }}
              />

              <button
                type="button"
                onClick={() => onChange(lines.filter((_, i) => i !== index))}
                disabled={lines.length === 1}
                title="Убрать позицию"
                className="rounded-lg p-2.5 cursor-pointer disabled:opacity-30"
                style={{ background: 'var(--color-surface-3)', color: 'var(--color-muted)' }}
              >
                <Trash2 size={16} />
              </button>
            </div>
          )
        })}
      </div>
    </div>
  )
}
