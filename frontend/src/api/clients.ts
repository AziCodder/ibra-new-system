export interface Client {
  id: number
  code: string
  full_name: string
  description: string
  telegram_group_link: string
  telegram_chat_id: string
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

export async function generateTelegramLink(clientId: number): Promise<{ token: string; expires_in_hours: number }> {
  const res = await fetch(`/api/clients/${clientId}/telegram-link`, {
    method: 'POST',
    credentials: 'include',
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error(err.detail || 'Failed to generate link')
  }
  return res.json()
}

export interface ClientUpdate {
  full_name?: string
  description?: string
  telegram_group_link?: string
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

export async function updateClient(id: number, data: ClientUpdate): Promise<Client> {
  const res = await fetch(`/api/clients/${id}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    credentials: 'include',
    body: JSON.stringify(data),
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error(err.detail || 'Failed to update client')
  }
  return res.json()
}

export async function deleteClient(id: number): Promise<void> {
  const res = await fetch(`/api/clients/${id}`, { method: 'DELETE', credentials: 'include' })
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error(err.detail || 'Failed to delete client')
  }
}
