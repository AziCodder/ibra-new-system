export type LogisticsStatus = 'in_transit' | 'accepted' | 'cancelled'

export interface LogisticsItem {
  product_id: number
  product_name: string
  quantity: string
}

export interface Logistics {
  id: number
  order_id: number
  /** A shipment carries one or more product lines. */
  items: LogisticsItem[]
  created_by_id: number
  created_by_name: string
  total_quantity: string
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

export interface LogisticsItemInput {
  product_id: number
  quantity: number
}

export interface LogisticsCreate {
  items: LogisticsItemInput[]
  tracking?: string
  ship_date: string
  invoice_file_key?: string | null
  details?: string
}

export interface LogisticsUpdate {
  /** Replaces the shipment's whole line list when present. */
  items?: LogisticsItemInput[]
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

export interface LogisticsSummary extends Logistics {
  order_number: string
  order_currency: string
  client_name: string
  manager_name: string
  manager_id: number
}

export async function fetchAllLogistics(params?: {
  status?: LogisticsStatus
  client_id?: number
  manager_id?: number
  search?: string
  sort?: 'asc' | 'desc'
}): Promise<LogisticsSummary[]> {
  const url = new URL('/api/logistics/', window.location.origin)
  if (params?.status) url.searchParams.set('status', params.status)
  if (params?.client_id != null) url.searchParams.set('client_id', String(params.client_id))
  if (params?.manager_id != null) url.searchParams.set('manager_id', String(params.manager_id))
  if (params?.search) url.searchParams.set('search', params.search)
  if (params?.sort) url.searchParams.set('sort', params.sort)
  const res = await fetch(url.toString(), { credentials: 'include' })
  return handle(res, 'Failed to fetch logistics')
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

export interface TelegramGroupOut {
  group_id: number
  chat_id: string
  title: string
}

export class AmbiguousGroupsError extends Error {
  availableGroups: TelegramGroupOut[]
  constructor(availableGroups: TelegramGroupOut[]) {
    super('Ambiguous notification target: choose one or more groups')
    this.availableGroups = availableGroups
  }
}

export async function notifyLogisticsReceived(
  orderId: number,
  logisticsId: number,
  groupIds?: number[],
): Promise<void> {
  const res = await fetch(`/api/orders/${orderId}/logistics/${logisticsId}/notify-received`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    credentials: 'include',
    body: JSON.stringify({ group_ids: groupIds ?? null }),
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    if (res.status === 409 && err.detail?.available_groups) {
      throw new AmbiguousGroupsError(err.detail.available_groups)
    }
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
