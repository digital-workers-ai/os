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

export const put = <T>(path: string, body?: unknown) =>
  request<T>(path, {
    method: 'PUT',
    body: body === undefined ? undefined : JSON.stringify(body),
  })

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
  enabled: boolean
}

export interface ValidationCoverage {
  provider_validated: number
  total: number
  by_status: Record<string, number>
  detail: string
}

export interface SourcesResponse {
  sources: SourceRow[]
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

export interface RebuildRun {
  seq: number
  ok: boolean
  created_at: string
  duration_ms: number
  raw_events_read: number
  entities: number
  facts: number
  totals: Record<string, number>
  error: string | null
}

export interface RunsResponse {
  runs: RebuildRun[]
}

export interface McpIndex {
  path: string
  tools: { name: string; description: string }[]
  resources: { uri: string; name: string; description: string }[]
  prompts: { name: string; description: string }[]
}

export interface SearchHit {
  kind: string
  id: string
  label: string
  evidence: string
}

export interface SearchResponse {
  q: string
  kind: string | null
  mode: 'words' | 'meaning' | 'both'
  meaning_enabled: boolean
  rerank_enabled: boolean
  reranked: boolean
  total: number
  limit: number
  offset: number
  by_kind: Record<string, number>
  results: SearchHit[]
}

export interface RawEventDetail {
  id: string
  source: string
  object_type: string
  source_id: string
  seq: number
  ingested_at: string
  raw_payload: unknown
}

export const api = {
  sources: () => get<SourcesResponse>('/api/sources'),
  sync: (sources?: string[]) => post<SyncResponse>('/api/sync', sources ? { sources } : {}),
  rebuild: () => post<RebuildResponse>('/api/rebuild'),
}
