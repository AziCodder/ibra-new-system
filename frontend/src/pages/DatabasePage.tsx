import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { fetchClients, createClient, type ClientCreate } from '../api/clients'
import { fetchSuppliers, createSupplier, type SupplierCreate } from '../api/suppliers'
import { fetchUsers, createUser, type UserCreate } from '../api/users'
import { useAuth } from '../contexts/AuthContext'
import ErrorState from '../components/ErrorState'
import { SkeletonTableRows } from '../components/Skeleton'

type Tab = 'users' | 'clients' | 'suppliers'

const TABS: { key: Tab; label: string }[] = [
  { key: 'users', label: 'Пользователи' },
  { key: 'clients', label: 'Клиенты' },
  { key: 'suppliers', label: 'Поставщики' },
]

function TabBar({ active, onChange }: { active: Tab; onChange: (t: Tab) => void }) {
  return (
    <div className="flex gap-1 mb-6 p-1 rounded-lg" style={{ background: 'var(--color-surface-2)' }}>
      {TABS.map((t) => (
        <button
          key={t.key}
          onClick={() => onChange(t.key)}
          className="px-4 py-2 text-sm rounded-md transition-colors cursor-pointer"
          style={{
            background: active === t.key ? 'var(--color-surface)' : 'transparent',
            color: active === t.key ? 'var(--color-text)' : 'var(--color-muted)',
            fontWeight: active === t.key ? 600 : 400,
          }}
        >
          {t.label}
        </button>
      ))}
    </div>
  )
}

function UsersTab() {
  const queryClient = useQueryClient()
  const [showForm, setShowForm] = useState(false)
  const [form, setForm] = useState<UserCreate>({ login: '', password: '', role: 'manager', full_name: '' })
  const { data: users, isLoading, isError, refetch } = useQuery({ queryKey: ['users'], queryFn: fetchUsers })
  const mutation = useMutation({
    mutationFn: () => createUser(form),
    onSuccess: () => { queryClient.invalidateQueries({ queryKey: ['users'] }); setShowForm(false); setForm({ login: '', password: '', role: 'manager', full_name: '' }) },
  })

  return (
    <>
      <div className="flex justify-end mb-4">
        <button onClick={() => setShowForm(!showForm)} className="rounded-lg px-4 py-2 text-sm font-medium cursor-pointer" style={{ background: 'var(--color-primary)', color: '#fff' }}>+ Добавить</button>
      </div>
      {showForm && (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3 mb-4">
          <input placeholder="Логин" maxLength={64} value={form.login} onChange={(e) => setForm({ ...form, login: e.target.value })} className="rounded-lg px-3 py-2 text-sm outline-none" style={{ background: 'var(--color-surface-2)', border: '1px solid var(--color-border)', color: 'var(--color-text)' }} />
          <input placeholder="Пароль" type="password" value={form.password} onChange={(e) => setForm({ ...form, password: e.target.value })} className="rounded-lg px-3 py-2 text-sm outline-none" style={{ background: 'var(--color-surface-2)', border: '1px solid var(--color-border)', color: 'var(--color-text)' }} />
          <input placeholder="ФИО" maxLength={255} value={form.full_name} onChange={(e) => setForm({ ...form, full_name: e.target.value })} className="rounded-lg px-3 py-2 text-sm outline-none" style={{ background: 'var(--color-surface-2)', border: '1px solid var(--color-border)', color: 'var(--color-text)' }} />
          <button onClick={() => mutation.mutate()} disabled={mutation.isPending || !form.login || !form.password} className="rounded-lg px-4 py-2 text-sm font-medium cursor-pointer disabled:opacity-50" style={{ background: 'var(--color-success)', color: '#fff' }}>Создать</button>
        </div>
      )}
      {isLoading ? <SkeletonTableRows rows={5} /> : isError ? (
        <ErrorState message="Не удалось загрузить пользователей" onRetry={() => refetch()} />
      ) : (
        <DataTable
          columns={['Логин', 'ФИО', 'Роль', 'Статус']}
          rows={users?.map((u) => [u.login, u.full_name || '—', u.role, u.is_active ? 'Активен' : 'Отключён']) ?? []}
        />
      )}
    </>
  )
}

function ClientsTab() {
  const queryClient = useQueryClient()
  const [showForm, setShowForm] = useState(false)
  const [form, setForm] = useState<ClientCreate>({ code: '', full_name: '' })
  const { data: clients, isLoading, isError, refetch } = useQuery({ queryKey: ['clients'], queryFn: fetchClients })
  const mutation = useMutation({
    mutationFn: () => createClient(form),
    onSuccess: () => { queryClient.invalidateQueries({ queryKey: ['clients'] }); setShowForm(false); setForm({ code: '', full_name: '' }) },
  })

  return (
    <>
      <div className="flex justify-end mb-4">
        <button onClick={() => setShowForm(!showForm)} className="rounded-lg px-4 py-2 text-sm font-medium cursor-pointer" style={{ background: 'var(--color-primary)', color: '#fff' }}>+ Добавить</button>
      </div>
      {showForm && (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3 mb-4">
          <input placeholder="Код (M33)" maxLength={20} value={form.code} onChange={(e) => setForm({ ...form, code: e.target.value })} className="rounded-lg px-3 py-2 text-sm outline-none" style={{ background: 'var(--color-surface-2)', border: '1px solid var(--color-border)', color: 'var(--color-text)' }} />
          <input placeholder="ФИО" maxLength={255} value={form.full_name} onChange={(e) => setForm({ ...form, full_name: e.target.value })} className="rounded-lg px-3 py-2 text-sm outline-none" style={{ background: 'var(--color-surface-2)', border: '1px solid var(--color-border)', color: 'var(--color-text)' }} />
          <input placeholder="Описание" value={form.description ?? ''} onChange={(e) => setForm({ ...form, description: e.target.value })} className="rounded-lg px-3 py-2 text-sm outline-none" style={{ background: 'var(--color-surface-2)', border: '1px solid var(--color-border)', color: 'var(--color-text)' }} />
          <button onClick={() => mutation.mutate()} disabled={mutation.isPending || !form.code || !form.full_name} className="rounded-lg px-4 py-2 text-sm font-medium cursor-pointer disabled:opacity-50" style={{ background: 'var(--color-success)', color: '#fff' }}>Создать</button>
        </div>
      )}
      {isLoading ? <SkeletonTableRows rows={5} /> : isError ? (
        <ErrorState message="Не удалось загрузить клиентов" onRetry={() => refetch()} />
      ) : (
        <DataTable
          columns={['Код', 'ФИО', 'Описание', 'TG группа']}
          rows={clients?.map((c) => [c.code, c.full_name, c.description || '—', c.telegram_group_link || '—']) ?? []}
        />
      )}
    </>
  )
}

function SuppliersTab() {
  const queryClient = useQueryClient()
  const [showForm, setShowForm] = useState(false)
  const [form, setForm] = useState<SupplierCreate>({ name: '' })
  const { data: suppliers, isLoading, isError, refetch } = useQuery({ queryKey: ['suppliers'], queryFn: fetchSuppliers })
  const mutation = useMutation({
    mutationFn: () => createSupplier(form),
    onSuccess: () => { queryClient.invalidateQueries({ queryKey: ['suppliers'] }); setShowForm(false); setForm({ name: '' }) },
  })

  return (
    <>
      <div className="flex justify-end mb-4">
        <button onClick={() => setShowForm(!showForm)} className="rounded-lg px-4 py-2 text-sm font-medium cursor-pointer" style={{ background: 'var(--color-primary)', color: '#fff' }}>+ Добавить</button>
      </div>
      {showForm && (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3 mb-4">
          <input placeholder="Название" maxLength={255} value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} className="rounded-lg px-3 py-2 text-sm outline-none" style={{ background: 'var(--color-surface-2)', border: '1px solid var(--color-border)', color: 'var(--color-text)' }} />
          <input placeholder="Контакты" value={form.contacts ?? ''} onChange={(e) => setForm({ ...form, contacts: e.target.value })} className="rounded-lg px-3 py-2 text-sm outline-none" style={{ background: 'var(--color-surface-2)', border: '1px solid var(--color-border)', color: 'var(--color-text)' }} />
          <input placeholder="Детали" value={form.details ?? ''} onChange={(e) => setForm({ ...form, details: e.target.value })} className="rounded-lg px-3 py-2 text-sm outline-none" style={{ background: 'var(--color-surface-2)', border: '1px solid var(--color-border)', color: 'var(--color-text)' }} />
          <button onClick={() => mutation.mutate()} disabled={mutation.isPending || !form.name} className="rounded-lg px-4 py-2 text-sm font-medium cursor-pointer disabled:opacity-50" style={{ background: 'var(--color-success)', color: '#fff' }}>Создать</button>
        </div>
      )}
      {isLoading ? <SkeletonTableRows rows={5} /> : isError ? (
        <ErrorState message="Не удалось загрузить поставщиков" onRetry={() => refetch()} />
      ) : (
        <DataTable
          columns={['Название', 'Контакты', 'Детали']}
          rows={suppliers?.map((s) => [s.name, s.contacts || '—', s.details || '—']) ?? []}
        />
      )}
    </>
  )
}

function DataTable({ columns, rows }: { columns: string[]; rows: string[][] }) {
  return (
    <div className="rounded-xl overflow-x-auto" style={{ background: 'var(--color-surface)', border: '1px solid var(--color-border)' }}>
      <table className="w-full">
        <thead>
          <tr style={{ borderBottom: '1px solid var(--color-border)' }}>
            {columns.map((col) => (
              <th key={col} className="px-4 py-3 text-left text-xs font-medium" style={{ color: 'var(--color-muted)' }}>{col}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row, i) => (
            <tr key={i} style={{ borderBottom: '1px solid var(--color-border)' }}>
              {row.map((cell, j) => (
                <td key={j} className="px-4 py-3 text-sm" style={{ color: 'var(--color-text)' }}>{cell}</td>
              ))}
            </tr>
          ))}
          {rows.length === 0 && (
            <tr>
              <td colSpan={columns.length} className="px-4 py-8 text-center text-sm" style={{ color: 'var(--color-muted)' }}>
                Нет данных
              </td>
            </tr>
          )}
        </tbody>
      </table>
    </div>
  )
}

export default function DatabasePage() {
  const { user } = useAuth()
  const [tab, setTab] = useState<Tab>('clients')

  if (user?.role !== 'admin') {
    return (
      <div className="p-4 sm:p-6">
        <p style={{ color: 'var(--color-danger)' }}>Доступ только для администраторов</p>
      </div>
    )
  }

  return (
    <div className="p-4 sm:p-6">
      <h2 className="text-lg font-semibold mb-4" style={{ color: 'var(--color-text)' }}>
        База данных
      </h2>
      <TabBar active={tab} onChange={setTab} />
      {tab === 'users' && <UsersTab />}
      {tab === 'clients' && <ClientsTab />}
      {tab === 'suppliers' && <SuppliersTab />}
    </div>
  )
}
