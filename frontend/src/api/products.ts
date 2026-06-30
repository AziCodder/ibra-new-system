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
  photo_key: string | null
  created_at: string
}

export async function fetchProducts(orderId: number): Promise<Product[]> {
  const res = await fetch(`/api/orders/${orderId}/products/`, { credentials: 'include' })
  if (!res.ok) throw new Error('Failed to fetch products')
  return res.json()
}
