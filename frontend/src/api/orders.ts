import { extractErrorMessage, extractErrorDetail, HttpError } from './errors'

const KNOWN_MESSAGES: Record<string, string> = {
  'Client not found': 'Клиент не найден',
  'Manager not found': 'Менеджер не найден',
  'Order not found': 'Заказ не найден',
  'Target user must have the manager or admin role': 'Указанный пользователь должен быть менеджером или администратором',
  'Only admins can assign a different manager': 'Только администратор может назначить другого менеджера',
  'Observers cannot create orders': 'Наблюдатели не могут создавать заказы',
  'Observers cannot change order status': 'Наблюдатели не могут менять статус заказа',
  'Only admins can mark an order as completed': 'Только администратор может завершить заказ',
  'Only admins can revert a cancelled order': 'Только администратор может вернуть отменённый заказ в работу',
  'Only admins can revert a completed order': 'Только администратор может вернуть завершённый заказ в работу',
  'A completed order cannot be cancelled': 'Завершённый заказ нельзя отменить — сначала верните его в работу',
  'Cannot complete: not all logistics accepted or payment requests not fully paid':
    'Нельзя завершить заказ — не вся логистика принята или не все запросы на оплату оплачены полностью',
}

const DEPENDENCY_LABELS: Record<string, string> = {
  payment_requests: 'запросы на оплату',
  logistics: 'логистика',
  ledger_entries: 'записи ДиР',
}

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
  file_keys: string[]
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

/** `manual` — личный порядок пользователя, заданный перетаскиванием карточек. */
export type OrderSortBy = 'created_at' | 'number' | 'manual'
export type OrderSortOrder = 'asc' | 'desc'

export interface OrderFilters {
  client_id?: number
  status?: OrderStatus
  manager_id?: number
  search?: string
  sort_by?: OrderSortBy
  sort_order?: OrderSortOrder
  page?: number
  page_size?: number
}

export async function fetchOrders(filters: OrderFilters = {}): Promise<OrderListResponse> {
  const params = new URLSearchParams()
  if (filters.client_id != null) params.set('client_id', String(filters.client_id))
  if (filters.status) params.set('status', filters.status)
  if (filters.manager_id != null) params.set('manager_id', String(filters.manager_id))
  if (filters.search) params.set('search', filters.search)
  if (filters.sort_by) params.set('sort_by', filters.sort_by)
  if (filters.sort_order) params.set('sort_order', filters.sort_order)
  params.set('page', String(filters.page ?? 1))
  params.set('page_size', String(filters.page_size ?? 20))

  const res = await fetch(`/api/orders/?${params.toString()}`, { credentials: 'include' })
  if (!res.ok) throw new Error('Failed to fetch orders')
  return res.json()
}

/** Сохранить личный порядок заказов: id видимой страницы в новом порядке. */
export async function reorderOrders(orderIds: number[]): Promise<void> {
  const res = await fetch('/api/orders/reorder', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    credentials: 'include',
    body: JSON.stringify({ order_ids: orderIds }),
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error(extractErrorMessage(err, 'Не удалось изменить порядок заказов', KNOWN_MESSAGES))
  }
}

export async function fetchOrder(id: number): Promise<Order> {
  const res = await fetch(`/api/orders/${id}`, { credentials: 'include' })
  if (!res.ok) {
    throw new HttpError(res.status, res.status === 404 ? 'Заказ не найден' : 'Не удалось загрузить заказ')
  }
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
    throw new Error(extractErrorMessage(err, 'Не удалось изменить статус заказа', KNOWN_MESSAGES))
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

export async function createOrder(
  data: { client_id: number; currency?: string; details?: string; manager_id?: number; file_keys?: string[] }
): Promise<Order> {
  const res = await fetch('/api/orders/', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    credentials: 'include',
    body: JSON.stringify(data),
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error(extractErrorMessage(err, 'Не удалось создать заказ', KNOWN_MESSAGES))
  }
  return res.json()
}

export async function updateOrder(
  orderId: number,
  data: { details: string; manager_id?: number }
): Promise<Order> {
  const res = await fetch(`/api/orders/${orderId}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    credentials: 'include',
    body: JSON.stringify(data),
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error(extractErrorMessage(err, 'Не удалось обновить заказ', KNOWN_MESSAGES))
  }
  return res.json()
}

export async function deleteOrder(orderId: number): Promise<void> {
  const res = await fetch(`/api/orders/${orderId}`, { method: 'DELETE', credentials: 'include' })
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    const breakdown = extractErrorDetail<Record<string, number>>(err, 'breakdown')
    if (breakdown) {
      const parts = Object.entries(breakdown)
        .filter(([, count]) => count > 0)
        .map(([key, count]) => `${DEPENDENCY_LABELS[key] ?? key} (${count} шт.)`)
      if (parts.length > 0) {
        throw new Error(`Нельзя удалить заказ — с ним связаны: ${parts.join(', ')}. Удаление возможно только когда у заказа не осталось ни одной связанной записи.`)
      }
    }
    throw new Error(extractErrorMessage(err, 'Не удалось удалить заказ', KNOWN_MESSAGES))
  }
}

export async function addOrderFile(orderId: number, fileKey: string): Promise<Order> {
  const res = await fetch(`/api/orders/${orderId}/files`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    credentials: 'include',
    body: JSON.stringify({ file_key: fileKey }),
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error(extractErrorMessage(err, 'Не удалось прикрепить файл', KNOWN_MESSAGES))
  }
  return res.json()
}

export async function removeOrderFile(orderId: number, fileKey: string): Promise<Order> {
  const res = await fetch(`/api/orders/${orderId}/files/${encodeURIComponent(fileKey)}`, {
    method: 'DELETE',
    credentials: 'include',
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error(extractErrorMessage(err, 'Не удалось удалить файл', KNOWN_MESSAGES))
  }
  return res.json()
}
