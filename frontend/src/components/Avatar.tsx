function initials(name: string): string {
  const parts = name.trim().split(/\s+/).filter(Boolean)
  if (parts.length === 0) return '?'
  if (parts.length === 1) return parts[0]!.slice(0, 2).toUpperCase()
  return (parts[0]![0]! + parts[1]![0]!).toUpperCase()
}

export default function Avatar({
  name,
  size = 32,
  background,
  color = '#ffffff',
  title,
}: {
  name: string
  size?: number
  background?: string
  color?: string
  title?: string
}) {
  return (
    <div
      className="flex items-center justify-center flex-shrink-0 font-semibold"
      style={{
        width: size,
        height: size,
        borderRadius: '50%',
        background: background ?? 'var(--color-primary)',
        color,
        fontSize: size * 0.4,
        lineHeight: 1,
      }}
      title={title ?? name}
    >
      {initials(name)}
    </div>
  )
}
