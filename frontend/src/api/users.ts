import type { User } from './auth'
import { extractErrorMessage as extractErrorMessageBase } from './errors'

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

const KNOWN_MESSAGES: Record<string, string> = {
  'Login already exists': 'Такой логин уже занят — выберите другой',
  'Cannot delete your own account': 'Нельзя удалить собственную учётную запись',
}

interface PydanticErrorItem { type?: string; loc?: (string | number)[]; msg?: string }

function extractErrorMessage(payload: unknown, fallback: string): string {
  const detail = (payload as { detail?: unknown } | null)?.detail
  if (Array.isArray(detail)) {
    const passwordTooShort = (detail as PydanticErrorItem[]).find((d) => d.type === 'string_too_short' && d.loc?.includes('password'))
    if (passwordTooShort) return 'Пароль должен быть не короче 8 символов'
  }
  return extractErrorMessageBase(payload, fallback, KNOWN_MESSAGES)
}

export async function fetchUsers(): Promise<User[]> {
  const res = await fetch('/api/users/', { credentials: 'include' })
  if (!res.ok) throw new Error('Не удалось загрузить пользователей')
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
    throw new Error(extractErrorMessage(err, 'Не удалось создать пользователя'))
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
    throw new Error(extractErrorMessage(err, 'Не удалось обновить пользователя'))
  }
  return res.json()
}

export async function deleteUser(id: number): Promise<void> {
  const res = await fetch(`/api/users/${id}`, { method: 'DELETE', credentials: 'include' })
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error(extractErrorMessage(err, 'Не удалось удалить пользователя'))
  }
}
