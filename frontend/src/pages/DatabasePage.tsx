import { useEffect, useRef, useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { fetchClients, createClient, updateClient, deleteClient, generateTelegramLink, type ClientCreate, type ClientUpdate } from '../api/clients'
import { fetchSuppliers, createSupplier, updateSupplier, deleteSupplier, type SupplierCreate, type SupplierUpdate } from '../api/suppliers'
import { fetchUsers, createUser, updateUser, deleteUser, type UserCreate, type UserUpdate } from '../api/users'
import { fetchNotificationLog } from '../api/notifications'
import { fetchActionLog } from '../api/actionLog'
import { fetchSystemHealth, type HealthStatus } from '../api/systemHealth'
import { fetchLogSources, fetchProcessLogs, type LogLine, type LogSource } from '../api/processLogs'
import { useAuth } from '../contexts/AuthContext'
import ErrorState from '../components/ErrorState'
import { SkeletonTableRows } from '../components/Skeleton'
import {
  Plus, Link, X, Copy, Check, Pencil, Trash2, Save,
  RefreshCw, Server, Database as DatabaseIcon, HardDrive, Globe,
  CircleCheck, TriangleAlert, CircleX, Search, Pause, Play, Download,
} from 'lucide-react'
import Tag, { type TagColor } from '../components/Tag'
import PageHeader from '../components/PageHeader'
import type { User } from '../api/auth'

type Tab = 'users' | 'clients' | 'suppliers' | 'notifications' | 'action-log' | 'health' | 'process-logs'

const TABS: { key: Tab; label: string }[] = [
  { key: 'users', label: 'Пользователи' },
  { key: 'clients', label: 'Клиенты' },
  { key: 'suppliers', label: 'Поставщики' },
  { key: 'notifications', label: 'Уведомления' },
  { key: 'action-log', label: 'Журнал действий' },
  { key: 'health', label: 'Состояние системы' },
  { key: 'process-logs', label: 'Логи процессов' },
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
  const [createError, setCreateError] = useState('')
  const [editId, setEditId] = useState<number | null>(null)
  const [editForm, setEditForm] = useState<UserUpdate & { password: string }>({ full_name: '', role: 'manager', is_active: true, password: '' })
  const [editError, setEditError] = useState('')

  const { data: users, isLoading, isError, refetch } = useQuery({ queryKey: ['users'], queryFn: fetchUsers })

  const createMut = useMutation({
    mutationFn: () => createUser(form),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['users'] })
      setShowForm(false)
      setForm({ login: '', password: '', role: 'manager', full_name: '' })
      setCreateError('')
    },
    onError: (err: Error) => setCreateError(err.message),
  })

  const updateMut = useMutation({
    mutationFn: ({ id, data }: { id: number; data: UserUpdate }) => updateUser(id, data),
    onSuccess: () => { queryClient.invalidateQueries({ queryKey: ['users'] }); setEditId(null); setEditError('') },
    onError: (err: Error) => setEditError(err.message),
  })

  const deleteMut = useMutation({
    mutationFn: (id: number) => deleteUser(id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['users'] }),
  })

  function startEdit(u: User) {
    setEditId(u.id)
    setEditForm({ full_name: u.full_name, role: u.role as UserUpdate['role'], is_active: u.is_active, password: '' })
    setEditError('')
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
          onClick={() => { setShowForm(!showForm); setCreateError('') }}
          className="rounded-lg px-4 py-2 text-sm font-medium cursor-pointer"
          style={{ background: 'var(--color-primary)', color: '#fff' }}
        >
          <Plus size={16} className="inline -mt-0.5" /> Добавить
        </button>
      </div>

      {showForm && (
        <div className="mb-4">
          {createError && (
            <div
              className="rounded-lg px-3 py-2 mb-3 text-sm"
              style={{ background: 'var(--color-danger-bg)', color: 'var(--color-danger)' }}
            >
              {createError}
            </div>
          )}
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-3">
            <input placeholder="Логин" maxLength={64} value={form.login} onChange={(e) => { setForm({ ...form, login: e.target.value }); setCreateError('') }} className="rounded-lg px-3 py-2 text-sm outline-none" style={INPUT_STYLE} />
            <div>
              <input
                placeholder="Пароль"
                type="password"
                value={form.password}
                onChange={(e) => { setForm({ ...form, password: e.target.value }); setCreateError('') }}
                className="rounded-lg px-3 py-2 text-sm outline-none w-full"
                style={form.password.length > 0 && form.password.length < 8 ? { ...INPUT_STYLE, border: '1px solid var(--color-danger)' } : INPUT_STYLE}
              />
              <span className="block text-xs mt-1" style={{ color: form.password.length > 0 && form.password.length < 8 ? 'var(--color-danger)' : 'var(--color-muted)' }}>
                Минимум 8 символов
              </span>
            </div>
            <input placeholder="ФИО" maxLength={255} value={form.full_name} onChange={(e) => setForm({ ...form, full_name: e.target.value })} className="rounded-lg px-3 py-2 text-sm outline-none" style={INPUT_STYLE} />
            <select value={form.role} onChange={(e) => setForm({ ...form, role: e.target.value as UserCreate['role'] })} className="rounded-lg px-3 py-2 text-sm outline-none" style={INPUT_STYLE}>
              <option value="manager">Менеджер</option>
              <option value="admin">Администратор</option>
              <option value="observer">Наблюдатель</option>
            </select>
            <button
              onClick={() => createMut.mutate()}
              disabled={createMut.isPending || !form.login || form.password.length < 8}
              className="rounded-lg px-4 py-2 text-sm font-medium cursor-pointer disabled:opacity-50 h-fit"
              style={{ background: 'var(--color-success)', color: '#fff' }}
            >
              {createMut.isPending ? 'Создание...' : 'Создать'}
            </button>
          </div>
        </div>
      )}

      {isLoading ? <SkeletonTableRows rows={5} /> : isError ? (
        <ErrorState message="Не удалось загрузить пользователей" onRetry={() => refetch()} />
      ) : (
        <div className="rounded-[8px] overflow-x-auto" style={{ background: 'var(--color-surface)', border: '1px solid var(--color-card-border)', boxShadow: 'var(--shadow-card)' }}>
          {editError && (
            <div
              className="text-sm px-4 py-2.5"
              style={{ background: 'var(--color-danger-bg)', color: 'var(--color-danger)', borderBottom: '1px solid var(--color-border)' }}
            >
              {editError}
            </div>
          )}
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
                        ? (() => {
                            const pwTooShort = (editForm.password?.length ?? 0) > 0 && (editForm.password?.length ?? 0) < 8
                            return (
                              <input
                                type="password"
                                placeholder="Оставьте пустым"
                                title={pwTooShort ? 'Минимум 8 символов' : undefined}
                                value={editForm.password ?? ''}
                                onChange={(e) => { setEditForm({ ...editForm, password: e.target.value }); setEditError('') }}
                                className="rounded px-2 py-1 text-sm w-full outline-none"
                                style={pwTooShort ? { ...INPUT_STYLE, border: '1px solid var(--color-danger)' } : INPUT_STYLE}
                              />
                            )
                          })()
                        : ''}
                    </td>
                    <td className="px-4 py-2.5">
                      <div className="flex gap-1.5 justify-end">
                        {isEditing ? (
                          <>
                            <IconBtn onClick={() => saveEdit(u.id)} title="Сохранить" disabled={updateMut.isPending || ((editForm.password?.length ?? 0) > 0 && (editForm.password?.length ?? 0) < 8)}><Save size={14} /></IconBtn>
                            <IconBtn onClick={() => { setEditId(null); setEditError('') }} title="Отмена"><X size={14} /></IconBtn>
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
  id: number; code: string; full_name: string; description: string; telegram_group_link: string; telegram_chat_id: string; telegram_groups: string[]
}

function ClientsTab() {
  const queryClient = useQueryClient()
  const [showForm, setShowForm] = useState(false)
  const [form, setForm] = useState<ClientCreate>({ full_name: '' })
  const [editId, setEditId] = useState<number | null>(null)
  const [editForm, setEditForm] = useState<ClientUpdate>({})
  const [tgToken, setTgToken] = useState<string | null>(null)
  const [tgClientName, setTgClientName] = useState('')
  const [tgLoading, setTgLoading] = useState<number | null>(null)
  const [copied, setCopied] = useState(false)

  const { data: clients, isLoading, isError, refetch } = useQuery({ queryKey: ['clients'], queryFn: fetchClients })

  const createMut = useMutation({
    mutationFn: () => createClient(form),
    onSuccess: () => { queryClient.invalidateQueries({ queryKey: ['clients'] }); setShowForm(false); setForm({ full_name: '' }) },
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
    if (!window.confirm(`Удалить клиента «${c.full_name}»? Это действие нельзя отменить. Если за клиентом остались заказы, система откажет и покажет их номера.`)) return
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
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3 mb-4">
          <input placeholder="ФИО" maxLength={255} value={form.full_name} onChange={(e) => setForm({ ...form, full_name: e.target.value })} className="rounded-lg px-3 py-2 text-sm outline-none" style={INPUT_STYLE} />
          <input placeholder="Описание" value={form.description ?? ''} onChange={(e) => setForm({ ...form, description: e.target.value })} className="rounded-lg px-3 py-2 text-sm outline-none" style={INPUT_STYLE} />
          <button onClick={() => createMut.mutate()} disabled={createMut.isPending || !form.full_name} className="rounded-lg px-4 py-2 text-sm font-medium cursor-pointer disabled:opacity-50" style={{ background: 'var(--color-success)', color: '#fff' }}>Создать</button>
        </div>
      )}

      {isLoading ? <SkeletonTableRows rows={5} /> : isError ? (
        <ErrorState message="Не удалось загрузить клиентов" onRetry={() => refetch()} />
      ) : (
        <div className="rounded-[8px] overflow-x-auto" style={{ background: 'var(--color-surface)', border: '1px solid var(--color-card-border)', boxShadow: 'var(--shadow-card)' }}>
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
                        : c.telegram_groups.length > 0
                          ? `👥 ${c.telegram_groups.join(', ')}`
                          : c.telegram_group_link || (c.telegram_chat_id ? 'нет в группах' : '—')}
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
        <div className="rounded-[8px] overflow-x-auto" style={{ background: 'var(--color-surface)', border: '1px solid var(--color-card-border)', boxShadow: 'var(--shadow-card)' }}>
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

// ── Notifications (read-only) ───────────────────────────────────────────────

function NotificationsTab() {
  const { data: entries, isLoading, isError, refetch } = useQuery({
    queryKey: ['notification-log'],
    queryFn: () => fetchNotificationLog(),
  })

  return isLoading ? <SkeletonTableRows rows={5} /> : isError ? (
    <ErrorState message="Не удалось загрузить журнал уведомлений" onRetry={() => refetch()} />
  ) : (
    <div className="rounded-[8px] overflow-x-auto" style={{ background: 'var(--color-surface)', border: '1px solid var(--color-card-border)', boxShadow: 'var(--shadow-card)' }}>
      <table className="rtable w-full">
        <thead>
          <tr style={{ borderBottom: '1px solid var(--color-border)' }}>
            {['Дата', 'Получатель', 'Сообщение', 'Статус', 'Ошибка'].map((col) => (
              <th key={col} className="px-4 py-3 text-left text-xs font-semibold" style={{ color: 'var(--color-muted)' }}>{col}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {(entries ?? []).map((n) => (
            <tr key={n.id} style={{ borderBottom: '1px solid var(--color-border)' }}>
              <td className="px-4 py-2.5 text-sm whitespace-nowrap" data-label="Дата" style={{ color: 'var(--color-text)' }}>
                {new Date(n.created_at).toLocaleString('ru-RU')}
              </td>
              <td className="px-4 py-2.5 text-sm" data-label="Получатель" style={{ color: 'var(--color-text)' }}>{n.target}</td>
              <td className="px-4 py-2.5 text-sm max-w-md truncate" data-label="Сообщение" style={{ color: 'var(--color-text)' }} title={n.message}>{n.message}</td>
              <td className="px-4 py-2.5 text-sm" data-label="Статус">
                <span style={{ color: n.status === 'sent' ? 'var(--color-success)' : 'var(--color-danger)' }}>
                  {n.status === 'sent' ? 'Доставлено' : 'Не доставлено'}
                </span>
              </td>
              <td className="px-4 py-2.5 text-sm max-w-xs truncate" data-label="Ошибка" style={{ color: 'var(--color-muted)' }} title={n.error}>{n.error || '—'}</td>
            </tr>
          ))}
          {(entries ?? []).length === 0 && (
            <tr><td colSpan={5} className="px-4 py-8 text-center text-sm" style={{ color: 'var(--color-muted)' }}>Нет данных</td></tr>
          )}
        </tbody>
      </table>
    </div>
  )
}

// ── Action log (read-only) ──────────────────────────────────────────────────

function ActionLogTab() {
  const { data: entries, isLoading, isError, refetch } = useQuery({
    queryKey: ['action-log'],
    queryFn: () => fetchActionLog(),
  })

  return isLoading ? <SkeletonTableRows rows={5} /> : isError ? (
    <ErrorState message="Не удалось загрузить журнал действий" onRetry={() => refetch()} />
  ) : (
    <div className="rounded-[8px] overflow-x-auto" style={{ background: 'var(--color-surface)', border: '1px solid var(--color-card-border)', boxShadow: 'var(--shadow-card)' }}>
      <table className="rtable w-full">
        <thead>
          <tr style={{ borderBottom: '1px solid var(--color-border)' }}>
            {['Дата', 'Кто', 'Действие', 'Сущность', 'Детали'].map((col) => (
              <th key={col} className="px-4 py-3 text-left text-xs font-semibold" style={{ color: 'var(--color-muted)' }}>{col}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {(entries ?? []).map((a) => (
            <tr key={a.id} style={{ borderBottom: '1px solid var(--color-border)' }}>
              <td className="px-4 py-2.5 text-sm whitespace-nowrap" data-label="Дата" style={{ color: 'var(--color-text)' }}>
                {new Date(a.created_at).toLocaleString('ru-RU')}
              </td>
              <td className="px-4 py-2.5 text-sm" data-label="Кто" style={{ color: 'var(--color-text)' }}>{a.actor_name}</td>
              <td className="px-4 py-2.5 text-sm" data-label="Действие" style={{ color: 'var(--color-text)' }}>{a.action}</td>
              <td className="px-4 py-2.5 text-sm" data-label="Сущность" style={{ color: 'var(--color-text)' }}>{a.entity_type} #{a.entity_id}</td>
              <td className="px-4 py-2.5 text-sm max-w-xs truncate" data-label="Детали" style={{ color: 'var(--color-muted)' }} title={a.details}>{a.details || '—'}</td>
            </tr>
          ))}
          {(entries ?? []).length === 0 && (
            <tr><td colSpan={5} className="px-4 py-8 text-center text-sm" style={{ color: 'var(--color-muted)' }}>Нет данных</td></tr>
          )}
        </tbody>
      </table>
    </div>
  )
}

// ── System health ────────────────────────────────────────────────────────

const STATUS_LABEL: Record<HealthStatus, string> = { ok: 'Работает', warn: 'Внимание', down: 'Сбой' }
const STATUS_COLOR: Record<HealthStatus, string> = {
  ok: 'var(--color-success)',
  warn: 'var(--color-warning)',
  down: 'var(--color-danger)',
}
const STATUS_BG: Record<HealthStatus, string> = {
  ok: 'var(--color-success-bg)',
  warn: 'var(--color-warning-bg)',
  down: 'var(--color-danger-bg)',
}
const STATUS_ICON: Record<HealthStatus, typeof CircleCheck> = { ok: CircleCheck, warn: TriangleAlert, down: CircleX }
const SERVICE_ICON: Record<string, typeof Server> = {
  backend: Server, database: DatabaseIcon, storage: HardDrive, frontend: Globe,
}

function codeTone(code: number | null): { color: string; background: string } {
  if (code === null) return { color: 'var(--color-danger)', background: 'var(--color-danger-bg)' }
  if (code < 400) return { color: 'var(--color-success)', background: 'var(--color-success-bg)' }
  if (code < 500) return { color: 'var(--color-warning)', background: 'var(--color-warning-bg)' }
  return { color: 'var(--color-danger)', background: 'var(--color-danger-bg)' }
}

function fmtTime(iso?: string) {
  return iso ? new Date(iso).toLocaleTimeString('ru-RU') : ''
}

function SystemHealthTab() {
  const [autoRefresh, setAutoRefresh] = useState(false)
  const { data: report, isLoading, isError, refetch, isFetching } = useQuery({
    queryKey: ['system-health'],
    queryFn: fetchSystemHealth,
  })

  useEffect(() => {
    if (!autoRefresh) return
    const id = setInterval(() => refetch(), 10000)
    return () => clearInterval(id)
  }, [autoRefresh, refetch])

  return (
    <>
      <div className="flex items-start justify-between gap-4 flex-wrap mb-5">
        <p className="text-sm" style={{ color: 'var(--color-muted)' }}>
          Здоровье сервисов и статус-коды страниц
          {report?.checked_at && <> · обновлено {fmtTime(report.checked_at)}</>}
        </p>
        <div className="flex items-center gap-2">
          <button
            onClick={() => setAutoRefresh((v) => !v)}
            className="rounded-lg px-3 py-2 text-sm cursor-pointer"
            style={{
              background: 'transparent',
              border: '1px solid var(--color-border)',
              color: autoRefresh ? 'var(--color-primary)' : 'var(--color-text)',
            }}
          >
            {autoRefresh ? 'Авто: вкл' : 'Авто: выкл'}
          </button>
          <button
            onClick={() => refetch()}
            disabled={isFetching}
            className="flex items-center gap-1.5 rounded-lg px-3 py-2 text-sm font-medium cursor-pointer disabled:opacity-60"
            style={{ background: 'var(--color-primary)', color: '#fff' }}
          >
            <RefreshCw size={14} className={isFetching ? 'animate-spin' : ''} /> Обновить
          </button>
        </div>
      </div>

      {isLoading ? <SkeletonTableRows rows={5} /> : isError ? (
        <ErrorState message="Не удалось загрузить состояние системы" onRetry={() => refetch()} />
      ) : !report ? null : !report.enabled ? (
        <div className="rounded-[8px] p-6 text-sm" style={{ background: 'var(--color-surface)', border: '1px solid var(--color-card-border)', color: 'var(--color-muted)' }}>
          Проверки состояния отключены (<code>HEALTH_CHECK_ENABLED=false</code>).
        </div>
      ) : (
        <>
          <div
            className="rounded-[8px] p-5 mb-5 flex items-center gap-4"
            style={{ background: STATUS_BG[report.overall], border: '1px solid var(--color-card-border)' }}
          >
            {(() => { const Icon = STATUS_ICON[report.overall]; return <Icon size={36} style={{ color: STATUS_COLOR[report.overall], flexShrink: 0 }} /> })()}
            <div>
              <p className="text-base font-bold" style={{ color: STATUS_COLOR[report.overall] }}>
                Система: {STATUS_LABEL[report.overall]}
              </p>
              <p className="text-sm" style={{ color: 'var(--color-muted)' }}>
                Сервисов: {report.services.length} · проверено страниц/эндпоинтов: {report.pages.length}
              </p>
            </div>
          </div>

          <h3 className="text-xs font-semibold uppercase tracking-wide mb-3" style={{ color: 'var(--color-muted)' }}>Сервисы</h3>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3 mb-7">
            {report.services.map((s) => {
              const ServiceIcon = SERVICE_ICON[s.name] || Server
              const StatusIcon = STATUS_ICON[s.status]
              return (
                <div key={s.name} className="rounded-[8px] p-4" style={{ background: 'var(--color-surface)', border: '1px solid var(--color-card-border)', boxShadow: 'var(--shadow-card)' }}>
                  <div className="flex items-center justify-between gap-2">
                    <span className="flex items-center gap-2 text-sm font-semibold" style={{ color: 'var(--color-text)' }}>
                      <ServiceIcon size={16} style={{ color: 'var(--color-muted)' }} />
                      {s.label}
                    </span>
                    <span
                      className="text-[11px] font-semibold px-2 py-0.5 rounded-full inline-flex items-center gap-1"
                      style={{ color: STATUS_COLOR[s.status], background: STATUS_BG[s.status] }}
                    >
                      <StatusIcon size={12} /> {STATUS_LABEL[s.status]}
                    </span>
                  </div>
                  <div className="mt-2 text-xs flex items-center gap-3" style={{ color: 'var(--color-muted)' }}>
                    {s.latency_ms !== undefined && <span>{s.latency_ms} мс</span>}
                    {s.detail && <span className="truncate" title={s.detail}>{s.detail}</span>}
                  </div>
                </div>
              )
            })}
          </div>

          <h3 className="text-xs font-semibold uppercase tracking-wide mb-3" style={{ color: 'var(--color-muted)' }}>Страницы и эндпоинты</h3>
          <div className="rounded-[8px] overflow-x-auto" style={{ background: 'var(--color-surface)', border: '1px solid var(--color-card-border)', boxShadow: 'var(--shadow-card)' }}>
            <table className="rtable w-full">
              <thead>
                <tr style={{ borderBottom: '1px solid var(--color-border)' }}>
                  {['Тип', 'Адрес', 'Код', 'Ответ', 'Статус'].map((col) => (
                    <th key={col} className="px-4 py-3 text-left text-xs font-semibold" style={{ color: 'var(--color-muted)' }}>{col}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {report.pages.map((p) => {
                  const StatusIcon = STATUS_ICON[p.status]
                  const tone = codeTone(p.status_code)
                  return (
                    <tr key={p.kind + p.name} style={{ borderBottom: '1px solid var(--color-border)' }}>
                      <td className="px-4 py-2.5" data-label="Тип">
                        <span className="text-[11px] font-semibold px-1.5 py-0.5 rounded uppercase" style={{ background: 'var(--color-surface-3)', color: 'var(--color-muted)' }}>{p.kind}</span>
                      </td>
                      <td className="px-4 py-2.5 text-sm" data-label="Адрес" style={{ color: 'var(--color-text)', fontFamily: 'monospace' }}>{p.name}</td>
                      <td className="px-4 py-2.5" data-label="Код">
                        <span className="text-xs font-semibold px-2 py-0.5 rounded" style={{ color: tone.color, background: tone.background }}>{p.status_code ?? 'ERR'}</span>
                      </td>
                      <td className="px-4 py-2.5 text-sm" data-label="Ответ" style={{ color: 'var(--color-muted)' }}>
                        {p.latency_ms !== undefined && <span>{p.latency_ms} мс</span>}
                        {p.detail && <span className="ml-2 truncate" style={{ color: 'var(--color-danger)' }} title={p.detail}>{p.detail}</span>}
                      </td>
                      <td className="px-4 py-2.5" data-label="Статус">
                        <StatusIcon size={16} style={{ color: STATUS_COLOR[p.status] }} />
                      </td>
                    </tr>
                  )
                })}
                {report.pages.length === 0 && (
                  <tr><td colSpan={5} className="px-4 py-8 text-center text-sm" style={{ color: 'var(--color-muted)' }}>Нет данных</td></tr>
                )}
              </tbody>
            </table>
          </div>
        </>
      )}
    </>
  )
}

// ── Process logs ─────────────────────────────────────────────────────────

const LOG_LEVELS = ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL']

const LEVEL_COLOR: Record<string, string> = {
  CRITICAL: '#fca5a5',
  ERROR: '#fca5a5',
  WARNING: '#fcd34d',
  INFO: '#7dd3fc',
  DEBUG: '#64748b',
}
const LINE_COLOR: Record<string, string> = {
  CRITICAL: '#fca5a5',
  ERROR: '#fca5a5',
  WARNING: '#fcd34d',
  DEBUG: '#64748b',
}

function fmtLogTs(iso: string | null) {
  if (!iso) return ''
  return new Date(iso).toLocaleString('ru-RU', {
    day: '2-digit', month: '2-digit', year: '2-digit',
    hour: '2-digit', minute: '2-digit', second: '2-digit',
  })
}

function toIso(local: string): string | undefined {
  return local ? new Date(local).toISOString() : undefined
}

function ProcessLogsTab() {
  const [source, setSource] = useState('')
  const [since, setSince] = useState('')
  const [until, setUntil] = useState('')
  const [tail, setTail] = useState(500)
  const [q, setQ] = useState('')
  const [qDraft, setQDraft] = useState('')
  const [levels, setLevels] = useState<string[]>([])
  const [showTimestamps, setShowTimestamps] = useState(true)
  const [autoRefresh, setAutoRefresh] = useState(false)
  const logBoxRef = useRef<HTMLDivElement>(null)

  const { data: sourcesRes } = useQuery({ queryKey: ['log-sources'], queryFn: fetchLogSources })

  useEffect(() => {
    if (!source && sourcesRes?.available && sourcesRes.items.length > 0) {
      const backend = sourcesRes.items.find((s: LogSource) => s.name === 'backend')
      setSource(backend?.name ?? sourcesRes.items[0].name)
    }
  }, [sourcesRes, source])

  const { data: logsRes, isLoading, isFetching, isError, refetch } = useQuery({
    queryKey: ['process-logs', source, since, until, tail, q, levels],
    queryFn: () => fetchProcessLogs({
      source,
      since: toIso(since),
      until: toIso(until),
      tail,
      q: q || undefined,
      level: levels.length ? levels : undefined,
    }),
    enabled: !!source && sourcesRes?.available === true,
  })

  useEffect(() => {
    if (!autoRefresh) return
    const id = setInterval(() => refetch(), 5000)
    return () => clearInterval(id)
  }, [autoRefresh, refetch])

  useEffect(() => {
    if (logBoxRef.current) logBoxRef.current.scrollTop = logBoxRef.current.scrollHeight
  }, [logsRes])

  function toggleLevel(l: string) {
    setLevels((prev) => (prev.includes(l) ? prev.filter((x) => x !== l) : [...prev, l]))
  }

  function downloadRaw() {
    const lines = logsRes?.lines ?? []
    const body = lines.map((l: LogLine) => (showTimestamps && l.ts ? `${l.ts} ${l.text}` : l.text)).join('\n')
    const blob = new Blob([body], { type: 'text/plain;charset=utf-8' })
    const a = document.createElement('a')
    a.href = URL.createObjectURL(blob)
    a.download = `${source || 'logs'}-${new Date().toISOString().slice(0, 19)}.log`
    a.click()
    URL.revokeObjectURL(a.href)
  }

  if (!sourcesRes) return <SkeletonTableRows rows={5} />

  if (!sourcesRes.available) {
    return (
      <div className="rounded-[8px] p-6" style={{ background: 'var(--color-surface)', border: '1px solid var(--color-card-border)' }}>
        <p className="font-semibold mb-1" style={{ color: 'var(--color-text)' }}>Логи недоступны</p>
        <p className="text-sm" style={{ color: 'var(--color-muted)' }}>{sourcesRes.detail || 'docker-socket-proxy не запущен.'}</p>
      </div>
    )
  }

  return (
    <>
      <div className="rounded-[8px] p-4 mb-4 space-y-3" style={{ background: 'var(--color-surface)', border: '1px solid var(--color-card-border)', boxShadow: 'var(--shadow-card)' }}>
        <div className="flex flex-wrap items-end gap-3">
          <label className="block">
            <span className="text-[11px] uppercase tracking-wide" style={{ color: 'var(--color-faint)' }}>Источник</span>
            <select value={source} onChange={(e) => setSource(e.target.value)} className="block mt-1 rounded-lg px-3 py-2 text-sm outline-none min-w-[200px]" style={INPUT_STYLE}>
              {sourcesRes.items.map((s) => (
                <option key={s.container} value={s.name}>{s.name} — {s.state}</option>
              ))}
            </select>
          </label>
          <label className="block">
            <span className="text-[11px] uppercase tracking-wide" style={{ color: 'var(--color-faint)' }}>С момента</span>
            <input type="datetime-local" value={since} onChange={(e) => setSince(e.target.value)} className="block mt-1 rounded-lg px-3 py-2 text-sm outline-none" style={INPUT_STYLE} />
          </label>
          <label className="block">
            <span className="text-[11px] uppercase tracking-wide" style={{ color: 'var(--color-faint)' }}>До момента</span>
            <input type="datetime-local" value={until} onChange={(e) => setUntil(e.target.value)} className="block mt-1 rounded-lg px-3 py-2 text-sm outline-none" style={INPUT_STYLE} />
          </label>
          <label className="block">
            <span className="text-[11px] uppercase tracking-wide" style={{ color: 'var(--color-faint)' }}>Строк</span>
            <select value={tail} onChange={(e) => setTail(Number(e.target.value))} className="block mt-1 rounded-lg px-3 py-2 text-sm outline-none" style={INPUT_STYLE}>
              {[200, 500, 1000, 2000, 5000].map((n) => <option key={n} value={n}>{n}</option>)}
            </select>
          </label>
          <label className="block flex-1 min-w-[180px]">
            <span className="text-[11px] uppercase tracking-wide" style={{ color: 'var(--color-faint)' }}>Поиск</span>
            <div className="relative mt-1">
              <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2" style={{ color: 'var(--color-faint)' }} />
              <input
                type="search"
                placeholder="подстрока в логе…"
                value={qDraft}
                onChange={(e) => setQDraft(e.target.value)}
                onKeyDown={(e) => { if (e.key === 'Enter') setQ(qDraft) }}
                className="w-full rounded-lg pl-9 pr-3 py-2 text-sm outline-none"
                style={INPUT_STYLE}
              />
            </div>
          </label>
        </div>

        <div className="flex flex-wrap items-center gap-2">
          <span className="text-[11px] uppercase tracking-wide mr-1" style={{ color: 'var(--color-faint)' }}>Уровень:</span>
          {LOG_LEVELS.map((l) => (
            <button
              key={l}
              onClick={() => toggleLevel(l)}
              className="text-[11px] font-semibold px-2.5 py-1 rounded cursor-pointer transition-colors"
              style={levels.includes(l)
                ? { background: 'var(--color-primary)', color: '#fff', border: '1px solid var(--color-primary)' }
                : { background: 'transparent', color: 'var(--color-muted)', border: '1px solid var(--color-border)' }}
            >
              {l}
            </button>
          ))}

          <div className="flex-1" />

          <label className="flex items-center gap-1.5 text-sm cursor-pointer select-none" style={{ color: 'var(--color-muted)' }}>
            <input type="checkbox" checked={showTimestamps} onChange={(e) => setShowTimestamps(e.target.checked)} /> Время
          </label>
          <IconBtn onClick={() => refetch()} title="Обновить" disabled={isFetching}>
            <RefreshCw size={14} className={isFetching ? 'animate-spin' : ''} />
          </IconBtn>
          <IconBtn onClick={() => setAutoRefresh((v) => !v)} title={autoRefresh ? 'Остановить авто-обновление' : 'Авто-обновление (5с)'}>
            {autoRefresh ? <Pause size={14} /> : <Play size={14} />}
          </IconBtn>
          <IconBtn onClick={downloadRaw} title="Скачать" disabled={!logsRes?.lines.length}>
            <Download size={14} />
          </IconBtn>
        </div>
      </div>

      {isError && (
        <div className="rounded-[8px] p-4 mb-4 text-sm" style={{ background: 'var(--color-danger-bg)', color: 'var(--color-danger)' }}>
          Не удалось загрузить логи
        </div>
      )}

      <div className="rounded-xl overflow-hidden" style={{ border: '1px solid var(--color-card-border)', background: '#0d1117' }}>
        <div className="flex items-center justify-between px-4 py-2 text-[12px]" style={{ borderBottom: '1px solid rgba(255,255,255,0.1)', color: '#94a3b8' }}>
          <span style={{ fontFamily: 'monospace' }}>{source}</span>
          <span>
            {logsRes?.count ?? 0} строк{logsRes?.truncated && <> · показаны последние {tail}</>}
          </span>
        </div>
        <div ref={logBoxRef} className="overflow-auto px-3 py-2" style={{ maxHeight: '62vh', fontFamily: 'monospace', fontSize: 12.5, lineHeight: 1.6 }}>
          {isLoading ? (
            <div className="px-1 py-4" style={{ color: '#64748b' }}>Загрузка…</div>
          ) : !logsRes?.lines.length ? (
            <div className="px-1 py-4" style={{ color: '#64748b' }}>Записей не найдено.</div>
          ) : (
            logsRes.lines.map((l, i) => (
              <div key={i} className="whitespace-pre-wrap break-words px-1 py-0.5" style={{ color: LINE_COLOR[l.level] || '#cbd5e1' }}>
                {showTimestamps && l.ts && <span style={{ color: '#64748b' }}>{fmtLogTs(l.ts)} </span>}
                {l.level && <span className="font-bold" style={{ color: LEVEL_COLOR[l.level] || '#475569' }}>{l.level} </span>}
                <span>{l.text}</span>
              </div>
            ))
          )}
        </div>
      </div>
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
      {tab === 'notifications' && <NotificationsTab />}
      {tab === 'action-log' && <ActionLogTab />}
      {tab === 'health' && <SystemHealthTab />}
      {tab === 'process-logs' && <ProcessLogsTab />}
    </div>
  )
}
