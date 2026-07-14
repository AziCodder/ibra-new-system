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
  requested_amount: string | null
  paid_amount: string | null
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
  search?: string
  page?: number
  page_size?: number
}

export async function fetchOrders(filters: OrderFilters = {}): Promise<OrderListResponse> {
  const params = new URLSearchParams()
  if (filters.client_id != null) params.set('client_id', String(filters.client_id))
  if (filters.status) params.set('status', filters.status)
  if (filters.manager_id != null) params.set('manager_id', String(filters.manager_id))
  if (filters.search) params.set('search', filters.search)
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

export async function setOrderStatus(orderId: number, status: OrderStatus): Promise<Order> {
  const res = await fetch(`/api/orders/${orderId}/set-status`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    credentials: 'include',
    body: JSON.stringify({ status }),
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error((err as { detail?: string }).detail || 'Failed to set order status')
  }
  return res.json()
}

export interface OrderStats {
  total_count: number
  total_count_delta_month: number
  in_progress_count: number
  waiting_payment_count: number
  completed_count: number
  completed_pct_month: number | null
  profit_month: Record<string, string>
  profit_month_delta_pct: number | null
}

export async function fetchOrderStats(): Promise<OrderStats> {
  const res = await fetch('/api/orders/stats', { credentials: 'include' })
  if (!res.ok) throw new Error('Failed to fetch order stats')
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
