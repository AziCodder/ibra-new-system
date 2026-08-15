import { useState } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { createLedgerEntry, type LedgerEntryType } from '../api/ledgerEntries'

const CURRENCIES = ['USD', 'EUR', 'CNY', 'RUB']

function formatNumber(value: number): string {
  return value.toLocaleString('ru-RU', { maximumFractionDigits: 2 })
}

export default function CreateLedgerEntryModal({
  orderId,
  type,
  orderCurrency,
  onClose,
}: {
  orderId: number
  type: LedgerEntryType
  orderCurrency: string
  onClose: () => void
}) {
  const queryClient = useQueryClient()

  const [amount, setAmount] = useState('')
  const [currency, setCurrency] = useState(orderCurrency)
  const [exchangeRate, setExchangeRate] = useState('1')
  const [details, setDetails] = useState('')
  const [error, setError] = useState('')

  const mutation = useMutation({
    mutationFn: () =>
      createLedgerEntry(orderId, {
        type,
        amount: Number(amount),
        currency,
        exchange_rate: Number(exchangeRate),
        details,
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['ledger-entries', orderId] })
      onClose()
    },
    onError: (err: Error) => setError(err.message),
  })

  const canSave = Number(amount) > 0 && Number(exchangeRate) > 0

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
          {type === 'income' ? 'Добавить доход' : 'Добавить расход'}
        </h3>

        {error && (
          <div
            className="rounded-lg px-3 py-2 mb-4 text-sm"
            style={{ background: 'var(--color-danger-bg)', color: 'var(--color-danger)' }}
          >
            {error}
          </div>
        )}

        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 mb-4">
          <label className="block">
            <span className="block text-sm mb-1.5" style={{ color: 'var(--color-muted)' }}>Сумма</span>
            <input
              type="number"
              min="0"
              step="1"
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
              onChange={(e) => {
                setCurrency(e.target.value)
                // In the order's own currency the rate is 1; anywhere else the
                // old value would silently apply to a different pair.
                setExchangeRate(e.target.value === orderCurrency ? '1' : '')
              }}
              className="w-full rounded-lg px-3 py-2.5 text-sm outline-none"
              style={{ background: 'var(--color-surface)', border: '1px solid var(--color-border)', color: 'var(--color-text)' }}
            >
              {CURRENCIES.map((c) => <option key={c} value={c}>{c}</option>)}
            </select>
          </label>
        </div>

        <label className="block mb-4">
          <span className="block text-sm mb-1.5" style={{ color: 'var(--color-muted)' }}>
            {currency === orderCurrency ? 'Курс (вручную)' : `Курс: 1 ${currency} = ? ${orderCurrency}`}
          </span>
          <input
            type="number"
            min="0"
            step="0.01"
            value={exchangeRate}
            onChange={(e) => setExchangeRate(e.target.value)}
            className="w-full rounded-lg px-3 py-2.5 text-sm outline-none"
            style={{ background: 'var(--color-surface)', border: '1px solid var(--color-border)', color: 'var(--color-text)' }}
          />
          {currency !== orderCurrency && (
            <span className="block text-xs mt-1.5" style={{ color: 'var(--color-muted)' }}>
              {Number(amount) > 0 && Number(exchangeRate) > 0
                ? `${formatNumber(Number(amount))} ${currency} ≈ ${formatNumber(Number(amount) * Number(exchangeRate))} ${orderCurrency}`
                : `Валюта отличается от валюты заказа (${orderCurrency}) — курс обязателен.`}
            </span>
          )}
        </label>

        <label className="block mb-6">
          <span className="block text-sm mb-1.5" style={{ color: 'var(--color-muted)' }}>Детали</span>
          <textarea
            value={details}
            onChange={(e) => setDetails(e.target.value)}
            rows={2}
            className="w-full rounded-lg px-3 py-2.5 text-sm outline-none resize-none"
            style={{ background: 'var(--color-surface)', border: '1px solid var(--color-border)', color: 'var(--color-text)' }}
          />
        </label>

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
            {mutation.isPending ? 'Сохранение...' : 'Сохранить'}
          </button>
        </div>
      </div>
    </div>
  )
}
