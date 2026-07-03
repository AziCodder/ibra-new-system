import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { fetchUsers, createUser, updateUser, type UserCreate } from '../api/users'
import type { User } from '../api/auth'

const ROLE_LABELS: Record<string, string> = {
  admin: 'Админ',
  manager: 'Менеджер',
  observer: 'Наблюдатель',
}

function CreateUserForm({ onClose }: { onClose: () => void }) {
  const queryClient = useQueryClient()
  const [form, setForm] = useState<UserCreate>({
    login: '',
    password: '',
    role: 'manager',
    full_name: '',
  })
  const [error, setError] = useState('')

  const mutation = useMutation({
    mutationFn: () => createUser(form),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['users'] })
      onClose()
    },
    onError: (err: Error) => setError(err.message),
  })

  return (
    <div
      className="rounded-xl p-6 mb-6"
      style={{ background: 'var(--color-surface-2)', border: '1px solid var(--color-border)' }}
    >
      <h3 className="text-sm font-semibold mb-4" style={{ color: 'var(--color-text)' }}>
        Новый пользователь
      </h3>
      {error && (
        <div className="rounded-lg px-3 py-2 mb-3 text-sm" style={{ background: 'var(--color-danger-bg)', color: 'var(--color-danger)' }}>
          {error}
        </div>
      )}
      <div className="grid grid-cols-2 gap-3 mb-4">
        <input
          placeholder="Логин"
          value={form.login}
          onChange={(e) => setForm({ ...form, login: e.target.value })}
          className="rounded-lg px-3 py-2 text-sm outline-none"
          style={{ background: 'var(--color-surface)', border: '1px solid var(--color-border)', color: 'var(--color-text)' }}
        />
        <input
          placeholder="Пароль"
          type="password"
          value={form.password}
          onChange={(e) => setForm({ ...form, password: e.target.value })}
          className="rounded-lg px-3 py-2 text-sm outline-none"
          style={{ background: 'var(--color-surface)', border: '1px solid var(--color-border)', color: 'var(--color-text)' }}
        />
        <input
          placeholder="ФИО"
          value={form.full_name}
          onChange={(e) => setForm({ ...form, full_name: e.target.value })}
          className="rounded-lg px-3 py-2 text-sm outline-none"
          style={{ background: 'var(--color-surface)', border: '1px solid var(--color-border)', color: 'var(--color-text)' }}
        />
        <select
          value={form.role}
          onChange={(e) => setForm({ ...form, role: e.target.value as UserCreate['role'] })}
          className="rounded-lg px-3 py-2 text-sm outline-none"
          style={{ background: 'var(--color-surface)', border: '1px solid var(--color-border)', color: 'var(--color-text)' }}
        >
          <option value="manager">Менеджер</option>
          <option value="observer">Наблюдатель</option>
          <option value="admin">Админ</option>
        </select>
      </div>
      <div className="flex gap-2">
        <button
          onClick={() => mutation.mutate()}
          disabled={mutation.isPending || !form.login || !form.password}
          className="rounded-lg px-4 py-2 text-sm font-medium cursor-pointer disabled:opacity-50"
          style={{ background: 'var(--color-primary)', color: '#fff' }}
        >
          Создать
        </button>
        <button
          onClick={onClose}
          className="rounded-lg px-4 py-2 text-sm cursor-pointer"
          style={{ background: 'var(--color-surface-3)', color: 'var(--color-text)' }}
        >
          Отмена
        </button>
      </div>
    </div>
  )
}

function UserRow({ user }: { user: User }) {
  const queryClient = useQueryClient()

  const toggleActive = useMutation({
    mutationFn: () => updateUser(user.id, { is_active: !user.is_active }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['users'] }),
  })

  return (
    <tr style={{ borderBottom: '1px solid var(--color-border)' }}>
      <td className="px-4 py-3 text-sm" style={{ color: 'var(--color-text)' }}>{user.login}</td>
      <td className="px-4 py-3 text-sm" style={{ color: 'var(--color-text)' }}>{user.full_name || '—'}</td>
      <td className="px-4 py-3 text-sm" style={{ color: 'var(--color-muted)' }}>{ROLE_LABELS[user.role]}</td>
      <td className="px-4 py-3 text-sm">
        <span
          className="inline-block rounded-full px-2.5 py-0.5 text-xs font-medium"
          style={{
            background: user.is_active ? 'var(--color-success-bg)' : 'var(--color-danger-bg)',
            color: user.is_active ? 'var(--color-success)' : 'var(--color-danger)',
          }}
        >
          {user.is_active ? 'Активен' : 'Отключён'}
        </span>
      </td>
      <td className="px-4 py-3 text-sm">
        <button
          onClick={() => toggleActive.mutate()}
          className="text-xs cursor-pointer rounded px-2 py-1"
          style={{ color: 'var(--color-muted)', background: 'var(--color-surface-3)' }}
        >
          {user.is_active ? 'Отключить' : 'Включить'}
        </button>
      </td>
    </tr>
  )
}

export default function UsersPage() {
  const [showCreate, setShowCreate] = useState(false)
  const { data: users, isLoading } = useQuery({
    queryKey: ['users'],
    queryFn: fetchUsers,
  })

  return (
    <div className="p-6">
      <div className="flex items-center justify-between mb-6">
        <h2 className="text-lg font-semibold" style={{ color: 'var(--color-text)' }}>
          Пользователи
        </h2>
        <button
          onClick={() => setShowCreate(true)}
          className="rounded-lg px-4 py-2 text-sm font-medium cursor-pointer"
          style={{ background: 'var(--color-primary)', color: '#fff' }}
        >
          + Добавить
        </button>
      </div>

      {showCreate && <CreateUserForm onClose={() => setShowCreate(false)} />}

      {isLoading ? (
        <p style={{ color: 'var(--color-muted)' }}>Загрузка...</p>
      ) : (
        <div
          className="rounded-xl overflow-x-auto"
          style={{ background: 'var(--color-surface)', border: '1px solid var(--color-border)' }}
        >
          <table className="w-full">
            <thead>
              <tr style={{ borderBottom: '1px solid var(--color-border)' }}>
                <th className="px-4 py-3 text-left text-xs font-medium" style={{ color: 'var(--color-muted)' }}>Логин</th>
                <th className="px-4 py-3 text-left text-xs font-medium" style={{ color: 'var(--color-muted)' }}>ФИО</th>
                <th className="px-4 py-3 text-left text-xs font-medium" style={{ color: 'var(--color-muted)' }}>Роль</th>
                <th className="px-4 py-3 text-left text-xs font-medium" style={{ color: 'var(--color-muted)' }}>Статус</th>
                <th className="px-4 py-3 text-left text-xs font-medium" style={{ color: 'var(--color-muted)' }}></th>
              </tr>
            </thead>
            <tbody>
              {users?.map((u) => <UserRow key={u.id} user={u} />)}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}
