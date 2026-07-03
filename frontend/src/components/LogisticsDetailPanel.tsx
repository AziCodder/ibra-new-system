import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  deleteLogistics,
  updateLogistics,
  acceptLogistics,
  unacceptLogistics,
  notifyLogisticsReceived,
  fetchLogisticsComments,
  createLogisticsComment,
  type Logistics,
  type LogisticsStatus,
} from '../api/logistics'
import FileUploader, { type UploadedFile } from './FileUploader'

const CURRENCIES = ['USD', 'EUR', 'CNY', 'RUB']

const STATUS_LABELS: Record<LogisticsStatus, string> = {
  in_transit: 'В дороге',
  accepted: 'Принят',
  cancelled: 'Отменён',
}

const STATUS_BADGE: Record<LogisticsStatus, { bg: string; color: string }> = {
  in_transit: { bg: 'var(--color-info-bg)', color: 'var(--color-info)' },
  accepted: { bg: 'var(--color-success-bg)', color: 'var(--color-success)' },
  cancelled: { bg: 'var(--color-danger-bg)', color: 'var(--color-danger)' },
}

function formatNumber(value: number): string {
  return value.toLocaleString('ru-RU', { maximumFractionDigits: 2 })
}

function formatDate(value: string): string {
  return new Date(value).toLocaleDateString('ru-RU')
}

function SummaryRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex justify-between text-sm py-1.5">
      <span style={{ color: 'var(--color-muted)' }}>{label}</span>
      <span style={{ color: 'var(--color-text)', fontVariantNumeric: 'tabular-nums' }}>{value}</span>
    </div>
  )
}

export default function LogisticsDetailPanel({
  orderId,
  orderNumber,
  logistics,
  canEdit,
  isAdmin,
  onClose,
}: {
  orderId: number
  orderNumber: string
  logistics: Logistics
  canEdit: boolean
  isAdmin: boolean
  onClose: () => void
}) {
  const queryClient = useQueryClient()
  const [error, setError] = useState('')
  const [copied, setCopied] = useState(false)
  const [isEditing, setIsEditing] = useState(false)
  const [isAccepting, setIsAccepting] = useState(false)
  const [commentText, setCommentText] = useState('')

  const [editQuantity, setEditQuantity] = useState(logistics.quantity)
  const [editTracking, setEditTracking] = useState(logistics.tracking)
  const [editShipDate, setEditShipDate] = useState(logistics.ship_date.slice(0, 10))
  const [editDetails, setEditDetails] = useState(logistics.details)
  const [editStatus, setEditStatus] = useState<LogisticsStatus>(logistics.status)
  const [editFile, setEditFile] = useState<UploadedFile | null>(
    logistics.invoice_file_key ? { key: logistics.invoice_file_key, filename: logistics.invoice_file_key, size: 0 } : null
  )

  const [receivedDate, setReceivedDate] = useState(() => new Date().toISOString().slice(0, 10))
  const [expenseAmount, setExpenseAmount] = useState('')
  const [acceptCurrency, setAcceptCurrency] = useState(logistics.currency ?? 'USD')
  const [exchangeRate, setExchangeRate] = useState('1')
  const [acceptNote, setAcceptNote] = useState('')

  const { data: comments, isLoading: commentsLoading } = useQuery({
    queryKey: ['logistics-comments', orderId, logistics.id],
    queryFn: () => fetchLogisticsComments(orderId, logistics.id),
  })

  const updateMutation = useMutation({
    mutationFn: () =>
      updateLogistics(orderId, logistics.id, {
        quantity: Number(editQuantity),
        tracking: editTracking,
        ship_date: new Date(editShipDate).toISOString(),
        invoice_file_key: editFile?.key ?? null,
        details: editDetails,
        status: editStatus,
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['logistics', orderId] })
      queryClient.invalidateQueries({ queryKey: ['all-logistics'] })
      setIsEditing(false)
    },
    onError: (err: Error) => setError(err.message),
  })

  const deleteMutation = useMutation({
    mutationFn: () => deleteLogistics(orderId, logistics.id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['logistics', orderId] })
      queryClient.invalidateQueries({ queryKey: ['all-logistics'] })
      onClose()
    },
    onError: (err: Error) => setError(err.message),
  })

  const acceptMutation = useMutation({
    mutationFn: () =>
      acceptLogistics(orderId, logistics.id, {
        received_date: new Date(receivedDate).toISOString(),
        expense_amount: Number(expenseAmount),
        currency: acceptCurrency,
        exchange_rate: Number(exchangeRate),
        note: acceptNote,
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['logistics', orderId] })
      queryClient.invalidateQueries({ queryKey: ['all-logistics'] })
      setIsAccepting(false)
    },
    onError: (err: Error) => setError(err.message),
  })

  const unacceptMutation = useMutation({
    mutationFn: () => unacceptLogistics(orderId, logistics.id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['logistics', orderId] })
      queryClient.invalidateQueries({ queryKey: ['all-logistics'] })
    },
    onError: (err: Error) => setError(err.message),
  })

  const notifyMutation = useMutation({
    mutationFn: () => notifyLogisticsReceived(orderId, logistics.id),
    onError: (err: Error) => setError(err.message),
  })

  const commentMutation = useMutation({
    mutationFn: () => createLogisticsComment(orderId, logistics.id, commentText),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['logistics-comments', orderId, logistics.id] })
      setCommentText('')
    },
    onError: (err: Error) => setError(err.message),
  })

  function handleDelete() {
    if (window.confirm('Удалить запись логистики?')) {
      deleteMutation.mutate()
    }
  }

  function handleUnaccept() {
    if (window.confirm('Распринять логистику? Данные приёмки будут удалены.')) {
      unacceptMutation.mutate()
    }
  }

  function handleNotify() {
    notifyMutation.mutate()
  }

  async function handleCopy() {
    const lines = [
      `Товар: ${logistics.product_name}`,
      `Дата отправки: ${formatDate(logistics.ship_date)}`,
      `Трекинг: ${logistics.tracking || '—'}`,
      `Примечание: ${logistics.details || '—'}`,
    ]
    try {
      await navigator.clipboard.writeText(lines.join('\n'))
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    } catch {
      setError('Не удалось скопировать')
    }
  }

  const canEditButton = canEdit && (isAdmin || logistics.status === 'in_transit')
  const canDeleteButton = canEdit && logistics.status === 'in_transit'
  const canAccept = isAdmin && logistics.status === 'in_transit'
  const canUnaccept = isAdmin && logistics.status === 'accepted'

  const badge = STATUS_BADGE[logistics.status]

  return (
    <div className="fixed inset-0 z-50" onClick={onClose}>
      <div className="absolute inset-0" style={{ background: 'rgba(0,0,0,0.5)' }} />
      <div
        onClick={(e) => e.stopPropagation()}
        className="absolute right-0 top-0 h-full w-full sm:w-[420px] overflow-y-auto p-6"
        style={{ background: 'var(--color-surface)', borderLeft: '1px solid var(--color-border)' }}
      >
        <div className="flex items-center justify-between mb-5">
          <h3 className="text-base font-semibold" style={{ color: 'var(--color-text)' }}>
            Логистика #{logistics.id}
          </h3>
          <button onClick={onClose} className="text-sm cursor-pointer" style={{ color: 'var(--color-muted)' }}>
            ✕
          </button>
        </div>

        {error && (
          <div
            className="rounded-lg px-3 py-2 mb-4 text-sm"
            style={{ background: 'var(--color-danger-bg)', color: 'var(--color-danger)' }}
          >
            {error}
          </div>
        )}

        {!isEditing && (
          <div className="rounded-xl p-4 mb-4" style={{ background: 'var(--color-surface-2)' }}>
            <div className="flex items-center justify-between mb-2">
              <span className="text-xs font-semibold rounded-full px-2.5 py-1" style={{ background: badge.bg, color: badge.color }}>
                {STATUS_LABELS[logistics.status]}
              </span>
              <span className="text-xs" style={{ color: 'var(--color-muted)' }}>№{orderNumber}</span>
            </div>
            <SummaryRow label="Товар" value={`${logistics.product_name} · ${formatNumber(Number(logistics.quantity))}`} />
            <SummaryRow label="Трекинг" value={logistics.tracking || '—'} />
            <SummaryRow label="Дата отправки" value={formatDate(logistics.ship_date)} />
            {logistics.details && (
              <p className="text-sm mt-1" style={{ color: 'var(--color-text)' }}>{logistics.details}</p>
            )}
            {logistics.invoice_file_key && (
              <a
                href={`/api/files/${logistics.invoice_file_key}`}
                target="_blank"
                rel="noreferrer"
                className="text-sm block mt-2"
                style={{ color: 'var(--color-primary)' }}
              >
                Накладная
              </a>
            )}
          </div>
        )}

        {isEditing && (
          <div className="rounded-xl p-4 mb-4" style={{ background: 'var(--color-surface-2)' }}>
            <div className="text-xs font-semibold uppercase tracking-wide mb-3" style={{ color: 'var(--color-muted)' }}>
              Редактирование
            </div>
            <label className="block mb-3">
              <span className="block text-sm mb-1.5" style={{ color: 'var(--color-muted)' }}>Кол-во</span>
              <input
                type="number"
                min="0.000001"
                step="any"
                value={editQuantity}
                onChange={(e) => setEditQuantity(e.target.value)}
                className="w-full rounded-lg px-3 py-2.5 text-sm outline-none"
                style={{ background: 'var(--color-surface)', border: '1px solid var(--color-border)', color: 'var(--color-text)' }}
              />
            </label>
            <label className="block mb-3">
              <span className="block text-sm mb-1.5" style={{ color: 'var(--color-muted)' }}>Трекинг</span>
              <input
                type="text"
                value={editTracking}
                onChange={(e) => setEditTracking(e.target.value)}
                className="w-full rounded-lg px-3 py-2.5 text-sm outline-none"
                style={{ background: 'var(--color-surface)', border: '1px solid var(--color-border)', color: 'var(--color-text)' }}
              />
            </label>
            <label className="block mb-3">
              <span className="block text-sm mb-1.5" style={{ color: 'var(--color-muted)' }}>Дата отправки</span>
              <input
                type="date"
                value={editShipDate}
                onChange={(e) => setEditShipDate(e.target.value)}
                className="w-full rounded-lg px-3 py-2.5 text-sm outline-none"
                style={{ background: 'var(--color-surface)', border: '1px solid var(--color-border)', color: 'var(--color-text)' }}
              />
            </label>
            <label className="block mb-3">
              <span className="block text-sm mb-1.5" style={{ color: 'var(--color-muted)' }}>Детали</span>
              <textarea
                value={editDetails}
                onChange={(e) => setEditDetails(e.target.value)}
                rows={2}
                className="w-full rounded-lg px-3 py-2.5 text-sm outline-none resize-none"
                style={{ background: 'var(--color-surface)', border: '1px solid var(--color-border)', color: 'var(--color-text)' }}
              />
            </label>
            <label className="block mb-3">
              <span className="block text-sm mb-1.5" style={{ color: 'var(--color-muted)' }}>Статус</span>
              <select
                value={editStatus}
                onChange={(e) => setEditStatus(e.target.value as LogisticsStatus)}
                className="w-full rounded-lg px-3 py-2.5 text-sm outline-none"
                style={{ background: 'var(--color-surface)', border: '1px solid var(--color-border)', color: 'var(--color-text)' }}
              >
                <option value="in_transit">{STATUS_LABELS.in_transit}</option>
                <option value="cancelled">{STATUS_LABELS.cancelled}</option>
              </select>
            </label>
            <div className="mb-4">
              <span className="block text-sm mb-1.5" style={{ color: 'var(--color-muted)' }}>Файл накладной</span>
              <FileUploader
                files={editFile ? [editFile] : []}
                onUpload={(f) => setEditFile(f)}
                onRemove={() => setEditFile(null)}
              />
            </div>
            <div className="flex gap-2">
              <button
                onClick={() => setIsEditing(false)}
                className="flex-1 rounded-lg px-4 py-2 text-sm cursor-pointer"
                style={{ background: 'var(--color-surface-3)', color: 'var(--color-text)' }}
              >
                Отмена
              </button>
              <button
                onClick={() => updateMutation.mutate()}
                disabled={updateMutation.isPending}
                className="flex-1 rounded-lg px-4 py-2 text-sm font-medium cursor-pointer disabled:opacity-50"
                style={{ background: 'var(--color-primary)', color: '#fff' }}
              >
                {updateMutation.isPending ? 'Сохранение...' : 'Сохранить'}
              </button>
            </div>
          </div>
        )}

        {logistics.status === 'accepted' && (
          <div className="rounded-xl p-4 mb-4" style={{ background: 'var(--color-surface-2)' }}>
            <div className="text-xs font-semibold uppercase tracking-wide mb-2" style={{ color: 'var(--color-muted)' }}>
              Приёмка
            </div>
            <SummaryRow label="Дата приёмки" value={logistics.received_date ? formatDate(logistics.received_date) : '—'} />
            <SummaryRow
              label="Расход"
              value={logistics.expense_amount ? `${formatNumber(Number(logistics.expense_amount))} ${logistics.currency}` : '—'}
            />
            <SummaryRow label="Курс" value={logistics.exchange_rate ?? '—'} />
            {logistics.acceptance_note && (
              <p className="text-sm mt-1" style={{ color: 'var(--color-text)' }}>{logistics.acceptance_note}</p>
            )}
          </div>
        )}

        {!isEditing && (
          <div className="flex gap-2 mb-4 flex-wrap">
            {canEditButton && (
              <button
                onClick={() => setIsEditing(true)}
                className="rounded-lg px-4 py-2 text-sm font-medium cursor-pointer"
                style={{ background: 'var(--color-surface-3)', color: 'var(--color-text)' }}
              >
                Редактировать
              </button>
            )}
            <button
              onClick={handleCopy}
              className="rounded-lg px-4 py-2 text-sm font-medium cursor-pointer"
              style={{ background: 'var(--color-surface-3)', color: 'var(--color-text)' }}
            >
              {copied ? 'Скопировано ✓' : 'Копировать'}
            </button>
            {canDeleteButton && (
              <button
                onClick={handleDelete}
                disabled={deleteMutation.isPending}
                className="rounded-lg px-4 py-2 text-sm font-medium cursor-pointer disabled:opacity-50"
                style={{ background: 'var(--color-danger-bg)', color: 'var(--color-danger)' }}
              >
                {deleteMutation.isPending ? 'Удаление...' : 'Удалить'}
              </button>
            )}
          </div>
        )}

        {canEdit && (
          <div className="flex gap-2 mb-4 flex-wrap">
            <button
              onClick={handleNotify}
              disabled={notifyMutation.isPending}
              className="rounded-lg px-4 py-2 text-sm font-medium cursor-pointer disabled:opacity-50"
              style={{ background: 'var(--color-surface-3)', color: 'var(--color-text)' }}
            >
              {notifyMutation.isPending ? 'Отправка...' : notifyMutation.isSuccess ? 'Уведомление отправлено ✓' : 'Уведомить о получении'}
            </button>
            {canAccept && !isAccepting && (
              <button
                onClick={() => setIsAccepting(true)}
                className="rounded-lg px-4 py-2 text-sm font-medium cursor-pointer"
                style={{ background: 'var(--color-primary)', color: '#fff' }}
              >
                Принять
              </button>
            )}
            {canUnaccept && (
              <button
                onClick={handleUnaccept}
                disabled={unacceptMutation.isPending}
                className="rounded-lg px-4 py-2 text-sm font-medium cursor-pointer disabled:opacity-50"
                style={{ background: 'var(--color-surface-3)', color: 'var(--color-text)' }}
              >
                {unacceptMutation.isPending ? 'Распринятие...' : 'Распринять'}
              </button>
            )}
          </div>
        )}

        {isAccepting && (
          <div className="rounded-xl p-4 mb-4" style={{ background: 'var(--color-surface-2)' }}>
            <div className="text-xs font-semibold uppercase tracking-wide mb-3" style={{ color: 'var(--color-muted)' }}>
              Приёмка логистики
            </div>
            <label className="block mb-3">
              <span className="block text-sm mb-1.5" style={{ color: 'var(--color-muted)' }}>Дата получения</span>
              <input
                type="date"
                value={receivedDate}
                onChange={(e) => setReceivedDate(e.target.value)}
                className="w-full rounded-lg px-3 py-2.5 text-sm outline-none"
                style={{ background: 'var(--color-surface)', border: '1px solid var(--color-border)', color: 'var(--color-text)' }}
              />
            </label>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 mb-3">
              <label className="block">
                <span className="block text-sm mb-1.5" style={{ color: 'var(--color-muted)' }}>Сумма</span>
                <input
                  type="number"
                  min="0.000001"
                  step="any"
                  value={expenseAmount}
                  onChange={(e) => setExpenseAmount(e.target.value)}
                  className="w-full rounded-lg px-3 py-2.5 text-sm outline-none"
                  style={{ background: 'var(--color-surface)', border: '1px solid var(--color-border)', color: 'var(--color-text)' }}
                />
              </label>
              <label className="block">
                <span className="block text-sm mb-1.5" style={{ color: 'var(--color-muted)' }}>Валюта</span>
                <select
                  value={acceptCurrency}
                  onChange={(e) => setAcceptCurrency(e.target.value)}
                  className="w-full rounded-lg px-3 py-2.5 text-sm outline-none"
                  style={{ background: 'var(--color-surface)', border: '1px solid var(--color-border)', color: 'var(--color-text)' }}
                >
                  {CURRENCIES.map((c) => <option key={c} value={c}>{c}</option>)}
                </select>
              </label>
            </div>
            <label className="block mb-3">
              <span className="block text-sm mb-1.5" style={{ color: 'var(--color-muted)' }}>Курс (вручную)</span>
              <input
                type="number"
                min="0.000001"
                step="any"
                value={exchangeRate}
                onChange={(e) => setExchangeRate(e.target.value)}
                className="w-full rounded-lg px-3 py-2.5 text-sm outline-none"
                style={{ background: 'var(--color-surface)', border: '1px solid var(--color-border)', color: 'var(--color-text)' }}
              />
            </label>
            <label className="block mb-4">
              <span className="block text-sm mb-1.5" style={{ color: 'var(--color-muted)' }}>Примечание</span>
              <textarea
                value={acceptNote}
                onChange={(e) => setAcceptNote(e.target.value)}
                rows={2}
                className="w-full rounded-lg px-3 py-2.5 text-sm outline-none resize-none"
                style={{ background: 'var(--color-surface)', border: '1px solid var(--color-border)', color: 'var(--color-text)' }}
              />
            </label>
            <div className="flex gap-2">
              <button
                onClick={() => setIsAccepting(false)}
                className="flex-1 rounded-lg px-4 py-2 text-sm cursor-pointer"
                style={{ background: 'var(--color-surface-3)', color: 'var(--color-text)' }}
              >
                Отмена
              </button>
              <button
                onClick={() => acceptMutation.mutate()}
                disabled={!(Number(expenseAmount) > 0 && Number(exchangeRate) > 0 && receivedDate !== '') || acceptMutation.isPending}
                className="flex-1 rounded-lg px-4 py-2 text-sm font-medium cursor-pointer disabled:opacity-50"
                style={{ background: 'var(--color-primary)', color: '#fff' }}
              >
                {acceptMutation.isPending ? 'Сохранение...' : 'Принять'}
              </button>
            </div>
          </div>
        )}

        <div className="rounded-xl p-4" style={{ background: 'var(--color-surface-2)' }}>
          <div className="text-xs font-semibold uppercase tracking-wide mb-2" style={{ color: 'var(--color-muted)' }}>
            Комментарии
          </div>
          {commentsLoading && <div className="text-sm" style={{ color: 'var(--color-muted)' }}>Загрузка...</div>}
          {!commentsLoading && (!comments || comments.length === 0) && (
            <div className="text-sm" style={{ color: 'var(--color-muted)' }}>Комментариев пока нет</div>
          )}
          {!commentsLoading && comments && comments.length > 0 && (
            <ul className="space-y-2 mb-3">
              {comments.map((c) => (
                <li key={c.id} className="text-sm" style={{ borderTop: '1px solid var(--color-border)', paddingTop: 8 }}>
                  <div className="flex justify-between">
                    <span style={{ color: 'var(--color-text)' }}>{c.author_name}</span>
                    <span style={{ color: 'var(--color-muted)' }}>{new Date(c.created_at).toLocaleString('ru-RU')}</span>
                  </div>
                  <div style={{ color: 'var(--color-text)' }}>{c.text}</div>
                </li>
              ))}
            </ul>
          )}
          <div className="flex gap-2 mt-3">
            <input
              type="text"
              value={commentText}
              onChange={(e) => setCommentText(e.target.value)}
              placeholder="Добавить комментарий..."
              className="flex-1 rounded-lg px-3 py-2 text-sm outline-none"
              style={{ background: 'var(--color-surface)', border: '1px solid var(--color-border)', color: 'var(--color-text)' }}
            />
            <button
              onClick={() => commentMutation.mutate()}
              disabled={commentText.trim() === '' || commentMutation.isPending}
              className="rounded-lg px-4 py-2 text-sm font-medium cursor-pointer disabled:opacity-50"
              style={{ background: 'var(--color-primary)', color: '#fff' }}
            >
              Отправить
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}
