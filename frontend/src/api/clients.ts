export interface Client {
  id: number
  code: string
  full_name: string
  description: string
  telegram_group_link: string
}

export interface ClientCreate {
  code: string
  full_name: string
  description?: string
  telegram_group_link?: string
}

export async function fetchClients(): Promise<Client[]> {
  const res = await fetch('/api/clients/', { credentials: 'include' })
  if (!res.ok) throw new Error('Failed to fetch clients')
  return res.json()
}

export async function createClient(data: ClientCreate): Promise<Client> {
  const res = await fetch('/api/clients/', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    credentials: 'include',
    body: JSON.stringify(data),
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error(err.detail || 'Failed to create client')
  }
  return res.json()
}
