export interface ActionLogEntry {
  id: number
  actor_id: number
  actor_name: string
  action: string
  entity_type: string
  entity_id: number
  details: string
  created_at: string
}

export async function fetchActionLog(params?: { entity_type?: string; actor_id?: number }): Promise<ActionLogEntry[]> {
  const search = new URLSearchParams()
  if (params?.entity_type) search.set('entity_type', params.entity_type)
  if (params?.actor_id != null) search.set('actor_id', String(params.actor_id))
  const query = search.toString()
  const res = await fetch(`/api/action-log/${query ? `?${query}` : ''}`, { credentials: 'include' })
  if (!res.ok) throw new Error('Failed to fetch action log')
  return res.json()
}
