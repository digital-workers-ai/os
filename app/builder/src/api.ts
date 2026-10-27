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

async function request<T>(path: string, method = 'GET', body?: unknown): Promise<T> {
  let res: Response
  try {
    res = await fetch(path, {
      method,
      headers: { 'content-type': 'application/json' },
      body: body === undefined ? undefined : JSON.stringify(body),
    })
  } catch (e) {
    throw new ApiError(0, `cannot reach the backend: ${(e as Error).message}`)
  }
  const text = await res.text()
  let parsed: unknown = null
  if (text) {
    try {
      parsed = JSON.parse(text)
    } catch {
      throw new ApiError(res.status, text.slice(0, 400))
    }
  }
  if (!res.ok) {
    const detail = (parsed as { detail?: unknown } | null)?.detail ?? res.statusText
    throw new ApiError(res.status, detail)
  }
  return parsed as T
}

const get = <T>(path: string) => request<T>(path)

const post = <T>(path: string, body?: unknown) => request<T>(path, 'POST', body)

const segment = encodeURIComponent

export interface AppSummary {
  name: string
  title: string
  description: string
  input: string[]
  roles: string[]
  lands_as: string
  script: boolean
  screen: boolean
}

export interface Field {
  name: string
  type: string
  description: string
  labels: [string, string][]
  unit: string | null
  entity: string | null
  by: string | null
  from_scan: boolean
  history: boolean
  by_script: boolean
  fields: Field[]
  lands_as: string | null
  file: string | null
}

export interface Part {
  name?: string
  values?: string[]
  lands_as?: string | null
  fields?: Field[]
}

export interface Template {
  kind: 'grid' | 'checklist'
  rows: Part | null
  columns: Part | null
  cells: Part | null
  sections: Record<string, string[]> | null
  items: Part | null
}

export interface AppDefinition extends AppSummary {
  fields: Field[]
  template: Template | null
}

export interface Suggestion {
  app: string | null
  title: string
  reason: string
}

export interface Turn {
  role: 'person' | 'builder'
  text: string
  questions: string[]
  suggestions: Suggestion[]
  draft: string | null
  problems: string[]
}

export interface Issue {
  number: number
  url: string
}

export interface ThreadRow {
  id: string
  app: string | null
  title: string | null
  created_at: string
  issue: Issue | null
}

export interface Thread extends ThreadRow {
  turns: Turn[]
}

export interface Sample {
  name: string
  media_type: string
  data: string
}

export interface Reading {
  fields: Record<string, unknown>
  missing: string[]
  template?: Record<string, unknown>
}

const thread = (id: string) => `/api/builder/threads/${segment(id)}`

export const getApps = () => get<AppSummary[]>('/api/custom/apps')

export const getApp = (app: string) => get<AppDefinition>(`/api/custom/apps/${segment(app)}`)

export const getYaml = (app: string) => get<{ yaml: string }>(`/api/builder/apps/${segment(app)}/yaml`)

export const getThreads = () => get<ThreadRow[]>('/api/builder/threads')

export const createThread = (app?: string) => post<Thread>('/api/builder/threads', { app })

export const getThread = (id: string) => get<Thread>(thread(id))

export const sendTurn = (id: string, text: string) => post<{ turn: Turn; reply: Turn }>(`${thread(id)}/turns`, { text })

export const tryDraft = (id: string, files: Sample[], text: string | null) => post<Reading>(`${thread(id)}/try`, { files, text })

export const submitThread = (id: string) => post<Issue>(`${thread(id)}/submit`)
