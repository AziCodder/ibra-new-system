import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { updateProduct, deleteProduct, type Product } from '../api/products'
import { fetchSuppliers } from '../api/suppliers'
import FileUploader, { type UploadedFile } from './FileUploader'

const CURRENCIES = ['USD', 'EUR', 'CNY', 'RUB']

function formatNumber(value: number): string {
  return value.toLocaleString('ru-RU', { maximumFractionDigits: 2 })
}

function SummaryRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex justify-between text-sm py-1.5">
      <span style={{ color: 'var(--color-muted)' }}>{label}</span>
      <span style={{ color: 'var(--color-text)', fontVariantNumeric: 'tabular-nums' }}>{value}</span>
    </div>
  )
}

export default function ProductDetailPanel({
  orderId,
  product,
  canEdit,
  onClose,
}: {
  orderId: number
  product: Product
  canEdit: boolean
  onClose: () => void
}) {
  const queryClient = useQueryClient()
  const [editing, setEditing] = useState(false)
  const [error, setError] = useState('')

  const [supplierId, setSupplierId] = useState<number | ''>(product.supplier_id)
  const [name, setName] = useState(product.name)
  const [details, setDetails] = useState(product.details)
  const [quantity, setQuantity] = useState(product.quantity)
  const [price, setPrice] = useState(product.price)
  const [currency, setCurrency] = useState(product.currency)
  const [photo, setPhoto] = useState<UploadedFile | null>(
    product.photo_key ? { key: product.photo_key, filename: product.photo_key, size: 0 } : null
  )

  const { data: suppliers } = useQuery({ queryKey: ['suppliers'], queryFn: fetchSuppliers, enabled: editing })

  const updateMutation = useMutation({
    mutationFn: () =>
      updateProduct(orderId, product.id, {
        supplier_id: Number(supplierId),
        name,
        details,
        quantity: Number(quantity),
        price: Number(price),
        currency,
        photo_key: photo?.key ?? null,
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['products', orderId] })
      setEditing(false)
    },
    onError: (err: Error) => setError(err.message),
  })

  const deleteMutation = useMutation({
    mutationFn: () => deleteProduct(orderId, product.id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['products', orderId] })
      onClose()
    },
    onError: (err: Error) => setError(err.message),
  })

  function handleDelete() {
    if (window.confirm(`Удалить товар «${product.name}»?`)) {
      deleteMutation.mutate()
    }
  }

  const quantityNum = Number(product.quantity)
  const priceNum = Number(product.price)
  const total = quantityNum * priceNum
  const canSave = supplierId !== '' && name.trim() !== '' && Number(quantity) > 0 && Number(price) >= 0

  return (
    <div className="fixed inset-0 z-50" onClick={onClose}>
      <div className="absolute inset-0" style={{ background: 'rgba(0,0,0,0.5)' }} />
      <div
        onClick={(e) => e.stopPropagation()}
        className="absolute right-0 top-0 h-full w-full sm:w-[420px] overflow-y-auto p-6"
        style={{ background: 'var(--color-surface)', borderLeft: '1px solid var(--color-border)' }}
      >
        <div className="flex items-center justify-between mb-5">
          <h3 className="text-base font-semibold" style={{ color: 'var(--color-text)' }}>
            {editing ? 'Редактировать товар' : product.name}
          </h3>
          <button onClick={onClose} className="text-sm cursor-pointer" style={{ color: 'var(--color-muted)' }}>
            ✕
          </button>
        </div>

        {error && (
          <div
            className="rounded-lg px-3 py-2 mb-4 text-sm"
            style={{ background: 'var(--color-danger-bg)', color: 'var(--color-danger)' }}
          >
            {error}
          </div>
        )}

        {!editing && (
          <>
            {product.photo_key ? (
              <img
                src={`/api/files/${product.photo_key}`}
                alt={product.name}
                className="w-full rounded-xl mb-4 object-cover"
                style={{ maxHeight: 220, border: '1px solid var(--color-border)' }}
              />
            ) : (
              <div
                className="rounded-xl p-6 text-center text-sm mb-4"
                style={{ background: 'var(--color-surface-2)', border: '1px dashed var(--color-border)', color: 'var(--color-muted)' }}
              >
                Без фото
              </div>
            )}

            {product.details && (
              <p className="text-sm mb-4" style={{ color: 'var(--color-text)' }}>
                {product.details}
              </p>
            )}

            <div className="rounded-xl p-4 mb-4" style={{ background: 'var(--color-surface-2)' }}>
              <SummaryRow label="Поставщик" value={product.supplier_name} />
              <SummaryRow label="Количество" value={formatNumber(quantityNum)} />
              <SummaryRow label="Цена" value={`${formatNumber(priceNum)} ${product.currency}`} />
              <SummaryRow label="Итого" value={`${formatNumber(total)} ${product.currency}`} />
            </div>

            <div className="rounded-xl p-4 mb-4" style={{ background: 'var(--color-surface-2)' }}>
              <div className="text-xs font-semibold uppercase tracking-wide mb-2" style={{ color: 'var(--color-muted)' }}>
                Счета и оплата
              </div>
              <SummaryRow label="Выставлено" value={`0 ${product.currency}`} />
              <SummaryRow label="Оплачено" value={`0 ${product.currency}`} />
              <SummaryRow label="Остаток" value={`${formatNumber(total)} ${product.currency}`} />
            </div>

            <div className="rounded-xl p-4 mb-6" style={{ background: 'var(--color-surface-2)' }}>
              <div className="text-xs font-semibold uppercase tracking-wide mb-2" style={{ color: 'var(--color-muted)' }}>
                Логистика
              </div>
              <SummaryRow label="Отправлено" value={`0 / ${formatNumber(quantityNum)}`} />
              <div className="text-sm mt-1" style={{ color: 'var(--color-muted)' }}>
                Трекингов пока нет
              </div>
            </div>

            {canEdit && (
              <div className="flex gap-2">
                <button
                  onClick={() => setEditing(true)}
                  className="flex-1 rounded-lg px-4 py-2 text-sm font-medium cursor-pointer"
                  style={{ background: 'var(--color-primary)', color: '#fff' }}
                >
                  Редактировать
                </button>
                <button
                  onClick={handleDelete}
                  disabled={deleteMutation.isPending}
                  className="rounded-lg px-4 py-2 text-sm font-medium cursor-pointer disabled:opacity-50"
                  style={{ background: 'var(--color-danger-bg)', color: 'var(--color-danger)' }}
                >
                  {deleteMutation.isPending ? 'Удаление...' : 'Удалить'}
                </button>
              </div>
            )}
          </>
        )}

        {editing && (
          <>
            <label className="block mb-4">
              <span className="block text-sm mb-1.5" style={{ color: 'var(--color-muted)' }}>Наименование</span>
              <input
                type="text"
                value={name}
                onChange={(e) => setName(e.target.value)}
                className="w-full rounded-lg px-3 py-2.5 text-sm outline-none"
                style={{ background: 'var(--color-surface-2)', border: '1px solid var(--color-border)', color: 'var(--color-text)' }}
              />
            </label>

            <label className="block mb-4">
              <span className="block text-sm mb-1.5" style={{ color: 'var(--color-muted)' }}>Детали</span>
              <textarea
                value={details}
                onChange={(e) => setDetails(e.target.value)}
                rows={2}
                className="w-full rounded-lg px-3 py-2.5 text-sm outline-none resize-none"
                style={{ background: 'var(--color-surface-2)', border: '1px solid var(--color-border)', color: 'var(--color-text)' }}
              />
            </label>

            <div className="grid grid-cols-2 gap-3 mb-4">
              <label className="block">
                <span className="block text-sm mb-1.5" style={{ color: 'var(--color-muted)' }}>Количество</span>
                <input
                  type="number"
                  min="0.000001"
                  step="any"
                  value={quantity}
                  onChange={(e) => setQuantity(e.target.value)}
                  className="w-full rounded-lg px-3 py-2.5 text-sm outline-none"
                  style={{ background: 'var(--color-surface-2)', border: '1px solid var(--color-border)', color: 'var(--color-text)' }}
                />
              </label>

              <label className="block">
                <span className="block text-sm mb-1.5" style={{ color: 'var(--color-muted)' }}>Цена</span>
                <input
                  type="number"
                  min="0"
                  step="any"
                  value={price}
                  onChange={(e) => setPrice(e.target.value)}
                  className="w-full rounded-lg px-3 py-2.5 text-sm outline-none"
                  style={{ background: 'var(--color-surface-2)', border: '1px solid var(--color-border)', color: 'var(--color-text)' }}
                />
              </label>
            </div>

            <label className="block mb-4">
              <span className="block text-sm mb-1.5" style={{ color: 'var(--color-muted)' }}>Валюта</span>
              <select
                value={currency}
                onChange={(e) => setCurrency(e.target.value)}
                className="w-full rounded-lg px-3 py-2.5 text-sm outline-none"
                style={{ background: 'var(--color-surface-2)', border: '1px solid var(--color-border)', color: 'var(--color-text)' }}
              >
                {CURRENCIES.map((c) => <option key={c} value={c}>{c}</option>)}
              </select>
            </label>

            <label className="block mb-4">
              <span className="block text-sm mb-1.5" style={{ color: 'var(--color-muted)' }}>Поставщик</span>
              <select
                value={supplierId}
                onChange={(e) => setSupplierId(e.target.value ? Number(e.target.value) : '')}
                className="w-full rounded-lg px-3 py-2.5 text-sm outline-none"
                style={{ background: 'var(--color-surface-2)', border: '1px solid var(--color-border)', color: 'var(--color-text)' }}
              >
                <option value="">Выберите поставщика</option>
                {suppliers?.map((s) => (
                  <option key={s.id} value={s.id}>{s.name}</option>
                ))}
              </select>
            </label>

            <div className="mb-6">
              <span className="block text-sm mb-1.5" style={{ color: 'var(--color-muted)' }}>Фото (1 файл)</span>
              <FileUploader
                files={photo ? [photo] : []}
                onUpload={(file) => setPhoto(file)}
                onRemove={() => setPhoto(null)}
              />
            </div>

            <div className="flex justify-end gap-2">
              <button
                onClick={() => setEditing(false)}
                className="rounded-lg px-4 py-2 text-sm cursor-pointer"
                style={{ background: 'var(--color-surface-3)', color: 'var(--color-text)' }}
              >
                Отмена
              </button>
              <button
                onClick={() => updateMutation.mutate()}
                disabled={!canSave || updateMutation.isPending}
                className="rounded-lg px-4 py-2 text-sm font-medium cursor-pointer disabled:opacity-50"
                style={{ background: 'var(--color-primary)', color: '#fff' }}
              >
                {updateMutation.isPending ? 'Сохранение...' : 'Сохранить'}
              </button>
            </div>
          </>
        )}
      </div>
    </div>
  )
}
