import type { ReactNode } from 'react'

export type TagColor = 'green' | 'blue' | 'orange' | 'purple' | 'red' | 'default'

export default function Tag({ color = 'default', children }: { color?: TagColor; children: ReactNode }) {
  return (
    <span
      className="inline-flex items-center whitespace-nowrap text-xs px-[7px]"
      style={{
        background: `var(--tag-${color}-bg)`,
        border: `1px solid var(--tag-${color}-border)`,
        color: `var(--tag-${color}-text)`,
        borderRadius: 'var(--radius-sm)',
        lineHeight: '20px',
      }}
    >
      {children}
    </span>
  )
}
