import { useState } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { X } from 'lucide-react'
import { updatePayment, deletePayment, type Payment } from '../api/payments'
import type { PaymentRequest } from '../api/paymentRequests'
import FileUploader, { type UploadedFile } from './FileUploader'

const CURRENCIES = ['USD', 'EUR', 'CNY', 'RUB']

function formatNumber(value: number): string {
  return value.toLocaleString('ru-RU', { maximumFractionDigits: 2 })
}

function Row({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex justify-between text-sm py-1.5">
      <span style={{ color: 'var(--color-muted)' }}>{label}</span>
      <span style={{ color: 'var(--color-text)', fontVariantNumeric: 'tabular-nums' }}>{value}</span>
    </div>
  )
}

export default function PaymentDetailModal({
  orderId,
  request,
  payment,
  canEdit,
  onClose,
}: {
  orderId: number
  request: PaymentRequest
  payment: Payment
  canEdit: boolean
  onClose: () => void
}) {
  const queryClient = useQueryClient()
  const [editing, setEditing] = useState(false)
  const [error, setError] = useState('')

  const [amount, setAmount] = useState(payment.amount)
  const [currency, setCurrency] = useState(payment.currency)
  const [exchangeRate, setExchangeRate] = useState(payment.exchange_rate)
  const [paidAt, setPaidAt] = useState(payment.paid_at.slice(0, 10))
  const [note, setNote] = useState(payment.note)
  const [file, setFile] = useState<UploadedFile | null>(
    payment.file_key ? { key: payment.file_key, filename: payment.file_key, size: 0 } : null
  )

  function handleCurrencyChange(next: string) {
    setCurrency(next)
    setExchangeRate(next === request.currency ? '1' : '')
  }

  function invalidate() {
    queryClient.invalidateQueries({ queryKey: ['payment-requests', orderId] })
    queryClient.invalidateQueries({ queryKey: ['all-payment-requests'] })
    queryClient.invalidateQueries({ queryKey: ['payments', orderId, request.id] })
  }

  const updateMutation = useMutation({
    mutationFn: () =>
      updatePayment(orderId, request.id, payment.id, {
        amount: Number(amount),
        currency,
        exchange_rate: Number(exchangeRate),
        file_key: file?.key ?? null,
        note,
        paid_at: new Date(paidAt).toISOString(),
      }),
    onSuccess: () => {
      invalidate()
      onClose()
    },
    onError: (err: Error) => setError(err.message),
  })

  const deleteMutation = useMutation({
    mutationFn: () => deletePayment(orderId, request.id, payment.id),
    onSuccess: () => {
      invalidate()
      onClose()
    },
    onError: (err: Error) => setError(err.message),
  })

  function handleDelete() {
    if (window.confirm('Удалить эту оплату? Остаток по запросу пересчитается.')) {
      deleteMutation.mutate()
    }
  }

  const canSave = Number(amount) > 0 && Number(exchangeRate) > 0 && paidAt !== ''
  // The rate is quoted from the request's currency outwards ("1 CNY = ? RUB"),
  // so converting a payment back into it divides.
  const converted = Number(amount) / (Number(exchangeRate) || 1)

  return (
    <div className="fixed inset-0 z-[60] flex items-center justify-center p-4" style={{ background: 'rgba(0,0,0,0.5)' }} onClick={onClose}>
      <div
        onClick={(e) => e.stopPropagation()}
        className="w-full max-w-sm rounded-[10px] p-5 max-h-[90vh] overflow-y-auto"
        style={{ background: 'var(--color-surface)', border: '1px solid var(--color-border)' }}
      >
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-base font-semibold" style={{ color: 'var(--color-text)' }}>
            Оплата #{payment.id}
          </h3>
          <button onClick={onClose} className="cursor-pointer" style={{ color: 'var(--color-muted)' }}><X size={18} /></button>
        </div>

        {error && (
          <div className="rounded-lg px-3 py-2 mb-4 text-sm" style={{ background: 'var(--color-danger-bg)', color: 'var(--color-danger)' }}>
            {error}
          </div>
        )}

        {!editing ? (
          <>
            <div className="rounded-[8px] p-4 mb-4" style={{ background: 'var(--color-surface-2)' }}>
              <Row label="Автор" value={payment.author_name} />
              <Row label="Сумма" value={`${formatNumber(Number(payment.amount))} ${payment.currency}`} />
              <Row
                label="Курс"
                value={payment.currency === request.currency
                  ? String(payment.exchange_rate)
                  : `1 ${request.currency} = ${payment.exchange_rate} ${payment.currency}`}
              />
              {payment.currency !== request.currency && (
                <Row label="В валюте запроса" value={`${formatNumber(converted)} ${request.currency}`} />
              )}
              <Row label="Дата оплаты" value={new Date(payment.paid_at).toLocaleDateString('ru-RU')} />
              {payment.note && (
                <div className="pt-2 mt-1 text-sm" style={{ borderTop: '1px solid var(--color-border)', color: 'var(--color-text)' }}>
                  {payment.note}
                </div>
              )}
              {payment.file_key && (
                <div className="pt-2 mt-1" style={{ borderTop: payment.note ? undefined : '1px solid var(--color-border)' }}>
                  <a href={`/api/files/${payment.file_key}`} target="_blank" rel="noreferrer" className="text-sm" style={{ color: 'var(--color-primary)' }}>
                    Открыть файл
                  </a>
                </div>
              )}
            </div>

            {canEdit && (
              <div className="flex gap-2">
                <button
                  onClick={() => setEditing(true)}
                  className="flex-1 rounded-lg px-4 py-2 text-sm font-medium cursor-pointer"
                  style={{ background: 'var(--color-surface-3)', color: 'var(--color-text)' }}
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
        ) : (
          <>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 mb-3">
              <label className="block">
                <span className="block text-sm mb-1.5" style={{ color: 'var(--color-muted)' }}>Сумма</span>
                <input
                  type="number"
                  min="0.000001"
                  step="any"
                  value={amount}
                  onChange={(e) => setAmount(e.target.value)}
                  className="w-full rounded-lg px-3 py-2.5 text-sm outline-none"
                  style={{ background: 'var(--color-surface)', border: '1px solid var(--color-border)', color: 'var(--color-text)' }}
                />
              </label>
              <label className="block">
                <span className="block text-sm mb-1.5" style={{ color: 'var(--color-muted)' }}>Валюта</span>
                <select
                  value={currency}
                  onChange={(e) => handleCurrencyChange(e.target.value)}
                  className="w-full rounded-lg px-3 py-2.5 text-sm outline-none"
                  style={{ background: 'var(--color-surface)', border: '1px solid var(--color-border)', color: 'var(--color-text)' }}
                >
                  {CURRENCIES.map((c) => <option key={c} value={c}>{c}</option>)}
                </select>
              </label>
            </div>

            <label className="block mb-1.5">
              <span className="block text-sm mb-1.5" style={{ color: 'var(--color-muted)' }}>Курс (вручную)</span>
              <input
                type="number"
                min="0.000001"
                step="any"
                placeholder={currency !== request.currency ? `1 ${request.currency} = ? ${currency}` : undefined}
                value={exchangeRate}
                onChange={(e) => setExchangeRate(e.target.value)}
                className="w-full rounded-lg px-3 py-2.5 text-sm outline-none"
                style={{
                  background: 'var(--color-surface)',
                  border: currency !== request.currency && !exchangeRate ? '1px solid var(--color-danger)' : '1px solid var(--color-border)',
                  color: 'var(--color-text)',
                }}
              />
            </label>
            {currency !== request.currency && (
              <div className="text-xs mb-3" style={{ color: 'var(--color-muted)' }}>
                Валюта платежа отличается от валюты запроса ({request.currency}) — курс обязателен.
              </div>
            )}
            {currency === request.currency && <div className="mb-3" />}

            <label className="block mb-3">
              <span className="block text-sm mb-1.5" style={{ color: 'var(--color-muted)' }}>Дата оплаты</span>
              <input
                type="date"
                value={paidAt}
                onChange={(e) => setPaidAt(e.target.value)}
                className="w-full rounded-lg px-3 py-2.5 text-sm outline-none"
                style={{ background: 'var(--color-surface)', border: '1px solid var(--color-border)', color: 'var(--color-text)' }}
              />
            </label>

            <label className="block mb-3">
              <span className="block text-sm mb-1.5" style={{ color: 'var(--color-muted)' }}>Примечание</span>
              <textarea
                value={note}
                onChange={(e) => setNote(e.target.value)}
                rows={2}
                className="w-full rounded-lg px-3 py-2.5 text-sm outline-none resize-none"
                style={{ background: 'var(--color-surface)', border: '1px solid var(--color-border)', color: 'var(--color-text)' }}
              />
            </label>

            <div className="mb-4">
              <span className="block text-sm mb-1.5" style={{ color: 'var(--color-muted)' }}>Файл</span>
              <FileUploader
                files={file ? [file] : []}
                onUpload={(f) => setFile(f)}
                onRemove={() => setFile(null)}
              />
            </div>

            <div className="flex gap-2">
              <button
                onClick={() => setEditing(false)}
                className="flex-1 rounded-lg px-4 py-2 text-sm cursor-pointer"
                style={{ background: 'var(--color-surface-3)', color: 'var(--color-text)' }}
              >
                Отмена
              </button>
              <button
                onClick={() => updateMutation.mutate()}
                disabled={!canSave || updateMutation.isPending}
                className="flex-1 rounded-lg px-4 py-2 text-sm font-medium cursor-pointer disabled:opacity-50"
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
