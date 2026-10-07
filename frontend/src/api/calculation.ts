import { extractErrorMessage } from './errors'

/** Mirrors backend/app/schemas/order_calculation.py. */
export const MIN_PARTICIPANTS = 2
export const MAX_PARTICIPANTS = 5

export interface CalculationParticipant {
  user_id: number
  full_name: string
  percent: string
  amount: string
}

export interface Calculation {
  is_calculated: boolean
  calculated_at: string | null
  /** Fixed once calculated; before that the current profit, or null while it isn't final. */
  profit: string | null
  currency: string
  is_ready: boolean
  participants: CalculationParticipant[]
}

export interface CalculationShare {
  user_id: number
  /** Sent as a string so 33.33 reaches the server's Decimal exactly. */
  percent: string
}

export async function fetchCalculation(orderId: number): Promise<Calculation> {
  const res = await fetch(`/api/orders/${orderId}/calculation/`, { credentials: 'include' })
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error(extractErrorMessage(err, 'Не удалось загрузить расчёт'))
  }
  return res.json()
}

export async function saveCalculation(orderId: number, participants: CalculationShare[]): Promise<Calculation> {
  const res = await fetch(`/api/orders/${orderId}/calculation/`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    credentials: 'include',
    body: JSON.stringify({ participants }),
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error(extractErrorMessage(err, 'Не удалось сохранить расчёт'))
  }
  return res.json()
}

export async function cancelCalculation(orderId: number): Promise<void> {
  const res = await fetch(`/api/orders/${orderId}/calculation/`, { method: 'DELETE', credentials: 'include' })
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error(extractErrorMessage(err, 'Не удалось отменить расчёт'))
  }
}
