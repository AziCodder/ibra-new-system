export type PaymentRequestPriority = 'low' | 'normal' | 'urgent'

export interface PaymentRequestItem {
  id: number
  product_id: number
  product_name: string
  amount: string
}

export interface PaymentRequest {
  id: number
  order_id: number
  created_by_id: number
  created_by_name: string
  requisites: string
  details: string
  priority: PaymentRequestPriority
  file_keys: string[]
  currency: string
  total_amount: string
  paid_amount: string
  remaining_amount: string
  items: PaymentRequestItem[]
  created_at: string
}

export interface PaymentRequestItemIn {
  product_id: number
  amount: number
}

export interface PaymentRequestCreate {
  requisites?: string
  details?: string
  priority?: PaymentRequestPriority
  file_keys?: string[]
  items: PaymentRequestItemIn[]
  group_ids?: number[] | null
}

export async function fetchPaymentRequests(orderId: number): Promise<PaymentRequest[]> {
  const res = await fetch(`/api/orders/${orderId}/payment-requests/`, { credentials: 'include' })
  if (!res.ok) throw new Error('Failed to fetch payment requests')
  return res.json()
}

export async function createPaymentRequest(orderId: number, data: PaymentRequestCreate): Promise<PaymentRequest> {
  const res = await fetch(`/api/orders/${orderId}/payment-requests/`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    credentials: 'include',
    body: JSON.stringify(data),
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error(err.detail || 'Failed to create payment request')
  }
  return res.json()
}

export async function deletePaymentRequest(orderId: number, requestId: number): Promise<void> {
  const res = await fetch(`/api/orders/${orderId}/payment-requests/${requestId}`, {
    method: 'DELETE',
    credentials: 'include',
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error(err.detail || 'Failed to delete payment request')
  }
}

export interface PaymentRequestSummary extends PaymentRequest {
  order_number: string
  client_name: string
  manager_name: string
  manager_id: number
  order_currency: string
}

export async function fetchAllPaymentRequests(params?: {
  manager_id?: number
  client_id?: number
  search?: string
  sort?: 'asc' | 'desc'
}): Promise<PaymentRequestSummary[]> {
  const url = new URL('/api/payment-requests/', window.location.origin)
  if (params?.manager_id) url.searchParams.set('manager_id', String(params.manager_id))
  if (params?.client_id) url.searchParams.set('client_id', String(params.client_id))
  if (params?.search) url.searchParams.set('search', params.search)
  if (params?.sort) url.searchParams.set('sort', params.sort)
  const res = await fetch(url.toString(), { credentials: 'include' })
  if (!res.ok) throw new Error('Failed to fetch payment requests')
  return res.json()
}
