export interface Payment {
  id: number
  payment_request_id: number
  author_id: number
  author_name: string
  amount: string
  currency: string
  exchange_rate: string
  file_key: string | null
  note: string
  created_at: string
}

export interface PaymentCreate {
  amount: number
  currency: string
  exchange_rate: number
  file_key?: string | null
  note?: string
}

export async function fetchPayments(orderId: number, requestId: number): Promise<Payment[]> {
  const res = await fetch(`/api/orders/${orderId}/payment-requests/${requestId}/payments/`, { credentials: 'include' })
  if (!res.ok) throw new Error('Failed to fetch payments')
  return res.json()
}

export async function createPayment(orderId: number, requestId: number, data: PaymentCreate): Promise<Payment> {
  const res = await fetch(`/api/orders/${orderId}/payment-requests/${requestId}/payments/`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    credentials: 'include',
    body: JSON.stringify(data),
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error(err.detail || 'Failed to create payment')
  }
  return res.json()
}
