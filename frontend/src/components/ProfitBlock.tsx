import { useQuery } from '@tanstack/react-query'
import { fetchOrderProfit } from '../api/profit'
import { SkeletonMetricRow } from './Skeleton'
import ErrorState from './ErrorState'

function fmtAmount(val: string, currency: string) {
  const n = parseFloat(val)
  return `${n.toLocaleString('ru-RU', { maximumFractionDigits: 2 })} ${currency}`
}

function MetricCard({
  label,
  value,
  currency,
  highlight,
}: {
  label: string
  value: string
  currency: string
  highlight?: boolean
}) {
  return (
    <div
      style={{
        background: highlight ? 'var(--color-success-bg)' : 'var(--color-surface-2)',
        borderRadius: 'var(--radius)',
        padding: '8px 14px',
        minWidth: 110,
        flex: '1 1 auto',
      }}
    >
      <div style={{ fontSize: 11, color: 'var(--color-faint)', marginBottom: 4 }}>{label}</div>
      <div
        style={{
          fontSize: 14,
          fontWeight: 600,
          color: highlight ? 'var(--color-success)' : 'var(--color-text)',
        }}
      >
        {fmtAmount(value, currency)}
      </div>
    </div>
  )
}

function Op({ children }: { children: string }) {
  return (
    <span style={{ color: 'var(--color-faint)', fontSize: 18, fontWeight: 300, alignSelf: 'center' }}>
      {children}
    </span>
  )
}

export default function ProfitBlock({ orderId }: { orderId: number }) {
  const { data, isLoading, isError, refetch } = useQuery({
    queryKey: ['profit', orderId],
    queryFn: () => fetchOrderProfit(orderId),
    staleTime: 60_000,
  })

  return (
    <div
      style={{
        background: 'var(--color-surface)',
        border: '1px solid var(--color-border)',
        borderRadius: 'var(--radius-lg)',
        padding: '16px 20px',
        marginBottom: '20px',
      }}
    >
      {isLoading && <SkeletonMetricRow />}

      {!isLoading && isError && (
        <ErrorState message="Не удалось загрузить итоги" onRetry={() => refetch()} />
      )}

      {!isLoading && !isError && data && !data.is_ready && (
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: 8,
            background: 'var(--color-warning-bg)',
            border: '1px solid rgba(245,158,11,.3)',
            borderRadius: 'var(--radius)',
            padding: '10px 14px',
            color: 'var(--color-warning)',
            fontSize: 13,
          }}
        >
          Итоги посчитаются после приёмки всей логистики
        </div>
      )}

      {!isLoading && !isError && data && data.is_ready && (
        <>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8, alignItems: 'center' }}>
            <MetricCard label="Доходы" value={data.income} currency={data.currency} />
            <Op>−</Op>
            <MetricCard label="Закупки" value={data.purchases} currency={data.currency} />
            <Op>−</Op>
            <MetricCard label="Логистика" value={data.logistics} currency={data.currency} />
            <Op>−</Op>
            <MetricCard label="Расходы" value={data.other_expenses} currency={data.currency} />
            <Op>=</Op>
            <MetricCard label="Чистая прибыль" value={data.profit} currency={data.currency} highlight />
          </div>

          {(data.profit_pct != null || data.processing_days != null) && (
            <div style={{ marginTop: 10, display: 'flex', gap: 16, fontSize: 12 }}>
              {data.profit_pct != null && (
                <span style={{ color: 'var(--color-success)', fontWeight: 600 }}>
                  {parseFloat(data.profit_pct).toFixed(2)}% прибыли
                </span>
              )}
              {data.processing_days != null && (
                <span style={{ color: 'var(--color-muted)' }}>
                  {data.processing_days} {data.processing_days === 1 ? 'день' : 'дней'} в обработке
                </span>
              )}
            </div>
          )}
        </>
      )}
    </div>
  )
}
