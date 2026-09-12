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

export type Filter = Record<string, string>

type Param = [string, string | undefined]

const filterParams = (filter: Filter = {}): Param[] => Object.entries(filter).map(([attr, value]) => ['filter', `${attr}:${value}`])

const query = (params: Param[]) => {
  const search = new URLSearchParams()
  for (const [key, value] of params) if (value !== undefined) search.append(key, value)
  const text = search.toString()
  return text ? `?${text}` : ''
}

export type Shape = 'kpi' | 'ratio' | 'breakdown' | 'series'

export interface MetricCardSpec {
  metric: string
  label: string
  shape: Shape
}

export type ColumnType = 'string' | 'number' | 'date'

export interface Column {
  attr: string
  type: ColumnType
}

export interface TableCardSpec {
  shape: 'table'
  label: string
  entity: string
  rank: string
  columns: Column[]
  window_attr: string | null
  limit: number
  filter: Filter
}

export type CardSpec = MetricCardSpec | TableCardSpec

export const isTable = (card: CardSpec): card is TableCardSpec => card.shape === 'table'

export interface SectionSpec {
  label: string
  cards: CardSpec[]
}

export interface PageSpec {
  label: string
  range: boolean
  goals: boolean
  findings: boolean
  filter: Filter
  parent: string | null
  sections: SectionSpec[]
}

export interface DashboardsResponse {
  dashboards: Record<string, PageSpec>
}

export const pageAt = (pages: Record<string, PageSpec>, name = '', parent: string | null = null): PageSpec | undefined =>
  pages[name]?.parent === parent ? pages[name] : undefined

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
  applied_filter?: Filter
  previous?: Previous
}

export interface MetricQuery {
  from?: string
  to?: string
  compare?: 'previous'
  filter?: Filter
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

export const getMetric = (name: string, { from, to, compare, filter }: MetricQuery = {}) =>
  get<MetricResponse>(`/api/metrics/${encodeURIComponent(name)}${query([['from', from], ['to', to], ['compare', compare], ...filterParams(filter)])}`)

export const getMetricDefinitions = () => get<MetricDefinitionsResponse>('/api/definitions/metrics')

export interface TopRow {
  canonical_id: string
  values: Record<string, string | null>
}

export interface TopResponse {
  entity: string
  rank: string
  columns: Column[]
  rows: TopRow[]
  entities: number
  window_from?: string
  window_to?: string
}

export interface TopQuery {
  from?: string
  to?: string
  filter?: Filter
}

export const getTop = (spec: TableCardSpec, { from, to, filter }: TopQuery = {}) => {
  const windowed: Param[] = from && to && spec.window_attr ? [['from', from], ['to', to], ['window_attr', spec.window_attr]] : []
  return get<TopResponse>(
    `/api/entities/top${query([
      ['entity', spec.entity],
      ['rank', spec.rank],
      ...spec.columns.map((column): Param => ['columns', column.attr]),
      ['limit', String(spec.limit)],
      ...windowed,
      ...filterParams({ ...filter, ...spec.filter }),
    ])}`,
  )
}

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
