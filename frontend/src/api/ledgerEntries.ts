export type LedgerEntryType = 'income' | 'expense'

export interface LedgerEntry {
  id: number
  order_id: number
  author_id: number
  author_name: string
  type: LedgerEntryType
  amount: string
  currency: string
  exchange_rate: string
  details: string
  created_at: string
}

export interface LedgerEntryCreate {
  type: LedgerEntryType
  amount: number
  currency: string
  exchange_rate: number
  details?: string
}

async function handle<T>(res: Response, fallback: string): Promise<T> {
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error(err.detail || fallback)
  }
  return res.json()
}

export async function fetchLedgerEntries(orderId: number): Promise<LedgerEntry[]> {
  const res = await fetch(`/api/orders/${orderId}/ledger-entries/`, { credentials: 'include' })
  return handle(res, 'Failed to fetch ledger entries')
}

export async function createLedgerEntry(orderId: number, data: LedgerEntryCreate): Promise<LedgerEntry> {
  const res = await fetch(`/api/orders/${orderId}/ledger-entries/`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    credentials: 'include',
    body: JSON.stringify(data),
  })
  return handle(res, 'Failed to create ledger entry')
}

export async function deleteLedgerEntry(orderId: number, entryId: number): Promise<void> {
  const res = await fetch(`/api/orders/${orderId}/ledger-entries/${entryId}`, {
    method: 'DELETE',
    credentials: 'include',
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error(err.detail || 'Failed to delete ledger entry')
  }
}
