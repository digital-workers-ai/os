export class ApiError extends Error {
  status: number
  detail: string

  constructor(status: number, detail: unknown) {
    const text = typeof detail === 'string' ? detail : JSON.stringify(detail)
    super(text)
    this.status = status
    this.detail = text
  }
}

export const asApiError = (e: unknown): ApiError =>
  e instanceof ApiError ? e : new ApiError(0, (e as Error)?.message ?? String(e))

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let res: Response
  try {
    res = await fetch(path, {
      ...init,
      headers: { 'content-type': 'application/json', ...(init?.headers || {}) },
    })
  } catch (e) {
    throw new ApiError(0, `cannot reach the backend: ${(e as Error).message}`)
  }
  const text = await res.text()
  let body: unknown = null
  if (text) {
    try {
      body = JSON.parse(text)
    } catch {
      throw new ApiError(res.status, text.slice(0, 400))
    }
  }
  if (!res.ok) {
    const detail = (body as { detail?: unknown } | null)?.detail ?? res.statusText
    throw new ApiError(res.status, detail)
  }
  return body as T
}

export const get = <T>(path: string) => request<T>(path)

export const post = <T>(path: string, body?: unknown) =>
  request<T>(path, {
    method: 'POST',
    body: body === undefined ? undefined : JSON.stringify(body),
  })

export interface Health {
  status: string
}

export interface SourceRow {
  source: string
  label: string
  category: string
  unlocks: string
  last_attempt: string | null
  last_success: string | null
  last_new_data: string | null
  attempts: number
  detail: string | null
  validation: string
  entities: string[]
  enabled_by_default: boolean
}

export interface ValidationCoverage {
  provider_validated: number
  total: number
  by_status: Record<string, number>
  detail: string
}

export interface SourcesResponse {
  sources: SourceRow[]
  enabled_by_default: string[]
  validation_coverage: ValidationCoverage
}

export interface SyncResult {
  source: string
  ok: boolean
  rows_fetched: number
  rows_written: number
  rows_refused: number
  rows_colliding: number
  pages_read: number
  truncated: boolean
  detail: string | null
}

export interface SyncResponse {
  ok: number
  failed: number
  rows_written: number
  results: SyncResult[]
}

export interface SyncRun {
  id: string
  source: string
  ok: boolean
  rows_written: number
  detail: string | null
  started_at: string
}

export interface SyncRunsResponse {
  total: number
  limit: number
  offset: number
  runs: SyncRun[]
}

export interface MatchRate {
  candidates: number
  matched: number
  edges: number
  match_rate: number | null
}

export interface Quarantine {
  rel: string
  record: string
  detail: string
}

export interface EngineReport {
  totals: Record<string, number>
  counts: Record<string, number>
  skips: Record<string, number>
  records_skipped: Record<string, number>
  clears: Record<string, number>
  dead_paths: string[]
  quarantines: Quarantine[]
  dangling_refs: Record<string, number>
  identity_less: Record<string, number>
  oversized: ({ kind: string } & Record<string, unknown>)[]
  disagreements: Record<string, number>
  match_rates: Record<string, MatchRate>
}

export interface RebuildResponse {
  ok: boolean
  duration_ms: number
  raw_events_read: number
  entities: number
  canonical: number
  facts: number
  links: number
  report: EngineReport
}

export type ReportResponse =
  | { ran: false; detail: string }
  | {
      ran: true
      ok: boolean
      duration_ms: number
      raw_events_read: number
      entities: number
      facts: number
      created_at: string
      report: EngineReport
    }

export const api = {
  health: () => get<Health>('/api/health'),
  sources: () => get<SourcesResponse>('/api/sources'),
  sync: (sources?: string[]) => post<SyncResponse>('/api/sync', sources ? { sources } : {}),
  syncRuns: (source: string, limit: number, offset: number) => {
    const params = new URLSearchParams({ limit: String(limit), offset: String(offset) })
    if (source) params.set('source', source)
    return get<SyncRunsResponse>(`/api/sync/runs?${params}`)
  },
  rebuild: () => post<RebuildResponse>('/api/rebuild'),
  report: () => get<ReportResponse>('/api/report'),
}
