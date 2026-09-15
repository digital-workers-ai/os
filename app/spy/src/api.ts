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

export interface Source {
  source: string
  ok: boolean | null
  last_sync: string | null
}

export type Platform = 'meta' | 'google'

interface AdFields {
  id: string
  competitor: string
  text: string
  format: string | null
  first_seen: string | null
  days_running: number | null
  url: string
}

export type Ad = AdFields & ({ running: true; last_seen: null } | { running: false; last_seen: string })

export interface AdsResponse {
  source: Source
  total: number
  running: number
  rows: Ad[]
}

export interface Domain {
  domain: string
  name: string
}

export interface Keyword {
  keyword: string
  positions: Record<string, number | null>
}

export interface RankingsResponse {
  source: Source
  engine: string
  checked_on: string | null
  us: string
  domains: Domain[]
  keywords: Keyword[]
}

export interface Prompt {
  prompt: string
  named: Record<string, string[]>
}

export interface Brand {
  brand: string
  named: number
  asked: number
  rate: number
}

export interface AnswersResponse {
  source: Source
  checked_on: string | null
  engines: string[]
  prompts: Prompt[]
  brands: Brand[]
}

export interface PageRow {
  competitor: string
  title: string
  url: string
  words: number | null
  sha: string | null
  fetched_on: string | null
}

export interface PagesResponse {
  source: Source
  total: number
  rows: PageRow[]
}

export interface Post {
  competitor: string
  text: string
  posted_at: string | null
  likes: number | null
  comments: number | null
  shares: number | null
  url: string
}

export interface PostsResponse {
  source: Source
  total: number
  rows: Post[]
}

export const getAds = (platform: Platform) => get<AdsResponse>(`/api/competitors/ads?platform=${platform}`)

export const getRankings = () => get<RankingsResponse>('/api/competitors/rankings')

export const getAnswers = () => get<AnswersResponse>('/api/competitors/answers')

export const getPages = () => get<PagesResponse>('/api/competitors/pages')

export const getPosts = () => get<PostsResponse>('/api/competitors/posts')
