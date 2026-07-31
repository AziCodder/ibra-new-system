export type NotificationStatus = 'sent' | 'failed'

export interface NotificationLogEntry {
  id: number
  target: string
  message: string
  status: NotificationStatus
  error: string
  created_at: string
}

export async function fetchNotificationLog(params?: { status?: NotificationStatus }): Promise<NotificationLogEntry[]> {
  const search = new URLSearchParams()
  if (params?.status) search.set('status', params.status)
  const query = search.toString()
  const res = await fetch(`/api/notifications/log${query ? `?${query}` : ''}`, { credentials: 'include' })
  if (!res.ok) throw new Error('Failed to fetch notification log')
  return res.json()
}
