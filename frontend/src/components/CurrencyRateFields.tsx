export const CURRENCIES = ['USD', 'EUR', 'CNY', 'RUB']

function formatNumber(value: number): string {
  return value.toLocaleString('ru-RU', { maximumFractionDigits: 2 })
}

const inputStyle = {
  background: 'var(--color-surface)',
  border: '1px solid var(--color-border)',
  color: 'var(--color-text)',
}

/**
 * Currency picker for a product, plus the rate to the order's currency.
 *
 * The rate is quoted from the order's currency outwards — "1 CNY = ? RUB" — so
 * the number entered is how many product-currency units one order-currency unit
 * buys, and converting back into the order's currency divides by it.
 *
 * The rate field only appears when the two currencies differ — in the order's own
 * currency the rate is always 1 and the backend rejects anything else, so showing
 * the input there would only invite a wrong answer.
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
      <label className="block mb-4">
        <span className="block text-sm mb-1.5" style={{ color: 'var(--color-muted)' }}>Валюта товара</span>
        <select
          value={currency}
          onChange={(e) => {
            onCurrencyChange(e.target.value)
            onExchangeRateChange(e.target.value === orderCurrency ? '1' : '')
          }}
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

      {isForeign && (
        <label className="block mb-4">
          <span className="block text-sm mb-1.5" style={{ color: 'var(--color-muted)' }}>
            Курс: 1 {orderCurrency} = ? {currency}
          </span>
          <input
            type="number"
            min="0.000001"
            step="any"
            value={exchangeRate}
            onChange={(e) => onExchangeRateChange(e.target.value)}
            className="w-full rounded-lg px-3 py-2.5 text-sm outline-none"
            style={{
              ...inputStyle,
              border: rate > 0 ? '1px solid var(--color-border)' : '1px solid var(--color-danger)',
            }}
          />
          <span className="block text-xs mt-1.5" style={{ color: 'var(--color-muted)' }}>
            {showPreview
              ? `${formatNumber(amount)} ${currency} ≈ ${formatNumber(amount / rate)} ${orderCurrency}`
              : `Валюта товара отличается от валюты заказа (${orderCurrency}) — курс обязателен.`}
          </span>
        </label>
      )}
    </>
  )
}
