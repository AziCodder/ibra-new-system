export const CURRENCIES = ['USD', 'CNY', 'RUB']

function formatNumber(value: number): string {
  return value.toLocaleString('ru-RU', { maximumFractionDigits: 2 })
}

const inputStyle = {
  background: 'var(--color-surface)',
  border: '1px solid var(--color-border)',
  color: 'var(--color-text)',
}

/** Currency picker for a product. */
export function CurrencySelect({
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
        style={inputStyle}
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

/**
 * Currency picker for a product, plus an optional rate to the order's currency.
 *
 * The rate is quoted from the product's currency inwards — "1 CNY = ? RUB" — so
 * the number entered is how many order-currency units one product-currency unit
 * buys, and converting into the order's currency multiplies by it. It takes no
 * part in the profit (purchases are valued at each payment's own rate); it only
 * feeds the "total in the order's currency" figures, so it may be left empty.
 *
 * The rate field only appears when the two currencies differ — in the order's own
 * currency the rate is always 1 and the backend rejects anything else.
 */
export default function CurrencyRateFields({
  orderCurrency,
  currency,
  onCurrencyChange,
  exchangeRate,
  onExchangeRateChange,
  amount,
}: {
  orderCurrency: string
  currency: string
  onCurrencyChange: (next: string) => void
  exchangeRate: string
  onExchangeRateChange: (next: string) => void
  /** Product total in `currency`, used for the converted preview. */
  amount: number
}) {
  const isForeign = currency !== orderCurrency
  const rate = Number(exchangeRate)
  const showPreview = isForeign && rate > 0 && amount > 0

  return (
    <>
      <CurrencySelect
        orderCurrency={orderCurrency}
        currency={currency}
        onChange={(next) => {
          onCurrencyChange(next)
          onExchangeRateChange(next === orderCurrency ? '1' : '')
        }}
      />

      {isForeign && (
        <label className="block mb-4">
          <span className="block text-sm mb-1.5" style={{ color: 'var(--color-muted)' }}>
            Курс: 1 {currency} = ? {orderCurrency} (необязательно)
          </span>
          <input
            type="number"
            min="0"
            step="0.01"
            value={exchangeRate}
            onChange={(e) => onExchangeRateChange(e.target.value)}
            className="w-full rounded-lg px-3 py-2.5 text-sm outline-none"
            style={inputStyle}
          />
          <span className="block text-xs mt-1.5" style={{ color: 'var(--color-muted)' }}>
            {showPreview
              ? `${formatNumber(amount)} ${currency} ≈ ${formatNumber(amount * rate)} ${orderCurrency}`
              : `Нужен только для пересчёта итога в ${orderCurrency} — в прибыли не участвует.`}
          </span>
        </label>
      )}
    </>
  )
}
