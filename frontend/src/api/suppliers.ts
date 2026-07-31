import { extractErrorMessage, extractErrorDetail } from './errors'

const KNOWN_MESSAGES: Record<string, string> = {
  'Supplier name already exists': 'Поставщик с таким названием уже существует',
}

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
  if (!res.ok) throw new Error('Не удалось загрузить поставщиков')
  return res.json()
}

export interface SupplierUpdate {
  name?: string
  contacts?: string
  details?: string
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
    throw new Error(extractErrorMessage(err, 'Не удалось создать поставщика', KNOWN_MESSAGES))
  }
  return res.json()
}

export async function updateSupplier(id: number, data: SupplierUpdate): Promise<Supplier> {
  const res = await fetch(`/api/suppliers/${id}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    credentials: 'include',
    body: JSON.stringify(data),
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error(extractErrorMessage(err, 'Не удалось обновить поставщика', KNOWN_MESSAGES))
  }
  return res.json()
}

export async function deleteSupplier(id: number): Promise<void> {
  const res = await fetch(`/api/suppliers/${id}`, { method: 'DELETE', credentials: 'include' })
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    const productNames = extractErrorDetail<string[]>(err, 'product_names')
    if (productNames && productNames.length > 0) {
      const productCount = extractErrorDetail<number>(err, 'product_count') ?? productNames.length
      const shown = productNames.join(', ')
      const more = productCount > productNames.length ? ` и ещё ${productCount - productNames.length}` : ''
      throw new Error(`Нельзя удалить поставщика — на нём числятся товары: ${shown}${more}. Удаление возможно только когда за поставщиком не остаётся ни одного товара.`)
    }
    throw new Error(extractErrorMessage(err, 'Не удалось удалить поставщика', KNOWN_MESSAGES))
  }
}
