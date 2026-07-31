import { extractErrorMessage, extractErrorDetail } from './errors'

export interface Client {
  id: number
  code: string
  full_name: string
  description: string
  telegram_group_link: string
  telegram_chat_id: string
  telegram_groups: string[]
}

export interface ClientCreate {
  full_name: string
  description?: string
  telegram_group_link?: string
}

export async function fetchClients(): Promise<Client[]> {
  const res = await fetch('/api/clients/', { credentials: 'include' })
  if (!res.ok) throw new Error('Не удалось загрузить клиентов')
  return res.json()
}

export async function generateTelegramLink(clientId: number): Promise<{ token: string; expires_in_hours: number }> {
  const res = await fetch(`/api/clients/${clientId}/telegram-link`, {
    method: 'POST',
    credentials: 'include',
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error(extractErrorMessage(err, 'Не удалось создать ссылку'))
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
    throw new Error(extractErrorMessage(err, 'Не удалось создать клиента'))
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
    throw new Error(extractErrorMessage(err, 'Не удалось обновить клиента'))
  }
  return res.json()
}

export async function deleteClient(id: number): Promise<void> {
  const res = await fetch(`/api/clients/${id}`, { method: 'DELETE', credentials: 'include' })
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    const orderNumbers = extractErrorDetail<string[]>(err, 'order_numbers')
    if (orderNumbers && orderNumbers.length > 0) {
      const orderCount = extractErrorDetail<number>(err, 'order_count') ?? orderNumbers.length
      const shown = orderNumbers.join(', ')
      const more = orderCount > orderNumbers.length ? ` и ещё ${orderCount - orderNumbers.length}` : ''
      throw new Error(`Нельзя удалить клиента — за ним закреплены заказы: ${shown}${more}. Удаление возможно только когда за клиентом не остаётся ни одного заказа (включая связанные заявки на оплату).`)
    }
    throw new Error(extractErrorMessage(err, 'Не удалось удалить клиента'))
  }
}

export interface TelegramGroupOut {
  group_id: number
  chat_id: string
  title: string
}

export async function fetchClientTelegramGroups(clientId: number): Promise<TelegramGroupOut[]> {
  const res = await fetch(`/api/clients/${clientId}/telegram-groups`, { credentials: 'include' })
  if (!res.ok) throw new Error('Failed to fetch client telegram groups')
  return res.json()
}
