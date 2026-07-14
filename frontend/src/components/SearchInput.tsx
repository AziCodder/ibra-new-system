import { useEffect, useState } from 'react'
import { Search } from 'lucide-react'

export default function SearchInput({
  value,
  onChange,
  placeholder = 'Поиск...',
  debounceMs = 300,
  className = '',
}: {
  value: string
  onChange: (v: string) => void
  placeholder?: string
  debounceMs?: number
  className?: string
}) {
  const [local, setLocal] = useState(value)

  useEffect(() => setLocal(value), [value])

  useEffect(() => {
    if (local === value) return
    const t = setTimeout(() => onChange(local), debounceMs)
    return () => clearTimeout(t)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [local])

  return (
    <div
      className={`flex items-center gap-2 ${className}`}
      style={{
        height: 36,
        padding: '0 14px',
        background: 'var(--color-surface)',
        border: '1px solid var(--color-border)',
        borderRadius: 999,
        color: 'var(--color-text)',
      }}
    >
      <Search size={15} style={{ color: 'var(--color-faint)', flexShrink: 0 }} />
      <input
        value={local}
        onChange={(e) => setLocal(e.target.value)}
        placeholder={placeholder}
        className="text-sm outline-none w-full min-w-0"
        style={{ background: 'transparent', color: 'var(--color-text)' }}
      />
    </div>
  )
}
