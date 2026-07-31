import { extractErrorMessage } from './errors'

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
  paid_at: string
  created_at: string
}

export interface PaymentCreate {
  amount: number
  currency: string
  exchange_rate: number
  file_key?: string | null
  note?: string
  paid_at?: string
}

export interface PaymentUpdate {
  amount: number
  currency: string
  exchange_rate: number
  file_key: string | null
  note: string
  paid_at: string
}

export async function fetchPayments(orderId: number, requestId: number): Promise<Payment[]> {
  const res = await fetch(`/api/orders/${orderId}/payment-requests/${requestId}/payments/`, { credentials: 'include' })
  if (!res.ok) throw new Error('Не удалось загрузить оплаты')
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
    throw new Error(extractErrorMessage(err, 'Не удалось внести оплату'))
  }
  return res.json()
}

export async function updatePayment(orderId: number, requestId: number, paymentId: number, data: PaymentUpdate): Promise<Payment> {
  const res = await fetch(`/api/orders/${orderId}/payment-requests/${requestId}/payments/${paymentId}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    credentials: 'include',
    body: JSON.stringify(data),
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error(extractErrorMessage(err, 'Не удалось обновить оплату'))
  }
  return res.json()
}

export async function deletePayment(orderId: number, requestId: number, paymentId: number): Promise<void> {
  const res = await fetch(`/api/orders/${orderId}/payment-requests/${requestId}/payments/${paymentId}`, {
    method: 'DELETE',
    credentials: 'include',
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error(extractErrorMessage(err, 'Не удалось удалить оплату'))
  }
}
