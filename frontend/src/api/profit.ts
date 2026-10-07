export interface ProfitBlocker {
  kind: 'no_products' | 'in_transit' | 'not_received' | 'not_paid'
  product_name: string | null
  /** in_transit: shipments on the way; not_received: quantity not accepted; not_paid: cost not covered. */
  amount: string | null
  currency: string | null
}

export interface ProfitBreakdown {
  income: string
  purchases: string
  logistics: string
  other_expenses: string
  profit: string
  currency: string
  is_ready: boolean
  /** Why the totals aren't final yet — empty once is_ready. */
  blockers: ProfitBlocker[]
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
