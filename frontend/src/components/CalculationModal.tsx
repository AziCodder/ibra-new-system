import { useRef, useState } from 'react'
import { useMutation, useQuery } from '@tanstack/react-query'
import { X } from 'lucide-react'
import { fetchStaff } from '../api/users'
import { MAX_PARTICIPANTS, MIN_PARTICIPANTS, saveCalculation, type Calculation } from '../api/calculation'

type Row = { key: number; userId: number | ''; percent: string }

/** Up to two decimals, like the server's Numeric(5, 2). */
const PERCENT_PATTERN = /^\d{1,3}(\.\d{1,2})?$/
const FULL_SHARE = 10000 // 100% in hundredths of a percent

const inputStyle = {
  background: 'var(--color-surface)',
  border: '1px solid var(--color-border)',
  color: 'var(--color-text)',
}

function toHundredths(value: string): number {
  return Math.round(Number(value) * 100)
}

function formatMoney(cents: number): string {
  return (cents / 100).toLocaleString('ru-RU', { maximumFractionDigits: 2 })
}

function roundHalfUp(value: number): number {
  return Math.sign(value) * Math.round(Math.abs(value))
}

/** Cents per share, the rounding remainder on the last one — the split the server stores. */
function splitProfit(profitCents: number, percents: number[]): number[] {
  const shares = percents.map((p) => roundHalfUp((profitCents * p) / FULL_SHARE))
  shares[shares.length - 1] += profitCents - shares.reduce((sum, s) => sum + s, 0)
  return shares
}

export default function CalculationModal({
  orderId,
  orderNumber,
  profit,
  currency,
  onClose,
  onSaved,
}: {
  orderId: number
  orderNumber: string
  profit: string
  currency: string
  onClose: () => void
  onSaved: (calculation: Calculation) => void
}) {
  const nextKey = useRef(MIN_PARTICIPANTS)
  const [rows, setRows] = useState<Row[]>(() =>
    Array.from({ length: MIN_PARTICIPANTS }, (_, i) => ({ key: i, userId: '', percent: '' })),
  )
  const [error, setError] = useState('')

  const { data: staff, isLoading: staffLoading } = useQuery({ queryKey: ['users', 'staff'], queryFn: fetchStaff })

  const profitCents = Math.round(Number(profit) * 100)
  const validPercent = (row: Row) => PERCENT_PATTERN.test(row.percent) && toHundredths(row.percent) > 0
  const totalShare = rows.reduce((sum, row) => sum + (validPercent(row) ? toHundredths(row.percent) : 0), 0)
  const allChosen = rows.every((row) => row.userId !== '')
  const allPercentsValid = rows.every(validPercent)
  const balanced = allPercentsValid && totalShare === FULL_SHARE
  const shares = balanced ? splitProfit(profitCents, rows.map((row) => toHundredths(row.percent))) : null
  const canSave = allChosen && balanced

  const mutation = useMutation({
    mutationFn: () =>
      saveCalculation(
        orderId,
        rows.map((row) => ({ user_id: Number(row.userId), percent: row.percent })),
      ),
    onSuccess: onSaved,
    onError: (err: Error) => setError(err.message),
  })

  function updateRow(key: number, patch: Partial<Row>) {
    setRows((current) => current.map((row) => (row.key === key ? { ...row, ...patch } : row)))
  }

  function addRow() {
    setRows((current) => [...current, { key: nextKey.current++, userId: '', percent: '' }])
  }

  function removeRow(key: number) {
    setRows((current) => current.filter((row) => row.key !== key))
  }

  function rowAmount(index: number): string {
    if (shares) return `${formatMoney(shares[index])} ${currency}`
    const row = rows[index]
    if (!validPercent(row)) return '—'
    return `${formatMoney(roundHalfUp((profitCents * toHundredths(row.percent)) / FULL_SHARE))} ${currency}`
  }

  const totalColor =
    totalShare === FULL_SHARE ? 'var(--color-success)' : totalShare > FULL_SHARE ? 'var(--color-danger)' : 'var(--color-warning)'

  let hint = ''
  if (!allChosen) hint = 'Выберите участника в каждой строке'
  else if (!allPercentsValid) hint = 'Укажите каждому участнику процент больше нуля, не больше двух знаков после запятой'
  else if (totalShare !== FULL_SHARE) hint = 'Сумма процентов должна быть ровно 100%'

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
        <h3 className="text-base font-semibold mb-1" style={{ color: 'var(--color-text)' }}>
          Расчёт заказа {orderNumber}
        </h3>
        <div className="text-sm mb-5" style={{ color: 'var(--color-muted)' }}>
          Общая прибыль —{' '}
          <span className="font-semibold" style={{ color: 'var(--color-success)' }}>
            {formatMoney(profitCents)} {currency}
          </span>
        </div>

        {error && (
          <div
            className="rounded-lg px-3 py-2 mb-4 text-sm"
            style={{ background: 'var(--color-danger-bg)', color: 'var(--color-danger)' }}
          >
            {error}
          </div>
        )}

        <div className="text-sm font-semibold mb-2" style={{ color: 'var(--color-text)' }}>Распределение</div>

        <div className="flex flex-col gap-3 mb-3">
          {rows.map((row, index) => {
            const takenByOthers = new Set(rows.filter((other) => other.key !== row.key).map((other) => other.userId))
            const options = (staff ?? []).filter((u) => !takenByOthers.has(u.id))
            return (
              <div key={row.key} className="rounded-lg p-3" style={{ background: 'var(--color-surface-2)' }}>
                <div className="flex items-center justify-between mb-1.5">
                  <span className="text-xs" style={{ color: 'var(--color-muted)' }}>Участник {index + 1}</span>
                  {rows.length > MIN_PARTICIPANTS && (
                    <button
                      onClick={() => removeRow(row.key)}
                      className="cursor-pointer"
                      style={{ color: 'var(--color-faint)' }}
                      aria-label={`Убрать участника ${index + 1}`}
                      title="Убрать участника"
                    >
                      <X size={14} />
                    </button>
                  )}
                </div>
                <div className="flex items-center gap-2 flex-wrap">
                  <select
                    value={row.userId}
                    disabled={staffLoading}
                    onChange={(e) => updateRow(row.key, { userId: e.target.value ? Number(e.target.value) : '' })}
                    className="flex-1 min-w-[160px] rounded-lg px-3 py-2 text-sm outline-none"
                    style={inputStyle}
                  >
                    <option value="">{staffLoading ? 'Загрузка...' : 'Выберите участника'}</option>
                    {options.map((u) => (
                      <option key={u.id} value={u.id}>
                        {u.full_name || u.login}
                        {u.is_active ? '' : ' (неактивен)'}
                      </option>
                    ))}
                  </select>
                  <div className="flex items-center gap-1">
                    <input
                      type="number"
                      min="0"
                      max="100"
                      step="0.01"
                      inputMode="decimal"
                      value={row.percent}
                      onChange={(e) => updateRow(row.key, { percent: e.target.value })}
                      placeholder="0"
                      aria-label={`Процент участника ${index + 1}`}
                      className="w-20 rounded-lg px-3 py-2 text-sm outline-none text-right"
                      style={inputStyle}
                    />
                    <span className="text-sm" style={{ color: 'var(--color-muted)' }}>%</span>
                  </div>
                  <span
                    className="w-28 text-right text-sm font-medium"
                    style={{ color: 'var(--color-text)', fontVariantNumeric: 'tabular-nums' }}
                  >
                    {rowAmount(index)}
                  </span>
                </div>
              </div>
            )
          })}
        </div>

        <button
          onClick={addRow}
          disabled={rows.length >= MAX_PARTICIPANTS}
          className="text-sm font-medium cursor-pointer disabled:opacity-40 disabled:cursor-not-allowed mb-5"
          style={{ color: 'var(--color-primary)' }}
          title={rows.length >= MAX_PARTICIPANTS ? `Не больше ${MAX_PARTICIPANTS} участников` : undefined}
        >
          + Добавить участника
        </button>

        <div className="flex items-center justify-between text-sm mb-1" style={{ fontVariantNumeric: 'tabular-nums' }}>
          <span style={{ color: 'var(--color-muted)' }}>
            Распределено: <span className="font-semibold" style={{ color: totalColor }}>{formatMoney(totalShare)}%</span> из 100%
          </span>
          <span className="font-semibold" style={{ color: 'var(--color-text)' }}>
            Итого: {shares ? `${formatMoney(profitCents)} ${currency}` : '—'}
          </span>
        </div>
        <div className="text-xs mb-5" style={{ color: 'var(--color-faint)', minHeight: 16 }}>{hint}</div>

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
            style={{ background: 'var(--color-success)', color: '#fff' }}
          >
            {mutation.isPending ? 'Сохранение...' : 'Сохранить'}
          </button>
        </div>
      </div>
    </div>
  )
}
