export interface LogSource {
  name: string
  container: string
  state: string
  image: string
}

export interface LogLine {
  ts: string | null
  level: string
  text: string
}

export interface LogSourcesResponse {
  items: LogSource[]
  available: boolean
  detail?: string
  levels?: string[]
}

export interface ProcessLogsResponse {
  source: string
  lines: LogLine[]
  count: number
  truncated: boolean
}

export interface ProcessLogsQuery {
  source: string
  since?: string
  until?: string
  level?: string[]
  q?: string
  tail?: number
}

export async function fetchLogSources(): Promise<LogSourcesResponse> {
  const res = await fetch('/api/process-logs/sources', { credentials: 'include' })
  if (!res.ok) throw new Error('Failed to fetch log sources')
  return res.json()
}

export async function fetchProcessLogs(params: ProcessLogsQuery): Promise<ProcessLogsResponse> {
  const search = new URLSearchParams()
  search.set('source', params.source)
  if (params.since) search.set('since', params.since)
  if (params.until) search.set('until', params.until)
  if (params.q) search.set('q', params.q)
  if (params.tail) search.set('tail', String(params.tail))
  for (const lvl of params.level ?? []) search.append('level', lvl)

  const res = await fetch(`/api/process-logs/?${search.toString()}`, { credentials: 'include' })
  if (!res.ok) throw new Error('Failed to fetch process logs')
  return res.json()
}
