import type { CSSProperties } from 'react'

/**
 * Pulsing placeholder block using design tokens (ДИЗАЙН_СИСТЕМА.md).
 * Used instead of a bare "Загрузка..." / blank so screens never flash white.
 */
export default function Skeleton({
  width = '100%',
  height = 16,
  radius = 8,
  style,
}: {
  width?: number | string
  height?: number | string
  radius?: number
  style?: CSSProperties
}) {
  return (
    <div
      className="animate-pulse"
      style={{
        width,
        height,
        borderRadius: radius,
        background: 'var(--color-surface-2)',
        ...style,
      }}
    />
  )
}

/** A card-shaped skeleton matching the order/list tile footprint. */
export function SkeletonCard({ lines = 3 }: { lines?: number }) {
  return (
    <div
      className="rounded-2xl p-5 flex flex-col gap-3"
      style={{ background: 'var(--color-surface)', border: '1px solid var(--color-border)' }}
    >
      <Skeleton width="55%" height={18} />
      {Array.from({ length: lines }).map((_, i) => (
        <Skeleton key={i} width={i === lines - 1 ? '40%' : '80%'} height={12} />
      ))}
    </div>
  )
}

/** A grid of skeleton cards for list screens while data loads. */
export function SkeletonCardGrid({ count = 6 }: { count?: number }) {
  return (
    <div className="grid gap-4" style={{ gridTemplateColumns: 'repeat(auto-fill, minmax(300px, 1fr))' }}>
      {Array.from({ length: count }).map((_, i) => (
        <SkeletonCard key={i} />
      ))}
    </div>
  )
}

/** Skeleton rows mimicking a data table while loading. */
export function SkeletonTableRows({ rows = 4 }: { rows?: number }) {
  return (
    <div className="rounded-2xl p-4 flex flex-col gap-2" style={{ border: '1px solid var(--color-border)' }}>
      {Array.from({ length: rows }).map((_, i) => (
        <Skeleton key={i} height={44} radius={10} />
      ))}
    </div>
  )
}

/** Skeleton row of metric cards (ProfitBlock). */
export function SkeletonMetricRow({ count = 5 }: { count?: number }) {
  return (
    <div className="flex flex-wrap gap-2">
      {Array.from({ length: count }).map((_, i) => (
        <Skeleton key={i} width={110} height={52} radius={8} />
      ))}
    </div>
  )
}
