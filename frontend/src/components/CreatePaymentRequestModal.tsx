import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { fetchProducts } from '../api/products'
import { fetchPaymentRequests, createPaymentRequest, type PaymentRequestPriority } from '../api/paymentRequests'
import { fetchClientTelegramGroups } from '../api/clients'
import FileUploader, { type UploadedFile } from './FileUploader'
import TelegramGroupPicker from './TelegramGroupPicker'

const MAX_FILES = 3

const PRIORITY_LABELS: Record<PaymentRequestPriority, string> = {
  low: 'Низкий',
  normal: 'Обычно',
  urgent: 'Срочно',
}

function formatNumber(value: number): string {
  return value.toLocaleString('ru-RU', { maximumFractionDigits: 2 })
}

export default function CreatePaymentRequestModal({
  orderId,
  clientId,
  onClose,
}: {
  orderId: number
  clientId: number
  onClose: () => void
}) {
  const queryClient = useQueryClient()

  const [selected, setSelected] = useState<Record<number, boolean>>({})
  const [amounts, setAmounts] = useState<Record<number, string>>({})
  const [requisites, setRequisites] = useState('')
  const [details, setDetails] = useState('')
  const [priority, setPriority] = useState<PaymentRequestPriority>('normal')
  const [files, setFiles] = useState<UploadedFile[]>([])
  const [selectedGroupIds, setSelectedGroupIds] = useState<number[]>([])
  const [error, setError] = useState('')

  const { data: products, isLoading: productsLoading } = useQuery({
    queryKey: ['products', orderId],
    queryFn: () => fetchProducts(orderId),
  })
  const { data: existingRequests, isLoading: requestsLoading } = useQuery({
    queryKey: ['payment-requests', orderId],
    queryFn: () => fetchPaymentRequests(orderId),
  })
  const { data: telegramGroups } = useQuery({
    queryKey: ['client-telegram-groups', clientId],
    queryFn: () => fetchClientTelegramGroups(clientId),
  })
  const needsGroupChoice = (telegramGroups?.length ?? 0) > 1

  function toggleGroup(groupId: number) {
    setSelectedGroupIds((prev) => (prev.includes(groupId) ? prev.filter((id) => id !== groupId) : [...prev, groupId]))
  }

  const loading = productsLoading || requestsLoading

  const remainingByProduct = new Map<number, number>()
  for (const product of products ?? []) {
    const total = Number(product.quantity) * Number(product.price)
    const alreadyRequested = (existingRequests ?? [])
      .flatMap((r) => r.items)
      .filter((item) => item.product_id === product.id)
      .reduce((sum, item) => sum + Number(item.amount), 0)
    remainingByProduct.set(product.id, total - alreadyRequested)
  }

  const selectedIds = Object.keys(selected).filter((id) => selected[Number(id)]).map(Number)
  const selectedCurrency = selectedIds.length > 0 ? products?.find((p) => p.id === selectedIds[0])?.currency : undefined

  function toggle(productId: number) {
    setSelected((prev) => ({ ...prev, [productId]: !prev[productId] }))
    setAmounts((prev) => {
      if (selected[productId]) return prev
      const remaining = remainingByProduct.get(productId) ?? 0
      return { ...prev, [productId]: remaining.toFixed(2) }
    })
  }

  const totalAmount = selectedIds.reduce((sum, id) => sum + (Number(amounts[id]) || 0), 0)

  const mutation = useMutation({
    mutationFn: () =>
      createPaymentRequest(orderId, {
        requisites,
        details,
        priority,
        file_keys: files.map((f) => f.key),
        items: selectedIds.map((id) => ({ product_id: id, amount: Number(amounts[id]) })),
        group_ids: needsGroupChoice ? selectedGroupIds : undefined,
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['payment-requests', orderId] })
      queryClient.invalidateQueries({ queryKey: ['products', orderId] })
      onClose()
    },
    onError: (err: Error) => setError(err.message),
  })

  const canSave =
    selectedIds.length > 0 &&
    selectedIds.every((id) => Number(amounts[id]) > 0) &&
    requisites.trim() !== '' &&
    (!needsGroupChoice || selectedGroupIds.length > 0)

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
          Создать запрос на оплату
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
          <div className="rounded-[8px] overflow-hidden mb-4" style={{ border: '1px solid var(--color-border)' }}>
            {products.map((product) => {
              const remaining = remainingByProduct.get(product.id) ?? 0
              const disabled =
                remaining <= 0 ||
                (selectedCurrency !== undefined && !selected[product.id] && product.currency !== selectedCurrency)
              return (
                <label
                  key={product.id}
                  className="flex items-center gap-3 px-3 py-2.5 text-sm"
                  style={{
                    borderTop: '1px solid var(--color-border)',
                    color: disabled ? 'var(--color-faint)' : 'var(--color-text)',
                    opacity: disabled ? 0.5 : 1,
                  }}
                >
                  <input
                    type="checkbox"
                    checked={!!selected[product.id]}
                    disabled={disabled}
                    onChange={() => toggle(product.id)}
                  />
                  <span className="flex-1 truncate">{product.name}</span>
                  <span className="text-xs" style={{ color: 'var(--color-muted)' }}>
                    остаток {formatNumber(remaining)} {product.currency}
                  </span>
                  {selected[product.id] && (
                    <input
                      type="number"
                      min="0.000001"
                      step="any"
                      value={amounts[product.id] ?? ''}
                      onChange={(e) => setAmounts((prev) => ({ ...prev, [product.id]: e.target.value }))}
                      className="w-24 rounded-lg px-2 py-1 text-sm text-right outline-none"
                      style={{ background: 'var(--color-surface)', border: '1px solid var(--color-border)', color: 'var(--color-text)' }}
                    />
                  )}
                </label>
              )
            })}
          </div>
        )}

        {selectedIds.length > 0 && (
          <div
            className="flex items-center justify-between rounded-lg px-3 py-2.5 mb-4 text-sm font-semibold"
            style={{ background: 'var(--color-surface-2)', color: 'var(--color-text)' }}
          >
            <span>Итого</span>
            <span style={{ fontVariantNumeric: 'tabular-nums' }}>
              {formatNumber(totalAmount)} {selectedCurrency}
            </span>
          </div>
        )}

        <label className="block mb-4">
          <span className="block text-sm mb-1.5" style={{ color: 'var(--color-muted)' }}>Реквизиты</span>
          <input
            type="text"
            value={requisites}
            onChange={(e) => setRequisites(e.target.value)}
            className="w-full rounded-lg px-3 py-2.5 text-sm outline-none"
            style={{ background: 'var(--color-surface)', border: '1px solid var(--color-border)', color: 'var(--color-text)' }}
          />
        </label>

        <label className="block mb-4">
          <span className="block text-sm mb-1.5" style={{ color: 'var(--color-muted)' }}>Детали платежа</span>
          <textarea
            value={details}
            onChange={(e) => setDetails(e.target.value)}
            rows={2}
            className="w-full rounded-lg px-3 py-2.5 text-sm outline-none resize-none"
            style={{ background: 'var(--color-surface)', border: '1px solid var(--color-border)', color: 'var(--color-text)' }}
          />
        </label>

        <label className="block mb-4">
          <span className="block text-sm mb-1.5" style={{ color: 'var(--color-muted)' }}>Приоритет</span>
          <select
            value={priority}
            onChange={(e) => setPriority(e.target.value as PaymentRequestPriority)}
            className="w-full rounded-lg px-3 py-2.5 text-sm outline-none"
            style={{ background: 'var(--color-surface)', border: '1px solid var(--color-border)', color: 'var(--color-text)' }}
          >
            {(Object.keys(PRIORITY_LABELS) as PaymentRequestPriority[]).map((p) => (
              <option key={p} value={p}>{PRIORITY_LABELS[p]}</option>
            ))}
          </select>
        </label>

        {needsGroupChoice && (
          <div className="mb-4">
            <span className="block text-sm mb-1.5" style={{ color: 'var(--color-muted)' }}>
              Куда отправить уведомление (клиент привязан к нескольким группам)
            </span>
            <TelegramGroupPicker groups={telegramGroups ?? []} selected={selectedGroupIds} onToggle={toggleGroup} />
          </div>
        )}

        <div className="mb-6">
          <span className="block text-sm mb-1.5" style={{ color: 'var(--color-muted)' }}>Файлы (до {MAX_FILES})</span>
          <FileUploader
            files={files}
            context="payment_request"
            disabled={files.length >= MAX_FILES}
            onUpload={(file) => setFiles((prev) => (prev.length >= MAX_FILES ? prev : [...prev, file]))}
            onRemove={(key) => setFiles((prev) => prev.filter((f) => f.key !== key))}
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
            {mutation.isPending ? 'Сохранение...' : 'Создать запрос'}
          </button>
        </div>
      </div>
    </div>
  )
}
