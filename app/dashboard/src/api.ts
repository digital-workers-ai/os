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

async function request<T>(path: string): Promise<T> {
  let res: Response
  try {
    res = await fetch(path, { headers: { 'content-type': 'application/json' } })
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

export type Shape = 'kpi' | 'ratio' | 'breakdown' | 'series'

export interface CardSpec {
  metric: string
  label: string
  shape: Shape
}

export interface SectionSpec {
  label: string
  cards: CardSpec[]
}

export interface PageSpec {
  label: string
  range: boolean
  goals: boolean
  findings: boolean
  sections: SectionSpec[]
}

export interface DashboardsResponse {
  dashboards: Record<string, PageSpec>
}

export interface Previous {
  value: number | null
  entities: number
  window_from: string
  window_to: string
}

export interface MetricResponse {
  as_of: string
  metric: string
  label: string
  description?: string
  entity: string
  value: number | null
  entities: number
  population_size?: number
  note?: string
  error?: string
  mixed_currencies?: string[]
  raw_fields: string[]
  attrs: string[]
  group_by?: string
  grain?: string
  breakdown?: Record<string, number | null>
  window_attr?: string
  window_from?: string
  window_to?: string
  window_days?: number
  window_bad_values?: number
  previous?: Previous
}

export type MetricWindow = {
  from: string
  to: string
  compare: 'previous'
}

export interface Term {
  expression: string
  filter?: Record<string, unknown>
}

export interface MetricSpec {
  label: string
  description?: string
  entity: string
  expression?: string
  filter?: Record<string, unknown>
  op?: string
  terms?: Term[]
  group_by?: string
  grain?: string
  window_attr?: string
  window_days?: number
}

export interface Provenance {
  label: string
  raw_fields: string[]
  attrs: string[]
}

export interface MetricDefinitionsResponse {
  definitions: Record<string, MetricSpec>
  provenance: Record<string, Provenance>
}

export const getDashboards = () => get<DashboardsResponse>('/api/definitions/dashboards')

export const getMetric = (name: string, window?: MetricWindow) => {
  const query = window ? `?${new URLSearchParams(window)}` : ''
  return get<MetricResponse>(`/api/metrics/${encodeURIComponent(name)}${query}`)
}

export const getMetricDefinitions = () => get<MetricDefinitionsResponse>('/api/definitions/metrics')

export interface Goal {
  goal: string
  label: string
  metric: string
  target?: number
  strategy?: string
  current: number | null
  met: boolean | null
  progress?: number | null
  entities: number
  trend?: string
}

export interface GoalsResponse {
  goals: Goal[]
  met: number
  missed: number
  unknown: number
}

export type Severity = 'high' | 'medium' | 'low'

export interface Finding {
  rule: string
  label: string
  severity: Severity
  entity_type: string
  canonical_id: string
  anchor: string
  company: string | null
  evidence: Record<string, string>
}

export interface FindingsResponse {
  as_of: string
  rules: number
  findings: Finding[]
  by_severity: Record<Severity, number>
  report: { evaluated: number; unreadable: Record<string, number> }
}

export const getGoals = () => get<GoalsResponse>('/api/insights/goals')

export const getFindings = () => get<FindingsResponse>('/api/insights/rules')
