import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useNavigate } from 'react-router-dom'
import { createOrder } from '../api/orders'
import { fetchClients } from '../api/clients'
import { fetchUsers } from '../api/users'
import { useAuth } from '../contexts/AuthContext'
import FileUploader, { type UploadedFile } from './FileUploader'

const CURRENCIES = ['USD', 'CNY', 'RUB']
const MAX_ORDER_FILES = 5

export default function CreateOrderModal({ onClose }: { onClose: () => void }) {
  const { user } = useAuth()
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const isAdmin = user?.role === 'admin'

  const [clientId, setClientId] = useState<number | ''>('')
  const [currency, setCurrency] = useState('RUB')
  const [details, setDetails] = useState('')
  const [managerId, setManagerId] = useState<number | ''>('')
  const [files, setFiles] = useState<UploadedFile[]>([])
  const [error, setError] = useState('')

  const { data: clients } = useQuery({ queryKey: ['clients'], queryFn: fetchClients })
  const { data: users } = useQuery({ queryKey: ['users'], queryFn: fetchUsers, enabled: isAdmin })
  const assignableManagers = users?.filter((u) => u.role === 'admin' || u.role === 'manager')

  const mutation = useMutation({
    mutationFn: () =>
      createOrder({
        client_id: Number(clientId),
        currency,
        details,
        file_keys: files.map((f) => f.key),
        ...(isAdmin && managerId ? { manager_id: Number(managerId) } : {}),
      }),
    onSuccess: (order) => {
      queryClient.invalidateQueries({ queryKey: ['orders'] })
      navigate(`/orders/${order.id}`)
    },
    onError: (err: Error) => setError(err.message),
  })

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4"
      style={{ background: 'rgba(0,0,0,0.5)' }}
      onClick={onClose}
    >
      <div
        onClick={(e) => e.stopPropagation()}
        className="w-full max-w-md rounded-[10px] p-6"
        style={{ background: 'var(--color-surface)', border: '1px solid var(--color-border)' }}
      >
        <h3 className="text-base font-semibold mb-5" style={{ color: 'var(--color-text)' }}>
          Создать заказ
        </h3>

        {error && (
          <div
            className="rounded-lg px-3 py-2 mb-4 text-sm"
            style={{ background: 'var(--color-danger-bg)', color: 'var(--color-danger)' }}
          >
            {error}
          </div>
        )}

        <label className="block mb-4">
          <span className="block text-sm mb-1.5" style={{ color: 'var(--color-muted)' }}>Клиент</span>
          <select
            value={clientId}
            onChange={(e) => setClientId(e.target.value ? Number(e.target.value) : '')}
            className="w-full rounded-lg px-3 py-2.5 text-sm outline-none"
            style={{ background: 'var(--color-surface)', border: '1px solid var(--color-border)', color: 'var(--color-text)' }}
          >
            <option value="">Выберите клиента</option>
            {clients?.map((c) => (
              <option key={c.id} value={c.id}>{c.code} — {c.full_name}</option>
            ))}
          </select>
        </label>

        <label className="block mb-4">
          <span className="block text-sm mb-1.5" style={{ color: 'var(--color-muted)' }}>Валюта</span>
          <select
            value={currency}
            onChange={(e) => setCurrency(e.target.value)}
            className="w-full rounded-lg px-3 py-2.5 text-sm outline-none"
            style={{ background: 'var(--color-surface)', border: '1px solid var(--color-border)', color: 'var(--color-text)' }}
          >
            {CURRENCIES.map((c) => <option key={c} value={c}>{c}</option>)}
          </select>
        </label>

        <label className="block mb-4">
          <span className="block text-sm mb-1.5" style={{ color: 'var(--color-muted)' }}>Детали</span>
          <textarea
            value={details}
            onChange={(e) => setDetails(e.target.value)}
            rows={3}
            className="w-full rounded-lg px-3 py-2.5 text-sm outline-none resize-none"
            style={{ background: 'var(--color-surface)', border: '1px solid var(--color-border)', color: 'var(--color-text)' }}
          />
        </label>

        <div className="mb-4">
          <span className="block text-sm mb-1.5" style={{ color: 'var(--color-muted)' }}>Файлы (до {MAX_ORDER_FILES})</span>
          <FileUploader
            files={files}
            context="order"
            disabled={files.length >= MAX_ORDER_FILES}
            onUpload={(file) => setFiles((prev) => (prev.length >= MAX_ORDER_FILES ? prev : [...prev, file]))}
            onRemove={(key) => setFiles((prev) => prev.filter((f) => f.key !== key))}
          />
        </div>

        {isAdmin ? (
          <label className="block mb-6">
            <span className="block text-sm mb-1.5" style={{ color: 'var(--color-muted)' }}>Менеджер</span>
            <select
              value={managerId}
              onChange={(e) => setManagerId(e.target.value ? Number(e.target.value) : '')}
              className="w-full rounded-lg px-3 py-2.5 text-sm outline-none"
              style={{ background: 'var(--color-surface)', border: '1px solid var(--color-border)', color: 'var(--color-text)' }}
            >
              <option value="">Я ({user?.full_name || user?.login})</option>
              {assignableManagers?.filter((u) => u.id !== user?.id).map((u) => (
                <option key={u.id} value={u.id}>{u.full_name || u.login}</option>
              ))}
            </select>
          </label>
        ) : (
          <div className="flex items-center justify-between mb-6 text-xs" style={{ color: 'var(--color-muted)' }}>
            <span>Менеджер</span>
            <span style={{ color: 'var(--color-text)' }}>{user?.full_name || user?.login}</span>
          </div>
        )}

        <div className="flex justify-end gap-2">
          <button
            onClick={onClose}
            className="rounded-lg px-4 py-2 text-sm cursor-pointer"
            style={{ background: 'var(--color-surface-3)', color: 'var(--color-text)' }}
          >
            Отмена
          </button>
          <button
            onClick={() => mutation.mutate()}
            disabled={!clientId || mutation.isPending}
            className="rounded-lg px-4 py-2 text-sm font-medium cursor-pointer disabled:opacity-50"
            style={{ background: 'var(--color-primary)', color: '#fff' }}
          >
            {mutation.isPending ? 'Создание...' : 'Сохранить'}
          </button>
        </div>
      </div>
    </div>
  )
}
