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

const put = <T>(path: string, body?: unknown) => request<T>(path, 'PUT', body)

const remove = <T>(path: string) => request<T>(path, 'DELETE')

const segment = encodeURIComponent

export type Input = 'photo' | 'pdf' | 'scan' | 'voice'

export type FieldType = 'text' | 'number' | 'money' | 'date' | 'one_of' | 'many_of' | 'lookup' | 'photo' | 'list' | 'screen'

export interface Field {
  name: string
  type: FieldType
  description: string
  labels: ([string, string] | string)[]
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
  lands_as?: string
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

export interface AppSummary {
  name: string
  title: string
  description: string
  input: Input[]
  roles: string[]
  lands_as: string
  script: boolean
  screen: boolean
}

export interface AppDefinition extends AppSummary {
  fields: Field[]
  template: Template | null
}

export type Values = Record<string, unknown>

export interface TemplateValues {
  rows: Record<string, Values>
  cells: Record<string, Values>
  items: Record<string, Values>
}

export interface RecordFile {
  path: string
  media_type: string
  kind: string
}

export interface Sent {
  name: string
  media_type: string
  data: string
}

export interface Clip {
  media_type: string
  data: string
}

export interface Created {
  id: string
  app: string
  fields: Values
  missing: string[]
  files: RecordFile[]
  transcript: string | null
}

export interface HistoryEntry {
  action: string
  actor: string
  at: string
}

export interface Detail {
  id: string
  app: string
  fields: Values
  files: RecordFile[]
  history: HistoryEntry[]
  counted: boolean
  entity: { type: string; id: string; label: string | null } | null
  removed: boolean
}

export interface Listed {
  id: string
  app: string
  fields: Values
  saved_at: string | null
}

export interface Lookup {
  matches: { value: string; label: string }[]
  history: Listed[]
}

export type Cursor = Record<string, string | number>

export interface Update {
  row?: string | number
  column?: string
  section?: string
  item?: string
  list?: string
  field: string
  value: unknown
}

export interface Heard {
  transcript: string
  updates: Update[]
  cursor: Cursor | null
  readback: string
}

export const getApps = () => get<AppSummary[]>('/api/custom/apps')

export const getApp = (app: string) => get<AppDefinition>(`/api/custom/apps/${segment(app)}`)

export const lookup = (app: string, field: string, q: string) =>
  get<Lookup>(`/api/custom/apps/${segment(app)}/lookup/${segment(field)}?${new URLSearchParams({ q })}`)

export const createRecord = (app: string, body: { files: Sent[]; scan: string | null; audio: Clip | null }) =>
  post<Created>(`/api/custom/apps/${segment(app)}/records`, body)

export const saveRecord = (id: string, fields: Values) => put<Detail>(`/api/custom/records/${segment(id)}`, { fields })

export const hear = (id: string, audio: Clip, cursor: Cursor | null) =>
  post<Heard>(`/api/custom/records/${segment(id)}/hear`, { audio, cursor })

export const attachFile = (id: string, file: Sent) => post<RecordFile>(`/api/custom/records/${segment(id)}/files`, file)

export const getRecords = (app: string) => get<Listed[]>(`/api/custom/records?${new URLSearchParams({ app })}`)

export const getRecord = (id: string) => get<Detail>(`/api/custom/records/${segment(id)}`)

export const removeRecord = (id: string) => remove<{ removed: boolean }>(`/api/custom/records/${segment(id)}`)

export const fileUrl = (id: string, path: string) => `/api/custom/records/${segment(id)}/files/${path.split('/').map(segment).join('/')}`
