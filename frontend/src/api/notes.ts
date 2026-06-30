export interface Note {
  id: number
  order_id: number
  author_id: number
  author_name: string
  text: string
  created_at: string
}

export async function fetchNotes(orderId: number): Promise<Note[]> {
  const res = await fetch(`/api/orders/${orderId}/notes/`, { credentials: 'include' })
  if (!res.ok) throw new Error('Failed to fetch notes')
  return res.json()
}

export async function createNote(orderId: number, text: string): Promise<Note> {
  const res = await fetch(`/api/orders/${orderId}/notes/`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    credentials: 'include',
    body: JSON.stringify({ text }),
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error(err.detail || 'Failed to create note')
  }
  return res.json()
}
