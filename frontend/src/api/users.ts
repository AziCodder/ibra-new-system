import type { User } from './auth'

export interface UserCreate {
  login: string
  password: string
  role: 'admin' | 'manager' | 'observer'
  full_name: string
}

export interface UserUpdate {
  full_name?: string
  role?: 'admin' | 'manager' | 'observer'
  is_active?: boolean
  password?: string
}

export async function fetchUsers(): Promise<User[]> {
  const res = await fetch('/api/users/', { credentials: 'include' })
  if (!res.ok) throw new Error('Failed to fetch users')
  return res.json()
}

export async function createUser(data: UserCreate): Promise<User> {
  const res = await fetch('/api/users/', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    credentials: 'include',
    body: JSON.stringify(data),
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error(err.detail || 'Failed to create user')
  }
  return res.json()
}

export async function updateUser(id: number, data: UserUpdate): Promise<User> {
  const res = await fetch(`/api/users/${id}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    credentials: 'include',
    body: JSON.stringify(data),
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error(err.detail || 'Failed to update user')
  }
  return res.json()
}
