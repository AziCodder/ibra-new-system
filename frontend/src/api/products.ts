import type { LogisticsStatus } from './logistics'

export interface ProductShipment {
  id: number
  tracking: string | null
  quantity: string
  status: LogisticsStatus
}

export interface Product {
  id: number
  order_id: number
  supplier_id: number
  supplier_name: string
  name: string
  details: string
  quantity: string
  price: string
  currency: string
  /** Order-currency units per 1 unit of `currency`; "1" when they are the same. */
  exchange_rate: string
  photo_key: string | null
  created_at: string
  requested_amount: string | null
  paid_amount: string | null
  shipped_quantity: string
  accepted_quantity: string
  shipments: ProductShipment[]
}

export interface ProductCreate {
  supplier_id: number
  name: string
  details?: string
  quantity: number
  price: number
  /** Defaults to the order's currency server-side when omitted. */
  currency?: string
  /** Required when `currency` differs from the order's; must be 1 otherwise. */
  exchange_rate?: number
  photo_key?: string | null
}

export async function fetchProducts(orderId: number): Promise<Product[]> {
  const res = await fetch(`/api/orders/${orderId}/products/`, { credentials: 'include' })
  if (!res.ok) throw new Error('Failed to fetch products')
  return res.json()
}

export async function createProduct(orderId: number, data: ProductCreate): Promise<Product> {
  const res = await fetch(`/api/orders/${orderId}/products/`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    credentials: 'include',
    body: JSON.stringify(data),
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error(err.detail || 'Failed to create product')
  }
  return res.json()
}

export type ProductUpdate = Partial<ProductCreate>

export async function updateProduct(orderId: number, productId: number, data: ProductUpdate): Promise<Product> {
  const res = await fetch(`/api/orders/${orderId}/products/${productId}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    credentials: 'include',
    body: JSON.stringify(data),
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error(err.detail || 'Failed to update product')
  }
  return res.json()
}

export async function deleteProduct(orderId: number, productId: number): Promise<void> {
  const res = await fetch(`/api/orders/${orderId}/products/${productId}`, {
    method: 'DELETE',
    credentials: 'include',
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error(err.detail || 'Failed to delete product')
  }
}
