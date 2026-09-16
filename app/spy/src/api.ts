import type { Bounds } from '@/lib/range'

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

const windowParams = (bounds?: Bounds): Param[] => [
  ['from', bounds?.from],
  ['to', bounds?.to],
]

export type Shape = 'kpi' | 'ratio' | 'series'

export interface MetricCardSpec {
  metric: string
  label: string
  shape: Shape
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
  applied_filter?: Filter
  previous?: Previous
}

export interface MetricQuery {
  from?: string
  to?: string
  compare?: 'previous'
  filter?: Filter
}

export const getMetric = (name: string, { from, to, compare, filter }: MetricQuery = {}) =>
  get<MetricResponse>(`/api/metrics/${encodeURIComponent(name)}${query([['from', from], ['to', to], ['compare', compare], ...filterParams(filter)])}`)

export interface Brand {
  name: string
  domain: string
  aliases: string[]
}

export interface Competitor extends Brand {
  linkedin: string | null
  google_advertiser_id: string | null
}

export interface SpyDefinition {
  brand: Brand
  competitors: Competitor[]
  queries: string[]
  country: string
  language: string
  engines: string[]
}

export const getDefinition = () => get<SpyDefinition>('/api/definitions/spy')

export type Role = 'brand' | 'competitor'

export interface VisibilityCompany {
  name: string
  domain: string
  role: Role
}

export interface VisibilityCheck {
  engine: string
  checked_at: string
  answer: string | null
  sources: number
  canonical_id: string
  mentions: Record<string, number>
}

export interface VisibilityQuery {
  query: string
  checks: VisibilityCheck[]
}

export interface VisibilityResponse {
  as_of: string
  engine: string | null
  window_from: string | null
  window_to: string | null
  companies: VisibilityCompany[]
  checks: number
  queries: VisibilityQuery[]
  share: Record<string, Record<string, number>>
}

export const getVisibility = (engine?: string, bounds?: Bounds) =>
  get<VisibilityResponse>(`/api/spy/visibility${query([['engine', engine], ...windowParams(bounds)])}`)

export interface AdCompany {
  name: string
  ads: number
  new: number
}

export interface Ad {
  canonical_id: string
  company: string
  platform: string
  name: string | null
  category: string
  first_seen: string
  last_seen: string
  url: string
  preview: string | null
}

export interface AdsResponse {
  as_of: string
  companies: AdCompany[]
  ads: Ad[]
}

export const getAds = (platform?: string, bounds?: Bounds) =>
  get<AdsResponse>(`/api/spy/ads${query([['platform', platform], ...windowParams(bounds)])}`)

export interface PostCompany {
  name: string
  posts: number
  likes: number
  comments: number
}

export interface Post {
  canonical_id: string
  company: string
  platform: string
  name: string
  category: string
  posted_at: string
  likes: number
  comments: number
  url: string
}

export interface PostsResponse {
  as_of: string
  companies: PostCompany[]
  total: number
  limit: number
  offset: number
  posts: Post[]
}

export interface PostsQuery {
  company?: string
  limit?: number
  offset?: number
}

export const getPosts = ({ company, limit, offset }: PostsQuery = {}, bounds?: Bounds) =>
  get<PostsResponse>(
    `/api/spy/posts${query([
      ['company', company],
      ['limit', limit === undefined ? undefined : String(limit)],
      ['offset', offset === undefined ? undefined : String(offset)],
      ...windowParams(bounds),
    ])}`,
  )

export interface Source {
  source: string
  label: string
  category: string
  enabled: boolean
  validation: string
  last_success: string | null
}

export interface SourcesResponse {
  sources: Source[]
}

export const getSources = () => get<SourcesResponse>('/api/sources')
