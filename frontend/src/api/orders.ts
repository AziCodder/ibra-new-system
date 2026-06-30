export type OrderStatus = 'in_progress' | 'completed' | 'cancelled'

export interface Order {
  id: number
  number: string
  client_id: number
  client_name: string
  manager_id: number
  manager_name: string
  status: OrderStatus
  currency: string
  details: string
  created_at: string
}

export interface OrderListResponse {
  items: Order[]
  total: number
  page: number
  page_size: number
}

export interface OrderFilters {
  client_id?: number
  status?: OrderStatus
  manager_id?: number
  page?: number
  page_size?: number
}

export async function fetchOrders(filters: OrderFilters = {}): Promise<OrderListResponse> {
  const params = new URLSearchParams()
  if (filters.client_id != null) params.set('client_id', String(filters.client_id))
  if (filters.status) params.set('status', filters.status)
  if (filters.manager_id != null) params.set('manager_id', String(filters.manager_id))
  params.set('page', String(filters.page ?? 1))
  params.set('page_size', String(filters.page_size ?? 20))

  const res = await fetch(`/api/orders/?${params.toString()}`, { credentials: 'include' })
  if (!res.ok) throw new Error('Failed to fetch orders')
  return res.json()
}

export async function fetchOrder(id: number): Promise<Order> {
  const res = await fetch(`/api/orders/${id}`, { credentials: 'include' })
  if (!res.ok) throw new Error('Failed to fetch order')
  return res.json()
}

export async function createOrder(data: { client_id: number; currency?: string; details?: string }): Promise<Order> {
  const res = await fetch('/api/orders/', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    credentials: 'include',
    body: JSON.stringify(data),
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error(err.detail || 'Failed to create order')
  }
  return res.json()
}
