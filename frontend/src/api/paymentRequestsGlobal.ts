export type Priority = 'low' | 'normal' | 'urgent'

export interface PaymentRequestGlobal {
  id: number
  order_id: number
  order_number: string
  client_name: string
  manager_name: string
  manager_id: number
  order_currency: string
  created_by_id: number
  created_by_name: string
  requisites: string
  details: string
  priority: Priority
  currency: string
  total_amount: string
  paid_amount: string
  remaining_amount: string
  created_at: string
}

export interface AddPaymentBody {
  amount: string
  currency: string
  exchange_rate: string
  note?: string
}

export async function fetchAllPaymentRequests(filters: {
  manager_id?: number
  client_id?: number
} = {}): Promise<PaymentRequestGlobal[]> {
  const params = new URLSearchParams()
  if (filters.manager_id != null) params.set('manager_id', String(filters.manager_id))
  if (filters.client_id != null) params.set('client_id', String(filters.client_id))
  const res = await fetch(`/api/payment-requests/?${params.toString()}`, { credentials: 'include' })
  if (!res.ok) throw new Error('Failed to fetch payment requests')
  return res.json()
}

export async function addPaymentGlobal(requestId: number, body: AddPaymentBody): Promise<void> {
  const res = await fetch(`/api/payment-requests/${requestId}/payments`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    credentials: 'include',
    body: JSON.stringify(body),
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error((err as { detail?: string }).detail || 'Failed to add payment')
  }
}
