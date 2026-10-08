const CURRENCIES = ['USD', 'CNY', 'RUB']

/** Currency picker for a product. No rate is asked for — it takes no part in the profit. */
export default function CurrencySelect({
  orderCurrency,
  currency,
  onChange,
}: {
  orderCurrency: string
  currency: string
  onChange: (next: string) => void
}) {
  return (
    <label className="block mb-4">
      <span className="block text-sm mb-1.5" style={{ color: 'var(--color-muted)' }}>Валюта товара</span>
      <select
        value={currency}
        onChange={(e) => onChange(e.target.value)}
        className="w-full rounded-lg px-3 py-2.5 text-sm outline-none"
        style={{ background: 'var(--color-surface)', border: '1px solid var(--color-border)', color: 'var(--color-text)' }}
      >
        {CURRENCIES.map((c) => (
          <option key={c} value={c}>
            {c}
            {c === orderCurrency ? ' — валюта заказа' : ''}
          </option>
        ))}
      </select>
    </label>
  )
}
