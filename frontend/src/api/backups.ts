import { extractErrorMessage } from './errors'

export type BackupKind = 'hourly' | 'daily' | 'manual'
export type BackupStatus = 'running' | 'ok' | 'failed'

export interface BackupRun {
  id: number
  kind: BackupKind
  label: string
  /** Имя копии, а если его не задавали — имя файла. */
  title: string
  /** Постоянная копия: суточные и все ручные. */
  permanent: boolean
  status: BackupStatus
  object_key: string
  size: number
  sha256: string
  /** Сколько S3-хранилищ подтвердили копию (0–2). */
  copies: number
  primary_state: string
  mirror_state: string
  stored_locally: boolean
  started_at: string
  finished_at: string | null
  duration_ms: number
  error: string
  node: string
  verified_at: string | null
  verify_status: BackupStatus | null
  verify_detail: string
  restored_at: string | null
  restore_status: BackupStatus | null
  restore_detail: string
  /** Когда временную копию удалит автоматика. У постоянных — null. */
  expires_at: string | null
}

export interface BackupBrief {
  id: number
  at: string
  size: number
  copies: number
  object_key: string
}

export interface BackupSummary {
  enabled: boolean
  retention_days: number
  storage: string
  hourly: BackupBrief | null
  daily: BackupBrief | null
  manual: BackupBrief | null
  verify: { at: string; status: BackupStatus | null; detail: string } | null
}

export interface BackupList {
  summary: BackupSummary
  items: BackupRun[]
}

export async function fetchBackups(): Promise<BackupList> {
  const res = await fetch('/api/backups/', { credentials: 'include' })
  if (!res.ok) throw new Error('Не удалось загрузить список бэкапов')
  return res.json()
}

export async function createBackup(name: string): Promise<{ status: string }> {
  const res = await fetch('/api/backups/', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    credentials: 'include',
    body: JSON.stringify({ name }),
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error(extractErrorMessage(err, 'Не удалось запустить создание копии'))
  }
  return res.json()
}

export async function deleteBackup(id: number): Promise<{ status: string }> {
  const res = await fetch(`/api/backups/${id}`, { method: 'DELETE', credentials: 'include' })
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error(extractErrorMessage(err, 'Не удалось удалить копию'))
  }
  return res.json()
}

export async function restoreBackup(id: number): Promise<{ status: string }> {
  const res = await fetch(`/api/backups/${id}/restore`, { method: 'POST', credentials: 'include' })
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error(extractErrorMessage(err, 'Не удалось запустить откат'))
  }
  return res.json()
}
