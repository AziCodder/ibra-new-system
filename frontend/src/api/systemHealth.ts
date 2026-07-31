export type HealthStatus = 'ok' | 'warn' | 'down'

export interface HealthService {
  name: string
  label: string
  status: HealthStatus
  latency_ms?: number
  detail?: string
}

export interface HealthProbe {
  name: string
  kind: 'page' | 'api'
  status: HealthStatus
  status_code: number | null
  latency_ms?: number
  detail?: string
}

export interface HealthReport {
  enabled: boolean
  overall: HealthStatus
  services: HealthService[]
  pages: HealthProbe[]
  checked_at: string
}

export async function fetchSystemHealth(): Promise<HealthReport> {
  const res = await fetch('/api/system-health/', { credentials: 'include' })
  if (!res.ok) throw new Error('Failed to fetch system health')
  return res.json()
}
