import type { TelegramGroupOut } from '../api/clients'

export default function TelegramGroupPicker({
  groups,
  selected,
  onToggle,
}: {
  groups: TelegramGroupOut[]
  selected: number[]
  onToggle: (groupId: number) => void
}) {
  return (
    <div className="rounded-[8px] overflow-hidden" style={{ border: '1px solid var(--color-border)' }}>
      {groups.map((g) => (
        <label
          key={g.group_id}
          className="flex items-center gap-3 px-3 py-2.5 text-sm"
          style={{ borderTop: '1px solid var(--color-border)', color: 'var(--color-text)' }}
        >
          <input type="checkbox" checked={selected.includes(g.group_id)} onChange={() => onToggle(g.group_id)} />
          <span className="flex-1 truncate">{g.title || g.chat_id}</span>
        </label>
      ))}
    </div>
  )
}
