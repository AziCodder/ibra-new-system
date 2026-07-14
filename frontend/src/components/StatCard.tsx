import { TrendingUp } from 'lucide-react'

export type StatDeltaTone = 'positive' | 'neutral' | 'warning'

const TONE_COLOR: Record<StatDeltaTone, string> = {
  positive: 'var(--color-success)',
  neutral: 'var(--color-muted)',
  warning: 'var(--color-warning)',
}

export default function StatCard({
  label,
  value,
  delta,
  tone = 'neutral',
}: {
  label: string
  value: string
  delta?: string
  tone?: StatDeltaTone
}) {
  return (
    <div
      className="min-w-0"
      style={{
        background: 'var(--color-surface)',
        border: '1px solid var(--color-border)',
        borderRadius: 'var(--radius-lg)',
        padding: '16px 18px',
      }}
    >
      <div className="text-xs truncate" style={{ color: 'var(--color-muted)' }}>
        {label}
      </div>
      <div className="text-2xl font-bold mt-1.5 truncate" style={{ color: 'var(--color-text)' }}>
        {value}
      </div>
      {delta && (
        <div
          className="flex items-center gap-1 text-xs mt-1.5 font-medium"
          style={{ color: TONE_COLOR[tone] }}
        >
          {tone === 'positive' && <TrendingUp size={12} />}
          {delta}
        </div>
      )}
    </div>
  )
}
