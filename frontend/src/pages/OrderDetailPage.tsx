import { useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { fetchOrder, setOrderStatus, updateOrder, deleteOrder, addOrderFile, removeOrderFile, type OrderStatus } from '../api/orders'
import { fetchUsers } from '../api/users'
import { HttpError } from '../api/errors'
import NotesSection from '../components/NotesSection'
import ProductsTable from '../components/ProductsTable'
import PaymentRequestsTab from '../components/PaymentRequestsTab'
import LogisticsTab from '../components/LogisticsTab'
import LedgerTab from '../components/LedgerTab'
import CalculationTab from '../components/CalculationTab'
import { useAuth } from '../contexts/AuthContext'
import ProfitBlock from '../components/ProfitBlock'
import Skeleton from '../components/Skeleton'
import ErrorState from '../components/ErrorState'
import NotFound from '../components/NotFound'
import FileUploader, { type UploadedFile } from '../components/FileUploader'
import Tag, { type TagColor } from '../components/Tag'
import { toast } from '../components/Toast'

const MAX_ORDER_FILES = 5

const STATUS_BADGE: Record<OrderStatus, { label: string; color: TagColor }> = {
  in_progress: { label: 'В работе', color: 'green' },
  completed: { label: 'Завершён', color: 'blue' },
  cancelled: { label: 'Отменён', color: 'red' },
}

type TabKey = 'items' | 'payments' | 'logistics' | 'finance' | 'calculation'

const TABS: { key: TabKey; label: string }[] = [
  { key: 'items', label: 'Товары' },
  { key: 'payments', label: 'Запросы на оплату' },
  { key: 'logistics', label: 'Логистика' },
  { key: 'finance', label: 'ДиР' },
]

// Only a completed order can be calculated, so the tab exists only then.
const COMPLETED_TABS: { key: TabKey; label: string }[] = [...TABS, { key: 'calculation', label: 'Расчёт' }]

export default function OrderDetailPage() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const { user } = useAuth()
  const orderId = Number(id)
  const [activeTab, setActiveTab] = useState<TabKey>('items')
  const [reassigning, setReassigning] = useState(false)
  const [editingDetails, setEditingDetails] = useState(false)
  const [detailsDraft, setDetailsDraft] = useState('')
  const queryClient = useQueryClient()
  const isAdmin = user?.role === 'admin'

  const { data: order, isLoading, isError, error, refetch } = useQuery({
    queryKey: ['order', orderId],
    queryFn: () => fetchOrder(orderId),
    enabled: !Number.isNaN(orderId),
    retry: (failureCount, err) => err instanceof HttpError && err.status === 404 ? false : failureCount < 2,
  })
  const isNotFound = error instanceof HttpError && error.status === 404

  const { data: users } = useQuery({ queryKey: ['users'], queryFn: fetchUsers, enabled: isAdmin && reassigning })
  const assignableManagers = users?.filter((u) => u.role === 'admin' || u.role === 'manager')

  const reassignMutation = useMutation({
    mutationFn: (managerId: number) => updateOrder(orderId, { details: order?.details ?? '', manager_id: managerId }),
    onSuccess: (updated) => {
      queryClient.setQueryData(['order', orderId], updated)
      setReassigning(false)
    },
  })

  const updateDetailsMutation = useMutation({
    mutationFn: (details: string) => updateOrder(orderId, { details }),
    onSuccess: (updated) => {
      queryClient.setQueryData(['order', orderId], updated)
      setEditingDetails(false)
    },
  })

  const deleteMutation = useMutation({
    mutationFn: () => deleteOrder(orderId),
    onSuccess: () => navigate('/'),
  })

  const addFileMutation = useMutation({
    mutationFn: (file: UploadedFile) => addOrderFile(orderId, file.key),
    onSuccess: (updated) => queryClient.setQueryData(['order', orderId], updated),
  })

  const removeFileMutation = useMutation({
    mutationFn: (fileKey: string) => removeOrderFile(orderId, fileKey),
    onSuccess: (updated) => queryClient.setQueryData(['order', orderId], updated),
  })

  function startEditDetails() {
    setDetailsDraft(order?.details ?? '')
    setEditingDetails(true)
  }

  function confirmDelete() {
    if (!order) return
    if (!window.confirm(`Удалить заказ «${order.number}»? Это действие нельзя отменить.`)) return
    deleteMutation.mutate()
  }

  const statusMutation = useMutation({
    mutationFn: (status: OrderStatus) => setOrderStatus(orderId, status),
    onMutate: async (status) => {
      await queryClient.cancelQueries({ queryKey: ['order', orderId] })
      const previous = queryClient.getQueryData<Awaited<ReturnType<typeof fetchOrder>>>(['order', orderId])
      if (previous) {
        queryClient.setQueryData(['order', orderId], { ...previous, status })
      }
      return { previous }
    },
    onError: (err, _status, ctx) => {
      if (ctx?.previous) queryClient.setQueryData(['order', orderId], ctx.previous)
      // A mutation's own onError replaces the app-wide toast, so show it here.
      toast(err instanceof Error ? err.message : 'Не удалось изменить статус заказа', 'error')
    },
    onSuccess: (updated) => {
      queryClient.setQueryData(['order', orderId], updated)
    },
  })

  if (isLoading) {
    return (
      <div className="p-6 flex flex-col gap-4">
        <Skeleton width={140} height={14} />
        <Skeleton width="60%" height={28} />
        <Skeleton width="45%" height={14} />
        <div className="flex gap-3 mt-2">
          <Skeleton width={90} height={32} />
          <Skeleton width={90} height={32} />
          <Skeleton width={90} height={32} />
        </div>
        <Skeleton width="100%" height={180} radius={14} style={{ marginTop: 12 }} />
      </div>
    )
  }

  if (isNotFound || (!isLoading && !order && !isError)) {
    return (
      <div className="p-4 sm:p-6">
        <NotFound
          title="Заказ не найден"
          message="Такого заказа нет, либо у вас нет к нему доступа."
          backTo="/"
          backLabel="← Ко всем заказам"
        />
      </div>
    )
  }

  if (isError || !order) {
    return (
      <div className="p-4 sm:p-6">
        <ErrorState message="Не удалось загрузить заказ" onRetry={() => refetch()} />
        <button onClick={() => navigate('/')} className="mt-3 text-sm cursor-pointer" style={{ color: 'var(--color-primary)' }}>
          ← Назад к заказам
        </button>
      </div>
    )
  }

  const badge = STATUS_BADGE[order.status]
  const date = new Date(order.created_at).toLocaleDateString('ru-RU', { day: '2-digit', month: 'long', year: 'numeric' })
  const isOwnerOrAdmin = !!user && (user.role === 'admin' || (user.role === 'manager' && user.id === order.manager_id))
  // A calculated order is frozen for everyone, admin included, until the calculation is cancelled.
  const frozen = order.is_calculated
  // Completed: goods, payments, logistics, ДиР and files are locked server-side until reverted to work.
  const completed = order.status === 'completed'
  const canEdit = isOwnerOrAdmin && !frozen && !completed
  const tabs = order.status === 'completed' ? COMPLETED_TABS : TABS
  const currentTab = tabs.some((tab) => tab.key === activeTab) ? activeTab : 'items'

  return (
    <div className="p-4 sm:p-6">
      <button onClick={() => navigate('/')} className="text-sm mb-4 cursor-pointer" style={{ color: 'var(--color-primary)' }}>
        ← Назад к заказам
      </button>

      <div className="flex items-center justify-between gap-3 flex-wrap mb-2">
        <div className="flex items-center gap-3 min-w-0">
          <span className="text-xs flex-shrink-0" style={{ color: 'var(--color-faint)' }}>№{order.id}</span>
          <h1 className="text-xl sm:text-2xl font-bold truncate" style={{ color: 'var(--color-text)' }}>{order.number}</h1>
        </div>
        <div className="flex items-center gap-3 flex-shrink-0">
          <Tag color={badge.color}>{badge.label}</Tag>
          {frozen && <Tag color="green">Рассчитан</Tag>}
          {isAdmin && !frozen && (
            <button
              onClick={confirmDelete}
              disabled={deleteMutation.isPending}
              className="text-xs font-medium cursor-pointer disabled:opacity-50"
              style={{ color: 'var(--color-danger)' }}
              title="Удалить заказ"
            >
              {deleteMutation.isPending ? 'Удаление...' : 'Удалить заказ'}
            </button>
          )}
        </div>
      </div>

      <div className="flex items-center gap-3 text-sm flex-wrap mb-6" style={{ color: 'var(--color-muted)' }}>
        <span>{order.client_name}</span>
        <span>·</span>
        {reassigning ? (
          <select
            autoFocus
            defaultValue=""
            disabled={reassignMutation.isPending}
            onChange={(e) => e.target.value && reassignMutation.mutate(Number(e.target.value))}
            onBlur={() => setReassigning(false)}
            className="text-sm outline-none px-2 py-1"
            style={{ background: 'var(--color-surface)', border: '1px solid var(--color-border)', borderRadius: 'var(--radius)', color: 'var(--color-text)' }}
          >
            <option value="" disabled>{order.manager_name}</option>
            {assignableManagers?.filter((u) => u.id !== order.manager_id).map((u) => (
              <option key={u.id} value={u.id}>{u.full_name || u.login}</option>
            ))}
          </select>
        ) : (
          <span>
            {order.manager_name}
            {isAdmin && !frozen && (
              <button
                onClick={() => setReassigning(true)}
                className="ml-1.5 text-xs cursor-pointer underline"
                style={{ color: 'var(--color-primary)' }}
              >
                изменить
              </button>
            )}
          </span>
        )}
        <span>·</span>
        <span>{date}</span>
        <span>·</span>
        <span>{order.currency}</span>
      </div>

      {frozen && (
        <div
          className="rounded-[8px] px-4 py-3 mb-4 text-sm flex items-center justify-between gap-3 flex-wrap"
          style={{ background: 'var(--color-info-bg)', color: 'var(--color-info)', border: '1px solid var(--color-border)' }}
        >
          <span>
            Заказ рассчитан и заморожен — изменения недоступны никому. Чтобы что-то изменить, администратор должен
            отменить расчёт.
          </span>
          {currentTab !== 'calculation' && (
            <button
              onClick={() => setActiveTab('calculation')}
              className="text-xs font-medium underline cursor-pointer"
              style={{ color: 'var(--color-info)' }}
            >
              Открыть расчёт
            </button>
          )}
        </div>
      )}

      {completed && !frozen && (
        <div
          className="rounded-[8px] px-4 py-3 mb-4 text-sm"
          style={{ background: 'var(--color-surface-2)', color: 'var(--color-muted)', border: '1px solid var(--color-border)' }}
        >
          Заказ завершён — товары, оплаты, логистика, ДиР и файлы закрыты для изменений. Чтобы что-то изменить,
          {isAdmin ? ' верните заказ в работу кнопкой ниже.' : ' попросите администратора вернуть заказ в работу.'}
        </div>
      )}

      {/* Status actions */}
      {user && user.role !== 'observer' && !frozen && (() => {
        const isAdmin = user.role === 'admin'
        const isOwner = user.role === 'manager' && user.id === order.manager_id
        const busy = statusMutation.isPending
        const actions: { label: string; status: OrderStatus; style: 'danger' | 'success' | 'ghost' }[] = []

        if (order.status === 'in_progress') {
          if (isAdmin) actions.push({ label: 'Завершить', status: 'completed', style: 'success' })
          if (isAdmin || isOwner) actions.push({ label: 'Отменить', status: 'cancelled', style: 'danger' })
        }
        if (order.status === 'cancelled' && isAdmin) {
          actions.push({ label: 'Вернуть в работу', status: 'in_progress', style: 'ghost' })
        }
        if (order.status === 'completed' && isAdmin) {
          actions.push({ label: 'Вернуть в работу', status: 'in_progress', style: 'ghost' })
        }

        if (actions.length === 0) return null
        return (
          <div className="flex items-center gap-2 flex-wrap mb-4">
            {actions.map((a) => (
              <button
                key={a.status}
                disabled={busy}
                onClick={() => statusMutation.mutate(a.status)}
                className="text-xs font-medium px-3 py-1.5 rounded-lg cursor-pointer transition-opacity disabled:opacity-50"
                style={{
                  background: a.style === 'success' ? 'var(--color-success-bg)' : a.style === 'danger' ? 'var(--color-danger-bg)' : 'var(--color-surface-2)',
                  color: a.style === 'success' ? 'var(--color-success)' : a.style === 'danger' ? 'var(--color-danger)' : 'var(--color-muted)',
                  border: '1px solid transparent',
                }}
              >
                {a.label}
              </button>
            ))}
          </div>
        )
      })()}

      {isAdmin && !frozen ? (
        editingDetails ? (
          <div
            className="rounded-[8px] p-4 mb-6"
            style={{ background: 'var(--color-surface)', border: '1px solid var(--color-border)' }}
          >
            <textarea
              autoFocus
              value={detailsDraft}
              onChange={(e) => setDetailsDraft(e.target.value)}
              rows={3}
              className="w-full text-sm outline-none resize-none mb-3"
              style={{ background: 'transparent', color: 'var(--color-text)' }}
            />
            <div className="flex justify-end gap-2">
              <button
                onClick={() => setEditingDetails(false)}
                className="text-xs cursor-pointer px-3 py-1.5 rounded-lg"
                style={{ background: 'var(--color-surface-2)', color: 'var(--color-muted)' }}
              >
                Отмена
              </button>
              <button
                onClick={() => updateDetailsMutation.mutate(detailsDraft)}
                disabled={updateDetailsMutation.isPending}
                className="text-xs font-medium cursor-pointer px-3 py-1.5 rounded-lg disabled:opacity-50"
                style={{ background: 'var(--color-primary)', color: '#fff' }}
              >
                {updateDetailsMutation.isPending ? 'Сохранение...' : 'Сохранить'}
              </button>
            </div>
          </div>
        ) : (
          <div
            onClick={startEditDetails}
            className="rounded-[8px] p-4 text-sm mb-6 cursor-pointer"
            style={{ background: 'var(--color-surface)', border: '1px solid var(--color-border)', color: order.details ? 'var(--color-text)' : 'var(--color-faint)' }}
            title="Нажмите, чтобы изменить"
          >
            {order.details || 'Добавить детали заказа...'}
            <span className="ml-1.5 text-xs underline" style={{ color: 'var(--color-primary)' }}>изменить</span>
          </div>
        )
      ) : (
        order.details && (
          <div
            className="rounded-[8px] p-4 text-sm mb-6"
            style={{ background: 'var(--color-surface)', border: '1px solid var(--color-border)', color: 'var(--color-text)' }}
          >
            {order.details}
          </div>
        )
      )}

      {isOwnerOrAdmin && (canEdit || order.file_keys.length > 0) && (
        <div className="mb-6">
          <div className="text-sm font-semibold mb-2" style={{ color: 'var(--color-text)' }}>
            Файлы заказа
          </div>
          <FileUploader
            files={order.file_keys.map((key) => ({ key, filename: key, size: 0 }))}
            context="order"
            readOnly={!canEdit}
            disabled={order.file_keys.length >= MAX_ORDER_FILES || addFileMutation.isPending}
            onUpload={(file) => addFileMutation.mutate(file)}
            onRemove={(key) => removeFileMutation.mutate(key)}
          />
        </div>
      )}

      <ProfitBlock orderId={orderId} />

      <div className="flex gap-1 overflow-x-auto mb-5" style={{ borderBottom: '1px solid var(--color-border)' }}>
        {tabs.map((tab) => (
          <button
            key={tab.key}
            onClick={() => setActiveTab(tab.key)}
            className="px-4 py-3 text-sm font-medium cursor-pointer whitespace-nowrap transition-colors"
            style={{
              color: currentTab === tab.key ? 'var(--color-primary)' : 'var(--color-muted)',
              borderBottom: currentTab === tab.key ? '2px solid var(--color-primary)' : '2px solid transparent',
              marginBottom: -1,
            }}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {currentTab === 'items' && <ProductsTable orderId={order.id} orderCurrency={order.currency} canEdit={canEdit} />}
      {currentTab === 'payments' && (
        <PaymentRequestsTab orderId={order.id} clientId={order.client_id} canEdit={canEdit} />
      )}
      {currentTab === 'logistics' && (
        <LogisticsTab
          orderId={order.id}
          orderNumber={order.number}
          canEdit={canEdit}
          canNotify={isOwnerOrAdmin}
          isAdmin={user?.role === 'admin'}
          orderCurrency={order.currency}
          readOnly={frozen}
        />
      )}
      {currentTab === 'finance' && <LedgerTab orderId={order.id} canEdit={canEdit} orderCurrency={order.currency} />}
      {currentTab === 'calculation' && (
        <CalculationTab orderId={order.id} orderNumber={order.number} isAdmin={isAdmin} />
      )}

      <NotesSection orderId={order.id} readOnly={frozen} />
    </div>
  )
}
