export interface Supplier {
  id: number
  name: string
  contacts: string
  details: string
}

export interface SupplierCreate {
  name: string
  contacts?: string
  details?: string
}

export async function fetchSuppliers(): Promise<Supplier[]> {
  const res = await fetch('/api/suppliers/', { credentials: 'include' })
  if (!res.ok) throw new Error('Failed to fetch suppliers')
  return res.json()
}

export async function createSupplier(data: SupplierCreate): Promise<Supplier> {
  const res = await fetch('/api/suppliers/', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    credentials: 'include',
    body: JSON.stringify(data),
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error(err.detail || 'Failed to create supplier')
  }
  return res.json()
}
