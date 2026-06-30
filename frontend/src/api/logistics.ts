export type LogisticsStatus = 'in_transit' | 'accepted' | 'cancelled'

export interface Logistics {
  id: number
  order_id: number
  product_id: number
  product_name: string
  created_by_id: number
  created_by_name: string
  quantity: string
  tracking: string
  ship_date: string
  invoice_file_key: string | null
  details: string
  status: LogisticsStatus
  received_date: string | null
  expense_amount: string | null
  currency: string | null
  exchange_rate: string | null
  acceptance_note: string | null
  created_at: string
}

export interface LogisticsCreate {
  product_id: number
  quantity: number
  tracking?: string
  ship_date: string
  invoice_file_key?: string | null
  details?: string
}

export interface LogisticsUpdate {
  quantity?: number
  tracking?: string
  ship_date?: string
  invoice_file_key?: string | null
  details?: string
  status?: LogisticsStatus
}

export interface LogisticsAccept {
  received_date: string
  expense_amount: number
  currency: string
  exchange_rate: number
  note?: string
}

export interface LogisticsComment {
  id: number
  logistics_id: number
  author_id: number
  author_name: string
  text: string
  created_at: string
}

async function handle<T>(res: Response, fallback: string): Promise<T> {
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error(err.detail || fallback)
  }
  return res.json()
}

export async function fetchLogistics(orderId: number): Promise<Logistics[]> {
  const res = await fetch(`/api/orders/${orderId}/logistics/`, { credentials: 'include' })
  return handle(res, 'Failed to fetch logistics')
}

export async function createLogistics(orderId: number, data: LogisticsCreate): Promise<Logistics> {
  const res = await fetch(`/api/orders/${orderId}/logistics/`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    credentials: 'include',
    body: JSON.stringify(data),
  })
  return handle(res, 'Failed to create logistics')
}

export async function updateLogistics(orderId: number, logisticsId: number, data: LogisticsUpdate): Promise<Logistics> {
  const res = await fetch(`/api/orders/${orderId}/logistics/${logisticsId}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    credentials: 'include',
    body: JSON.stringify(data),
  })
  return handle(res, 'Failed to update logistics')
}

export async function deleteLogistics(orderId: number, logisticsId: number): Promise<void> {
  const res = await fetch(`/api/orders/${orderId}/logistics/${logisticsId}`, {
    method: 'DELETE',
    credentials: 'include',
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error(err.detail || 'Failed to delete logistics')
  }
}

export async function acceptLogistics(orderId: number, logisticsId: number, data: LogisticsAccept): Promise<Logistics> {
  const res = await fetch(`/api/orders/${orderId}/logistics/${logisticsId}/accept`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    credentials: 'include',
    body: JSON.stringify(data),
  })
  return handle(res, 'Failed to accept logistics')
}

export async function unacceptLogistics(orderId: number, logisticsId: number): Promise<Logistics> {
  const res = await fetch(`/api/orders/${orderId}/logistics/${logisticsId}/unaccept`, {
    method: 'POST',
    credentials: 'include',
  })
  return handle(res, 'Failed to unaccept logistics')
}

export async function notifyLogisticsReceived(orderId: number, logisticsId: number): Promise<void> {
  const res = await fetch(`/api/orders/${orderId}/logistics/${logisticsId}/notify-received`, {
    method: 'POST',
    credentials: 'include',
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error(err.detail || 'Failed to send notification')
  }
}

export async function fetchLogisticsComments(orderId: number, logisticsId: number): Promise<LogisticsComment[]> {
  const res = await fetch(`/api/orders/${orderId}/logistics/${logisticsId}/comments`, { credentials: 'include' })
  return handle(res, 'Failed to fetch comments')
}

export async function createLogisticsComment(orderId: number, logisticsId: number, text: string): Promise<LogisticsComment> {
  const res = await fetch(`/api/orders/${orderId}/logistics/${logisticsId}/comments`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    credentials: 'include',
    body: JSON.stringify({ text }),
  })
  return handle(res, 'Failed to add comment')
}
