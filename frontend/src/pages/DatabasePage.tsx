import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { fetchClients, createClient, updateClient, deleteClient, generateTelegramLink, type ClientCreate, type ClientUpdate } from '../api/clients'
import { fetchSuppliers, createSupplier, updateSupplier, deleteSupplier, type SupplierCreate, type SupplierUpdate } from '../api/suppliers'
import { fetchUsers, createUser, updateUser, deleteUser, type UserCreate, type UserUpdate } from '../api/users'
import { useAuth } from '../contexts/AuthContext'
import ErrorState from '../components/ErrorState'
import { SkeletonTableRows } from '../components/Skeleton'
import { Plus, Link, X, Copy, Check, Pencil, Trash2, Save } from 'lucide-react'
import Tag, { type TagColor } from '../components/Tag'
import PageHeader from '../components/PageHeader'
import type { User } from '../api/auth'

type Tab = 'users' | 'clients' | 'suppliers'

const TABS: { key: Tab; label: string }[] = [
  { key: 'users', label: 'Пользователи' },
  { key: 'clients', label: 'Клиенты' },
  { key: 'suppliers', label: 'Поставщики' },
]

const INPUT_STYLE = {
  background: 'var(--color-surface)',
  border: '1px solid var(--color-border)',
  color: 'var(--color-text)',
}

function TabBar({ active, onChange }: { active: Tab; onChange: (t: Tab) => void }) {
  return (
    <div className="flex gap-6 mb-6" style={{ borderBottom: '1px solid var(--color-border)' }}>
      {TABS.map((t) => (
        <button
          key={t.key}
          onClick={() => onChange(t.key)}
          className="px-1 pb-3 text-sm transition-colors cursor-pointer relative"
          style={{
            color: active === t.key ? 'var(--color-primary)' : 'var(--color-muted)',
            fontWeight: active === t.key ? 600 : 400,
          }}
        >
          {t.label}
          {active === t.key && (
            <span
              className="absolute bottom-0 left-0 right-0 h-0.5 rounded-full"
              style={{ background: 'var(--color-primary)' }}
            />
          )}
        </button>
      ))}
    </div>
  )
}

function IconBtn({ onClick, title, danger, disabled, children }: { onClick: () => void; title: string; danger?: boolean; disabled?: boolean; children: React.ReactNode }) {
  return (
    <button
      onClick={onClick}
      title={title}
      disabled={disabled}
      className="rounded-md p-1.5 cursor-pointer disabled:opacity-40 transition-colors"
      style={{
        background: 'transparent',
        border: '1px solid var(--color-border)',
        color: danger ? 'var(--color-danger)' : 'var(--color-muted)',
      }}
    >
      {children}
    </button>
  )
}

// ── Users ──────────────────────────────────────────────────────────────────

function UsersTab() {
  const { user: me } = useAuth()
  const queryClient = useQueryClient()
  const [showForm, setShowForm] = useState(false)
  const [form, setForm] = useState<UserCreate>({ login: '', password: '', role: 'manager', full_name: '' })
  const [editId, setEditId] = useState<number | null>(null)
  const [editForm, setEditForm] = useState<UserUpdate & { password: string }>({ full_name: '', role: 'manager', is_active: true, password: '' })

  const { data: users, isLoading, isError, refetch } = useQuery({ queryKey: ['users'], queryFn: fetchUsers })

  const createMut = useMutation({
    mutationFn: () => createUser(form),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['users'] })
      setShowForm(false)
      setForm({ login: '', password: '', role: 'manager', full_name: '' })
    },
  })

  const updateMut = useMutation({
    mutationFn: ({ id, data }: { id: number; data: UserUpdate }) => updateUser(id, data),
    onSuccess: () => { queryClient.invalidateQueries({ queryKey: ['users'] }); setEditId(null) },
  })

  const deleteMut = useMutation({
    mutationFn: (id: number) => deleteUser(id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['users'] }),
  })

  function startEdit(u: User) {
    setEditId(u.id)
    setEditForm({ full_name: u.full_name, role: u.role as UserUpdate['role'], is_active: u.is_active, password: '' })
  }

  function saveEdit(id: number) {
    const data: UserUpdate = {
      full_name: editForm.full_name,
      role: editForm.role,
      is_active: editForm.is_active,
    }
    if (editForm.password) data.password = editForm.password
    updateMut.mutate({ id, data })
  }

  function confirmDelete(u: User) {
    if (!window.confirm(`Удалить пользователя «${u.login}»? Это действие нельзя отменить.`)) return
    deleteMut.mutate(u.id)
  }

  return (
    <>
      <div className="flex justify-end mb-4">
        <button
          onClick={() => setShowForm(!showForm)}
          className="rounded-lg px-4 py-2 text-sm font-medium cursor-pointer"
          style={{ background: 'var(--color-primary)', color: '#fff' }}
        >
          <Plus size={16} className="inline -mt-0.5" /> Добавить
        </button>
      </div>

      {showForm && (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-3 mb-4">
          <input placeholder="Логин" maxLength={64} value={form.login} onChange={(e) => setForm({ ...form, login: e.target.value })} className="rounded-lg px-3 py-2 text-sm outline-none" style={INPUT_STYLE} />
          <input placeholder="Пароль" type="password" value={form.password} onChange={(e) => setForm({ ...form, password: e.target.value })} className="rounded-lg px-3 py-2 text-sm outline-none" style={INPUT_STYLE} />
          <input placeholder="ФИО" maxLength={255} value={form.full_name} onChange={(e) => setForm({ ...form, full_name: e.target.value })} className="rounded-lg px-3 py-2 text-sm outline-none" style={INPUT_STYLE} />
          <select value={form.role} onChange={(e) => setForm({ ...form, role: e.target.value as UserCreate['role'] })} className="rounded-lg px-3 py-2 text-sm outline-none" style={INPUT_STYLE}>
            <option value="manager">Менеджер</option>
            <option value="admin">Администратор</option>
            <option value="observer">Наблюдатель</option>
          </select>
          <button onClick={() => createMut.mutate()} disabled={createMut.isPending || !form.login || !form.password} className="rounded-lg px-4 py-2 text-sm font-medium cursor-pointer disabled:opacity-50" style={{ background: 'var(--color-success)', color: '#fff' }}>Создать</button>
        </div>
      )}

      {isLoading ? <SkeletonTableRows rows={5} /> : isError ? (
        <ErrorState message="Не удалось загрузить пользователей" onRetry={() => refetch()} />
      ) : (
        <div className="rounded-[8px] overflow-x-auto" style={{ background: 'var(--color-surface)', border: '1px solid var(--color-card-border)' }}>
          <table className="rtable w-full">
            <thead>
              <tr style={{ borderBottom: '1px solid var(--color-border)' }}>
                {['ФИО', 'Логин', 'Роль', 'Статус', 'Новый пароль', ''].map((col) => (
                  <th key={col} className="px-4 py-3 text-left text-xs font-semibold" style={{ color: 'var(--color-muted)' }}>{col}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {(users ?? []).map((u) => {
                const isEditing = editId === u.id
                const isSelf = me?.id === u.id
                return (
                  <tr key={u.id} style={{ borderBottom: '1px solid var(--color-border)', background: isEditing ? 'var(--color-surface-hover, var(--color-bg))' : undefined }}>
                    <td className="px-4 py-2.5 text-sm" data-label="ФИО" style={{ color: 'var(--color-text)' }}>
                      {isEditing
                        ? <input value={editForm.full_name ?? ''} onChange={(e) => setEditForm({ ...editForm, full_name: e.target.value })} maxLength={255} className="rounded px-2 py-1 text-sm w-full outline-none" style={INPUT_STYLE} />
                        : u.full_name || '—'}
                    </td>
                    <td className="px-4 py-2.5 text-sm" data-label="Логин" style={{ color: 'var(--color-text)' }}>{u.login}</td>
                    <td className="px-4 py-2.5 text-sm" data-label="Роль">
                      {isEditing
                        ? <select value={editForm.role} onChange={(e) => setEditForm({ ...editForm, role: e.target.value as UserUpdate['role'] })} className="rounded px-2 py-1 text-sm outline-none" style={INPUT_STYLE}>
                            <option value="manager">Менеджер</option>
                            <option value="admin">Администратор</option>
                            <option value="observer">Наблюдатель</option>
                          </select>
                        : <RoleBadge role={u.role} />}
                    </td>
                    <td className="px-4 py-2.5 text-sm" data-label="Статус">
                      {isEditing
                        ? <select value={editForm.is_active ? 'true' : 'false'} onChange={(e) => setEditForm({ ...editForm, is_active: e.target.value === 'true' })} className="rounded px-2 py-1 text-sm outline-none" style={INPUT_STYLE}>
                            <option value="true">Активен</option>
                            <option value="false">Отключён</option>
                          </select>
                        : <span style={{ color: u.is_active ? 'var(--color-success)' : 'var(--color-muted)' }}>{u.is_active ? 'Активен' : 'Отключён'}</span>}
                    </td>
                    <td className="px-4 py-2.5 text-sm" data-label="Новый пароль">
                      {isEditing
                        ? <input type="password" placeholder="Оставьте пустым" value={editForm.password ?? ''} onChange={(e) => setEditForm({ ...editForm, password: e.target.value })} className="rounded px-2 py-1 text-sm w-full outline-none" style={INPUT_STYLE} />
                        : ''}
                    </td>
                    <td className="px-4 py-2.5">
                      <div className="flex gap-1.5 justify-end">
                        {isEditing ? (
                          <>
                            <IconBtn onClick={() => saveEdit(u.id)} title="Сохранить" disabled={updateMut.isPending}><Save size={14} /></IconBtn>
                            <IconBtn onClick={() => setEditId(null)} title="Отмена"><X size={14} /></IconBtn>
                          </>
                        ) : (
                          <>
                            <IconBtn onClick={() => startEdit(u)} title="Редактировать"><Pencil size={14} /></IconBtn>
                            <IconBtn onClick={() => confirmDelete(u)} title="Удалить" danger disabled={isSelf || deleteMut.isPending}><Trash2 size={14} /></IconBtn>
                          </>
                        )}
                      </div>
                    </td>
                  </tr>
                )
              })}
              {(users ?? []).length === 0 && (
                <tr><td colSpan={6} className="px-4 py-8 text-center text-sm" style={{ color: 'var(--color-muted)' }}>Нет данных</td></tr>
              )}
            </tbody>
          </table>
        </div>
      )}
    </>
  )
}

// ── Clients ────────────────────────────────────────────────────────────────

interface ClientRow {
  id: number; code: string; full_name: string; description: string; telegram_group_link: string; telegram_chat_id: string
}

function ClientsTab() {
  const queryClient = useQueryClient()
  const [showForm, setShowForm] = useState(false)
  const [form, setForm] = useState<ClientCreate>({ code: '', full_name: '' })
  const [editId, setEditId] = useState<number | null>(null)
  const [editForm, setEditForm] = useState<ClientUpdate>({})
  const [tgToken, setTgToken] = useState<string | null>(null)
  const [tgClientName, setTgClientName] = useState('')
  const [tgLoading, setTgLoading] = useState<number | null>(null)
  const [copied, setCopied] = useState(false)

  const { data: clients, isLoading, isError, refetch } = useQuery({ queryKey: ['clients'], queryFn: fetchClients })

  const createMut = useMutation({
    mutationFn: () => createClient(form),
    onSuccess: () => { queryClient.invalidateQueries({ queryKey: ['clients'] }); setShowForm(false); setForm({ code: '', full_name: '' }) },
  })

  const updateMut = useMutation({
    mutationFn: ({ id, data }: { id: number; data: ClientUpdate }) => updateClient(id, data),
    onSuccess: () => { queryClient.invalidateQueries({ queryKey: ['clients'] }); setEditId(null) },
  })

  const deleteMut = useMutation({
    mutationFn: (id: number) => deleteClient(id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['clients'] }),
  })

  function startEdit(c: ClientRow) {
    setEditId(c.id)
    setEditForm({ full_name: c.full_name, description: c.description || '', telegram_group_link: c.telegram_group_link || '' })
  }

  function confirmDelete(c: ClientRow) {
    if (!window.confirm(`Удалить клиента «${c.full_name}»? Связанные заказы останутся, но привязка к клиенту будет утеряна.`)) return
    deleteMut.mutate(c.id)
  }

  async function handleGenerateLink(clientId: number, clientName: string) {
    setTgLoading(clientId)
    try {
      const { token } = await generateTelegramLink(clientId)
      setTgToken(token)
      setTgClientName(clientName)
    } finally {
      setTgLoading(null)
    }
  }

  function handleCopy(text: string) {
    navigator.clipboard.writeText(text)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  const tgCommand = tgToken ? `/start ${tgToken}` : ''

  return (
    <>
      {tgToken && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4" style={{ background: 'rgba(0,0,0,0.6)' }} onClick={() => setTgToken(null)}>
          <div className="rounded-xl p-6 w-full max-w-md" style={{ background: 'var(--color-surface)', border: '1px solid var(--color-card-border)' }} onClick={(e) => e.stopPropagation()}>
            <div className="flex items-center justify-between mb-4">
              <h3 className="font-semibold text-base" style={{ color: 'var(--color-text)' }}>Привязка Telegram — {tgClientName}</h3>
              <button onClick={() => setTgToken(null)} className="cursor-pointer" style={{ color: 'var(--color-muted)' }}><X size={18} /></button>
            </div>
            <p className="text-sm mb-3" style={{ color: 'var(--color-muted)' }}>Передайте клиенту инструкцию: открыть бота и отправить команду:</p>
            <div className="flex items-center gap-2 rounded-lg px-3 py-2 mb-3" style={{ background: 'var(--color-surface)', border: '1px solid var(--color-border)' }}>
              <code className="flex-1 text-sm break-all" style={{ color: 'var(--color-text)', fontFamily: 'monospace' }}>{tgCommand}</code>
              <button onClick={() => handleCopy(tgCommand)} className="flex-shrink-0 cursor-pointer" style={{ color: copied ? 'var(--color-success)' : 'var(--color-muted)' }} title="Копировать">
                {copied ? <Check size={16} /> : <Copy size={16} />}
              </button>
            </div>
            <p className="text-xs" style={{ color: 'var(--color-muted)' }}>Токен действителен 24 часа.</p>
            <div className="flex justify-end mt-4">
              <button onClick={() => setTgToken(null)} className="rounded-lg px-4 py-2 text-sm cursor-pointer" style={{ background: 'var(--color-surface)', border: '1px solid var(--color-border)', color: 'var(--color-text)' }}>Закрыть</button>
            </div>
          </div>
        </div>
      )}

      <div className="flex justify-end mb-4">
        <button onClick={() => setShowForm(!showForm)} className="rounded-lg px-4 py-2 text-sm font-medium cursor-pointer" style={{ background: 'var(--color-primary)', color: '#fff' }}>
          <Plus size={16} className="inline -mt-0.5" /> Добавить
        </button>
      </div>

      {showForm && (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3 mb-4">
          <input placeholder="Код (M33)" maxLength={20} value={form.code} onChange={(e) => setForm({ ...form, code: e.target.value })} className="rounded-lg px-3 py-2 text-sm outline-none" style={INPUT_STYLE} />
          <input placeholder="ФИО" maxLength={255} value={form.full_name} onChange={(e) => setForm({ ...form, full_name: e.target.value })} className="rounded-lg px-3 py-2 text-sm outline-none" style={INPUT_STYLE} />
          <input placeholder="Описание" value={form.description ?? ''} onChange={(e) => setForm({ ...form, description: e.target.value })} className="rounded-lg px-3 py-2 text-sm outline-none" style={INPUT_STYLE} />
          <button onClick={() => createMut.mutate()} disabled={createMut.isPending || !form.code || !form.full_name} className="rounded-lg px-4 py-2 text-sm font-medium cursor-pointer disabled:opacity-50" style={{ background: 'var(--color-success)', color: '#fff' }}>Создать</button>
        </div>
      )}

      {isLoading ? <SkeletonTableRows rows={5} /> : isError ? (
        <ErrorState message="Не удалось загрузить клиентов" onRetry={() => refetch()} />
      ) : (
        <div className="rounded-[8px] overflow-x-auto" style={{ background: 'var(--color-surface)', border: '1px solid var(--color-card-border)' }}>
          <table className="rtable w-full">
            <thead>
              <tr style={{ borderBottom: '1px solid var(--color-border)' }}>
                {['Код', 'ФИО', 'Описание', 'TG группа', 'TG привязка', ''].map((col) => (
                  <th key={col} className="px-4 py-3 text-left text-xs font-semibold" style={{ color: 'var(--color-muted)' }}>{col}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {(clients ?? []).map((c) => {
                const isEditing = editId === c.id
                return (
                  <tr key={c.id} style={{ borderBottom: '1px solid var(--color-border)', background: isEditing ? 'var(--color-surface-hover, var(--color-bg))' : undefined }}>
                    <td className="px-4 py-2.5 text-sm" data-label="Код" style={{ color: 'var(--color-text)' }}>{c.code}</td>
                    <td className="px-4 py-2.5 text-sm" data-label="ФИО" style={{ color: 'var(--color-text)' }}>
                      {isEditing
                        ? <input value={editForm.full_name ?? ''} onChange={(e) => setEditForm({ ...editForm, full_name: e.target.value })} maxLength={255} className="rounded px-2 py-1 text-sm w-full outline-none" style={INPUT_STYLE} />
                        : c.full_name}
                    </td>
                    <td className="px-4 py-2.5 text-sm" data-label="Описание" style={{ color: 'var(--color-text)' }}>
                      {isEditing
                        ? <input value={editForm.description ?? ''} onChange={(e) => setEditForm({ ...editForm, description: e.target.value })} className="rounded px-2 py-1 text-sm w-full outline-none" style={INPUT_STYLE} />
                        : c.description || '—'}
                    </td>
                    <td className="px-4 py-2.5 text-sm" data-label="TG группа" style={{ color: 'var(--color-text)' }}>
                      {isEditing
                        ? <input value={editForm.telegram_group_link ?? ''} onChange={(e) => setEditForm({ ...editForm, telegram_group_link: e.target.value })} placeholder="https://t.me/..." className="rounded px-2 py-1 text-sm w-full outline-none" style={INPUT_STYLE} />
                        : c.telegram_group_link || '—'}
                    </td>
                    <td className="px-4 py-2.5 text-sm" data-label="TG привязка">
                      {c.telegram_chat_id
                        ? <span className="text-xs px-2 py-0.5 rounded-full" style={{ background: 'rgba(34,197,94,0.15)', color: 'var(--color-success)' }}>Привязан</span>
                        : <span className="text-xs" style={{ color: 'var(--color-muted)' }}>Не привязан</span>}
                    </td>
                    <td className="px-4 py-2.5">
                      <div className="flex gap-1.5 justify-end">
                        {isEditing ? (
                          <>
                            <IconBtn onClick={() => updateMut.mutate({ id: c.id, data: editForm })} title="Сохранить" disabled={updateMut.isPending}><Save size={14} /></IconBtn>
                            <IconBtn onClick={() => setEditId(null)} title="Отмена"><X size={14} /></IconBtn>
                          </>
                        ) : (
                          <>
                            <IconBtn onClick={() => handleGenerateLink(c.id, c.full_name)} title="Сгенерировать токен Telegram" disabled={tgLoading === c.id}><Link size={14} /></IconBtn>
                            <IconBtn onClick={() => startEdit(c)} title="Редактировать"><Pencil size={14} /></IconBtn>
                            <IconBtn onClick={() => confirmDelete(c)} title="Удалить" danger disabled={deleteMut.isPending}><Trash2 size={14} /></IconBtn>
                          </>
                        )}
                      </div>
                    </td>
                  </tr>
                )
              })}
              {(clients ?? []).length === 0 && (
                <tr><td colSpan={6} className="px-4 py-8 text-center text-sm" style={{ color: 'var(--color-muted)' }}>Нет данных</td></tr>
              )}
            </tbody>
          </table>
        </div>
      )}
    </>
  )
}

// ── Suppliers ──────────────────────────────────────────────────────────────

interface SupplierRow { id: number; name: string; contacts: string; details: string }

function SuppliersTab() {
  const queryClient = useQueryClient()
  const [showForm, setShowForm] = useState(false)
  const [form, setForm] = useState<SupplierCreate>({ name: '' })
  const [editId, setEditId] = useState<number | null>(null)
  const [editForm, setEditForm] = useState<SupplierUpdate>({})

  const { data: suppliers, isLoading, isError, refetch } = useQuery({ queryKey: ['suppliers'], queryFn: fetchSuppliers })

  const createMut = useMutation({
    mutationFn: () => createSupplier(form),
    onSuccess: () => { queryClient.invalidateQueries({ queryKey: ['suppliers'] }); setShowForm(false); setForm({ name: '' }) },
  })

  const updateMut = useMutation({
    mutationFn: ({ id, data }: { id: number; data: SupplierUpdate }) => updateSupplier(id, data),
    onSuccess: () => { queryClient.invalidateQueries({ queryKey: ['suppliers'] }); setEditId(null) },
  })

  const deleteMut = useMutation({
    mutationFn: (id: number) => deleteSupplier(id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['suppliers'] }),
  })

  function startEdit(s: SupplierRow) {
    setEditId(s.id)
    setEditForm({ name: s.name, contacts: s.contacts || '', details: s.details || '' })
  }

  function confirmDelete(s: SupplierRow) {
    if (!window.confirm(`Удалить поставщика «${s.name}»? Это действие нельзя отменить.`)) return
    deleteMut.mutate(s.id)
  }

  return (
    <>
      <div className="flex justify-end mb-4">
        <button onClick={() => setShowForm(!showForm)} className="rounded-lg px-4 py-2 text-sm font-medium cursor-pointer" style={{ background: 'var(--color-primary)', color: '#fff' }}>
          <Plus size={16} className="inline -mt-0.5" /> Добавить
        </button>
      </div>

      {showForm && (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3 mb-4">
          <input placeholder="Название" maxLength={255} value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} className="rounded-lg px-3 py-2 text-sm outline-none" style={INPUT_STYLE} />
          <input placeholder="Контакты" value={form.contacts ?? ''} onChange={(e) => setForm({ ...form, contacts: e.target.value })} className="rounded-lg px-3 py-2 text-sm outline-none" style={INPUT_STYLE} />
          <input placeholder="Детали" value={form.details ?? ''} onChange={(e) => setForm({ ...form, details: e.target.value })} className="rounded-lg px-3 py-2 text-sm outline-none" style={INPUT_STYLE} />
          <button onClick={() => createMut.mutate()} disabled={createMut.isPending || !form.name} className="rounded-lg px-4 py-2 text-sm font-medium cursor-pointer disabled:opacity-50" style={{ background: 'var(--color-success)', color: '#fff' }}>Создать</button>
        </div>
      )}

      {isLoading ? <SkeletonTableRows rows={5} /> : isError ? (
        <ErrorState message="Не удалось загрузить поставщиков" onRetry={() => refetch()} />
      ) : (
        <div className="rounded-[8px] overflow-x-auto" style={{ background: 'var(--color-surface)', border: '1px solid var(--color-card-border)' }}>
          <table className="rtable w-full">
            <thead>
              <tr style={{ borderBottom: '1px solid var(--color-border)' }}>
                {['Название', 'Контакты', 'Детали', ''].map((col) => (
                  <th key={col} className="px-4 py-3 text-left text-xs font-semibold" style={{ color: 'var(--color-muted)' }}>{col}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {(suppliers ?? []).map((s) => {
                const isEditing = editId === s.id
                return (
                  <tr key={s.id} style={{ borderBottom: '1px solid var(--color-border)', background: isEditing ? 'var(--color-surface-hover, var(--color-bg))' : undefined }}>
                    <td className="px-4 py-2.5 text-sm" data-label="Название" style={{ color: 'var(--color-text)' }}>
                      {isEditing
                        ? <input value={editForm.name ?? ''} onChange={(e) => setEditForm({ ...editForm, name: e.target.value })} maxLength={255} className="rounded px-2 py-1 text-sm w-full outline-none" style={INPUT_STYLE} />
                        : s.name}
                    </td>
                    <td className="px-4 py-2.5 text-sm" data-label="Контакты" style={{ color: 'var(--color-text)' }}>
                      {isEditing
                        ? <input value={editForm.contacts ?? ''} onChange={(e) => setEditForm({ ...editForm, contacts: e.target.value })} className="rounded px-2 py-1 text-sm w-full outline-none" style={INPUT_STYLE} />
                        : s.contacts || '—'}
                    </td>
                    <td className="px-4 py-2.5 text-sm" data-label="Детали" style={{ color: 'var(--color-text)' }}>
                      {isEditing
                        ? <input value={editForm.details ?? ''} onChange={(e) => setEditForm({ ...editForm, details: e.target.value })} className="rounded px-2 py-1 text-sm w-full outline-none" style={INPUT_STYLE} />
                        : s.details || '—'}
                    </td>
                    <td className="px-4 py-2.5">
                      <div className="flex gap-1.5 justify-end">
                        {isEditing ? (
                          <>
                            <IconBtn onClick={() => updateMut.mutate({ id: s.id, data: editForm })} title="Сохранить" disabled={updateMut.isPending}><Save size={14} /></IconBtn>
                            <IconBtn onClick={() => setEditId(null)} title="Отмена"><X size={14} /></IconBtn>
                          </>
                        ) : (
                          <>
                            <IconBtn onClick={() => startEdit(s)} title="Редактировать"><Pencil size={14} /></IconBtn>
                            <IconBtn onClick={() => confirmDelete(s)} title="Удалить" danger disabled={deleteMut.isPending}><Trash2 size={14} /></IconBtn>
                          </>
                        )}
                      </div>
                    </td>
                  </tr>
                )
              })}
              {(suppliers ?? []).length === 0 && (
                <tr><td colSpan={4} className="px-4 py-8 text-center text-sm" style={{ color: 'var(--color-muted)' }}>Нет данных</td></tr>
              )}
            </tbody>
          </table>
        </div>
      )}
    </>
  )
}

// ── Role badge ─────────────────────────────────────────────────────────────

const ROLE_LABELS: Record<string, string> = {
  admin: 'Администратор',
  manager: 'Менеджер',
  observer: 'Наблюдатель',
}
const ROLE_COLOR: Record<string, TagColor> = {
  admin: 'blue',
  manager: 'green',
  observer: 'default',
}

function RoleBadge({ role }: { role: string }) {
  return <Tag color={ROLE_COLOR[role] ?? 'default'}>{ROLE_LABELS[role] ?? role}</Tag>
}

// ── Page ───────────────────────────────────────────────────────────────────

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
      <PageHeader title="База данных" subtitle="Пользователи, клиенты, поставщики" />
      <TabBar active={tab} onChange={setTab} />
      {tab === 'users' && <UsersTab />}
      {tab === 'clients' && <ClientsTab />}
      {tab === 'suppliers' && <SuppliersTab />}
    </div>
  )
}
