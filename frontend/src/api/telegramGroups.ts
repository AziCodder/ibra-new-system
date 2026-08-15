/** A Telegram chat the bot has been added to, as the admin sees it. */
export interface TelegramGroupAdmin {
  id: number
  chat_id: string
  title: string
  /** false once the bot was removed from the chat — nothing can be delivered there */
  is_active: boolean
  client_ids: number[]
  created_at: string
}

export async function fetchTelegramGroups(): Promise<TelegramGroupAdmin[]> {
  const res = await fetch('/api/telegram-groups/', { credentials: 'include' })
  if (!res.ok) throw new Error('Failed to fetch telegram groups')
  return res.json()
}

/** Replaces the chat's client list with exactly `clientIds`. */
export async function setTelegramGroupClients(
  groupId: number,
  clientIds: number[],
): Promise<TelegramGroupAdmin> {
  const res = await fetch(`/api/telegram-groups/${groupId}/clients`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    credentials: 'include',
    body: JSON.stringify({ client_ids: clientIds }),
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error(err.detail || 'Failed to save clients of the chat')
  }
  return res.json()
}

export async function deleteTelegramGroup(groupId: number): Promise<void> {
  const res = await fetch(`/api/telegram-groups/${groupId}`, {
    method: 'DELETE',
    credentials: 'include',
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error(err.detail || 'Failed to delete the chat')
  }
}
