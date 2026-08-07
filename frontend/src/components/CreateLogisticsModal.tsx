import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { fetchProducts } from '../api/products'
import { fetchLogistics, createLogistics } from '../api/logistics'
import FileUploader, { type UploadedFile } from './FileUploader'
import ShipmentLinesEditor, { type ShipmentLine, remainingByProduct, validateLines } from './ShipmentLinesEditor'

export default function CreateLogisticsModal({ orderId, onClose }: { orderId: number; onClose: () => void }) {
  const queryClient = useQueryClient()

  const [lines, setLines] = useState<ShipmentLine[]>([{ productId: '', quantity: '' }])
  const [tracking, setTracking] = useState('')
  const [shipDate, setShipDate] = useState(() => new Date().toISOString().slice(0, 10))
  const [details, setDetails] = useState('')
  const [file, setFile] = useState<UploadedFile | null>(null)
  const [error, setError] = useState('')

  const { data: products, isLoading: productsLoading } = useQuery({
    queryKey: ['products', orderId],
    queryFn: () => fetchProducts(orderId),
  })
  const { data: logisticsList, isLoading: logisticsLoading } = useQuery({
    queryKey: ['logistics', orderId],
    queryFn: () => fetchLogistics(orderId),
  })

  const loading = productsLoading || logisticsLoading
  const remaining = remainingByProduct(products ?? [], logisticsList ?? [])
  const linesValid = validateLines(lines, remaining)

  const mutation = useMutation({
    mutationFn: () =>
      createLogistics(orderId, {
        items: lines.map((line) => ({ product_id: Number(line.productId), quantity: Number(line.quantity) })),
        tracking,
        ship_date: new Date(shipDate).toISOString(),
        invoice_file_key: file?.key ?? null,
        details,
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['logistics', orderId] })
      queryClient.invalidateQueries({ queryKey: ['all-logistics'] })
      // Products carry the shipped/accepted rollup shown on the product card.
      queryClient.invalidateQueries({ queryKey: ['products', orderId] })
      onClose()
    },
    onError: (err: Error) => setError(err.message),
  })

  const canSave = linesValid && shipDate !== ''

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
        <h3 className="text-base font-semibold mb-5" style={{ color: 'var(--color-text)' }}>
          Создать логистику
        </h3>

        {error && (
          <div
            className="rounded-lg px-3 py-2 mb-4 text-sm"
            style={{ background: 'var(--color-danger-bg)', color: 'var(--color-danger)' }}
          >
            {error}
          </div>
        )}

        {loading && <div style={{ color: 'var(--color-muted)' }}>Загрузка...</div>}

        {!loading && (!products || products.length === 0) && (
          <div className="text-sm mb-4" style={{ color: 'var(--color-muted)' }}>
            В заказе нет товаров — сначала добавьте товары на вкладке «Товары».
          </div>
        )}

        {!loading && products && products.length > 0 && (
          <ShipmentLinesEditor
            products={products}
            remaining={remaining}
            lines={lines}
            onChange={setLines}
          />
        )}

        <label className="block mb-4">
          <span className="block text-sm mb-1.5" style={{ color: 'var(--color-muted)' }}>Трекинг</span>
          <input
            type="text"
            value={tracking}
            onChange={(e) => setTracking(e.target.value)}
            className="w-full rounded-lg px-3 py-2.5 text-sm outline-none"
            style={{ background: 'var(--color-surface)', border: '1px solid var(--color-border)', color: 'var(--color-text)' }}
          />
        </label>

        <label className="block mb-4">
          <span className="block text-sm mb-1.5" style={{ color: 'var(--color-muted)' }}>Дата отправки</span>
          <input
            type="date"
            value={shipDate}
            onChange={(e) => setShipDate(e.target.value)}
            className="w-full rounded-lg px-3 py-2.5 text-sm outline-none"
            style={{ background: 'var(--color-surface)', border: '1px solid var(--color-border)', color: 'var(--color-text)' }}
          />
        </label>

        <label className="block mb-4">
          <span className="block text-sm mb-1.5" style={{ color: 'var(--color-muted)' }}>Детали</span>
          <textarea
            value={details}
            onChange={(e) => setDetails(e.target.value)}
            rows={2}
            className="w-full rounded-lg px-3 py-2.5 text-sm outline-none resize-none"
            style={{ background: 'var(--color-surface)', border: '1px solid var(--color-border)', color: 'var(--color-text)' }}
          />
        </label>

        <div className="mb-6">
          <span className="block text-sm mb-1.5" style={{ color: 'var(--color-muted)' }}>Файл накладной</span>
          <FileUploader
            files={file ? [file] : []}
            onUpload={(f) => setFile(f)}
            onRemove={() => setFile(null)}
          />
        </div>

        <div className="flex justify-end gap-2">
          <button
            onClick={onClose}
            className="rounded-lg px-4 py-2 text-sm cursor-pointer"
            style={{ background: 'var(--color-surface-3)', color: 'var(--color-text)' }}
          >
            Отмена
          </button>
          <button
            onClick={() => mutation.mutate()}
            disabled={!canSave || mutation.isPending}
            className="rounded-lg px-4 py-2 text-sm font-medium cursor-pointer disabled:opacity-50"
            style={{ background: 'var(--color-primary)', color: '#fff' }}
          >
            {mutation.isPending ? 'Сохранение...' : 'Создать логистику'}
          </button>
        </div>
      </div>
    </div>
  )
}
