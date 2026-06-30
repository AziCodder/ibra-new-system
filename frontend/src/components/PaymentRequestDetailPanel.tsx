import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { deletePaymentRequest, type PaymentRequest, type PaymentRequestPriority } from '../api/paymentRequests'
import { fetchPayments, createPayment } from '../api/payments'
import FileUploader, { type UploadedFile } from './FileUploader'

const CURRENCIES = ['USD', 'EUR', 'CNY', 'RUB']

const PRIORITY_LABELS: Record<PaymentRequestPriority, string> = {
  low: 'Низкий',
  normal: 'Обычно',
  urgent: 'Срочно',
}

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

export default function PaymentRequestDetailPanel({
  orderId,
  request,
  canEdit,
  onClose,
}: {
  orderId: number
  request: PaymentRequest
  canEdit: boolean
  onClose: () => void
}) {
  const queryClient = useQueryClient()
  const [error, setError] = useState('')
  const [copied, setCopied] = useState(false)

  const [amount, setAmount] = useState('')
  const [currency, setCurrency] = useState(request.currency)
  const [exchangeRate, setExchangeRate] = useState('1')
  const [note, setNote] = useState('')
  const [file, setFile] = useState<UploadedFile | null>(null)

  const { data: payments, isLoading: paymentsLoading } = useQuery({
    queryKey: ['payments', orderId, request.id],
    queryFn: () => fetchPayments(orderId, request.id),
  })

  const paymentMutation = useMutation({
    mutationFn: () =>
      createPayment(orderId, request.id, {
        amount: Number(amount),
        currency,
        exchange_rate: Number(exchangeRate),
        file_key: file?.key ?? null,
        note,
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['payment-requests', orderId] })
      queryClient.invalidateQueries({ queryKey: ['payments', orderId, request.id] })
      setAmount('')
      setExchangeRate('1')
      setNote('')
      setFile(null)
    },
    onError: (err: Error) => setError(err.message),
  })

  const deleteMutation = useMutation({
    mutationFn: () => deletePaymentRequest(orderId, request.id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['payment-requests', orderId] })
      onClose()
    },
    onError: (err: Error) => setError(err.message),
  })

  function handleDelete() {
    if (window.confirm('Удалить запрос на оплату?')) {
      deleteMutation.mutate()
    }
  }

  async function handleCopy() {
    const lines = [
      `Запрос на оплату #${request.id}`,
      `Приоритет: ${PRIORITY_LABELS[request.priority]}`,
      `Реквизиты: ${request.requisites || '—'}`,
      `Детали: ${request.details || '—'}`,
      'Товары:',
      ...request.items.map((item) => `  - ${item.product_name}: ${formatNumber(Number(item.amount))} ${request.currency}`),
      `Итого: ${formatNumber(Number(request.total_amount))} ${request.currency}`,
      `Оплачено: ${formatNumber(Number(request.paid_amount))} ${request.currency}`,
      `Остаток: ${formatNumber(Number(request.remaining_amount))} ${request.currency}`,
    ]
    try {
      await navigator.clipboard.writeText(lines.join('\n'))
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    } catch {
      setError('Не удалось скопировать')
    }
  }

  const canSave = Number(amount) > 0 && Number(exchangeRate) > 0

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
            Запрос на оплату #{request.id}
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

        <div className="rounded-xl p-4 mb-4" style={{ background: 'var(--color-surface-2)' }}>
          <div className="text-xs font-semibold uppercase tracking-wide mb-2" style={{ color: 'var(--color-muted)' }}>
            Товары
          </div>
          {request.items.map((item) => (
            <SummaryRow key={item.id} label={item.product_name} value={`${formatNumber(Number(item.amount))} ${request.currency}`} />
          ))}
          <div style={{ borderTop: '1px solid var(--color-border)', margin: '8px 0' }} />
          <SummaryRow label="Итого" value={`${formatNumber(Number(request.total_amount))} ${request.currency}`} />
          <SummaryRow label="Оплачено" value={`${formatNumber(Number(request.paid_amount))} ${request.currency}`} />
          <SummaryRow label="Остаток" value={`${formatNumber(Number(request.remaining_amount))} ${request.currency}`} />
        </div>

        <div className="rounded-xl p-4 mb-4" style={{ background: 'var(--color-surface-2)' }}>
          <SummaryRow label="Приоритет" value={PRIORITY_LABELS[request.priority]} />
          <SummaryRow label="Реквизиты" value={request.requisites || '—'} />
          {request.details && (
            <p className="text-sm mt-1" style={{ color: 'var(--color-text)' }}>{request.details}</p>
          )}
        </div>

        {request.file_keys.length > 0 && (
          <div className="rounded-xl p-4 mb-4" style={{ background: 'var(--color-surface-2)' }}>
            <div className="text-xs font-semibold uppercase tracking-wide mb-2" style={{ color: 'var(--color-muted)' }}>
              Файлы
            </div>
            <ul className="space-y-1">
              {request.file_keys.map((key) => (
                <li key={key}>
                  <a href={`/api/files/${key}`} target="_blank" rel="noreferrer" className="text-sm" style={{ color: 'var(--color-primary)' }}>
                    {key}
                  </a>
                </li>
              ))}
            </ul>
          </div>
        )}

        <div className="flex gap-2 mb-6">
          <button
            onClick={handleCopy}
            className="flex-1 rounded-lg px-4 py-2 text-sm font-medium cursor-pointer"
            style={{ background: 'var(--color-surface-3)', color: 'var(--color-text)' }}
          >
            {copied ? 'Скопировано ✓' : 'Копировать информацию'}
          </button>
          {canEdit && (
            <button
              onClick={handleDelete}
              disabled={deleteMutation.isPending}
              className="rounded-lg px-4 py-2 text-sm font-medium cursor-pointer disabled:opacity-50"
              style={{ background: 'var(--color-danger-bg)', color: 'var(--color-danger)' }}
            >
              {deleteMutation.isPending ? 'Удаление...' : 'Удалить'}
            </button>
          )}
        </div>

        {canEdit && Number(request.remaining_amount) > 0 && (
          <div className="rounded-xl p-4 mb-4" style={{ background: 'var(--color-surface-2)' }}>
            <div className="text-xs font-semibold uppercase tracking-wide mb-3" style={{ color: 'var(--color-muted)' }}>
              Внести оплату
            </div>

            <div className="grid grid-cols-2 gap-3 mb-3">
              <label className="block">
                <span className="block text-sm mb-1.5" style={{ color: 'var(--color-muted)' }}>Сумма</span>
                <input
                  type="number"
                  min="0"
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
                  onChange={(e) => setCurrency(e.target.value)}
                  className="w-full rounded-lg px-3 py-2.5 text-sm outline-none"
                  style={{ background: 'var(--color-surface)', border: '1px solid var(--color-border)', color: 'var(--color-text)' }}
                >
                  {CURRENCIES.map((c) => <option key={c} value={c}>{c}</option>)}
                </select>
              </label>
            </div>

            <label className="block mb-3">
              <span className="block text-sm mb-1.5" style={{ color: 'var(--color-muted)' }}>Курс (вручную)</span>
              <input
                type="number"
                min="0"
                step="any"
                value={exchangeRate}
                onChange={(e) => setExchangeRate(e.target.value)}
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

            <button
              onClick={() => paymentMutation.mutate()}
              disabled={!canSave || paymentMutation.isPending}
              className="w-full rounded-lg px-4 py-2 text-sm font-medium cursor-pointer disabled:opacity-50"
              style={{ background: 'var(--color-primary)', color: '#fff' }}
            >
              {paymentMutation.isPending ? 'Сохранение...' : 'Внести оплату'}
            </button>
          </div>
        )}

        <div className="rounded-xl p-4" style={{ background: 'var(--color-surface-2)' }}>
          <div className="text-xs font-semibold uppercase tracking-wide mb-2" style={{ color: 'var(--color-muted)' }}>
            История оплат
          </div>
          {paymentsLoading && <div className="text-sm" style={{ color: 'var(--color-muted)' }}>Загрузка...</div>}
          {!paymentsLoading && (!payments || payments.length === 0) && (
            <div className="text-sm" style={{ color: 'var(--color-muted)' }}>Оплат пока нет</div>
          )}
          {!paymentsLoading && payments && payments.length > 0 && (
            <ul className="space-y-2">
              {payments.map((p) => (
                <li key={p.id} className="text-sm" style={{ borderTop: '1px solid var(--color-border)', paddingTop: 8 }}>
                  <div className="flex justify-between">
                    <span style={{ color: 'var(--color-text)' }}>{p.author_name}</span>
                    <span style={{ color: 'var(--color-text)', fontVariantNumeric: 'tabular-nums' }}>
                      {formatNumber(Number(p.amount))} {p.currency}
                    </span>
                  </div>
                  <div style={{ color: 'var(--color-muted)' }}>
                    {new Date(p.created_at).toLocaleString('ru-RU')} · курс {p.exchange_rate}
                    {p.note ? ` · ${p.note}` : ''}
                  </div>
                </li>
              ))}
            </ul>
          )}
        </div>
      </div>
    </div>
  )
}
