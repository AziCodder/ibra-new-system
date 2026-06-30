export interface ProfitBreakdown {
  income: string
  purchases: string
  logistics: string
  other_expenses: string
  profit: string
  currency: string
  is_ready: boolean
  profit_pct: string | null
  processing_days: number | null
}

export async function fetchOrderProfit(orderId: number): Promise<ProfitBreakdown> {
  const res = await fetch(`/api/orders/${orderId}/profit`, { credentials: 'include' })
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error((err as { detail?: string }).detail || 'Failed to fetch profit')
  }
  return res.json()
}
