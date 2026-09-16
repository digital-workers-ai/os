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

export const get = <T>(path: string) => request<T>(path)

export const post = <T>(path: string, body?: unknown) => request<T>(path, 'POST', body)

export const put = <T>(path: string, body?: unknown) => request<T>(path, 'PUT', body)

type Param = [string, string | number | undefined]

const query = (params: Param[]) => {
  const search = new URLSearchParams()
  for (const [key, value] of params) if (value !== undefined) search.append(key, String(value))
  const text = search.toString()
  return text ? `?${text}` : ''
}

const segment = encodeURIComponent

export type Kind = 'post' | 'newsletter' | 'blog' | 'image' | 'carousel'

export type Origin = 'chat' | 'marketer' | 'mcp'

export type RunStatus = 'running' | 'ok' | 'held' | 'failed'

export type SlotState = 'empty' | 'built' | 'skipped'

export interface Slot {
  date: string
  time: string
  name: string
  kind: Kind
  skill: string
  look: string | null
  ratio: string | null
  theme: string
  state: SlotState
  asset_seq: number | null
}

export interface Cadence {
  kind: Kind
  done: number
  planned: number
}

export interface CalendarResponse {
  from: string
  to: string
  slots: Slot[]
  cadence: Cadence[]
}

export interface AgentRun {
  seq: number
  agent: string
  trigger: 'daily' | 'manual'
  read_detail: string
  made: number
  duration_ms: number
  ok: boolean
  error: string | null
  created_at: string
}

export interface SkillRunRow {
  seq: number
  skill: string
  skill_sha: string
  caller: Origin
  asset_seq: number | null
  version: number | null
  stage: string | null
  status: RunStatus
  error: string | null
  model: string | null
  tokens_in: number
  tokens_out: number
  duration_ms: number
  started_at: string
  finished_at: string | null
}

export interface ToolCall {
  id: number
  tool: string
  ok: boolean
  duration_ms: number
  detail: string | null
}

export interface AssetFile {
  path: string
  media_type: string
  bytes: number
  url: string
  text: string | null
}

export interface SkillRun extends SkillRunRow {
  tool_calls: ToolCall[]
  files: AssetFile[]
}

export interface AssetRow {
  seq: number
  name: string
  kind: Kind
  skill: string
  look: string | null
  ratio: string | null
  origin: Origin
  slot_date: string | null
  slot_name: string | null
  status: RunStatus
  version: number
  preview: string | null
  created_at: string
}

export interface AssetVersion {
  version: number
  note: string
  created_at: string
  files: AssetFile[]
}

export interface Claim {
  version: number
  text: string
  source_kind: string
  source_ref: string | null
  verified: boolean
}

export interface Evidence {
  version: number
  kind: string
  ref: string
  detail: string
}

export interface Asset extends AssetRow {
  versions: AssetVersion[]
  claims: Claim[]
  evidence: Evidence[]
  feedback: string | null
  skill_run_seq: number | null
}

export interface AssetsResponse {
  assets: AssetRow[]
  total: number
}

export interface TodayResponse {
  today: string
  last_run: AgentRun | null
  week: Slot[]
  building: SkillRunRow[]
  built_today: AssetRow[]
}

export interface CanvasNode {
  id: string
  asset_seq: number
  version: number
  date: string
  kind: Kind
  label: string
  media_type: string
  url: string | null
  origin: Origin
  skill: string
  look: string | null
  status: RunStatus
}

export interface CanvasResponse {
  nodes: CanvasNode[]
}

export interface ThreadRow {
  seq: number
  title: string
  created_at: string
}

export interface Turn {
  id: number
  role: 'person' | 'studio'
  text: string
  skill_run: SkillRunRow | null
  asset_seq: number | null
  created_at: string
}

export interface Thread {
  seq: number
  title: string
  turns: Turn[]
}

export interface TurnResponse {
  turn: Turn
  reply: Turn
  skill_run: SkillRunRow | null
  asset: AssetRow | null
}

export interface RunResponse {
  skill_run: SkillRunRow
  asset: AssetRow
}

export interface VersionResponse {
  skill_run: SkillRunRow
  version: number
}

export interface SkillRow {
  name: string
  description: string
  makes: Kind
  runs: number
  lessons: number
}

export interface Skill extends Omit<SkillRow, 'lessons'> {
  body: string
  lessons: string[]
  sha: string
}

export interface SkillsResponse {
  skills: SkillRow[]
}

export interface LookSlot {
  name: string
  max: number
}

export interface LookRow {
  name: string
  medium: 'image' | 'carousel'
  ratios: string[]
  slots: LookSlot[] | Record<string, LookSlot[]>
  slides?: { min: number; max: number }
}

export interface Look extends LookRow {
  sample: Record<string, unknown>
  layouts: string
}

export interface LooksResponse {
  looks: LookRow[]
}

export interface BrandTokens {
  logo: string
  colors: Record<string, string>
  fonts: Record<string, string>
}

export interface BrandAsset {
  name: string
  path: string
  media_type: string
  bytes: number
}

export interface BrandFile {
  file: string
  front: Record<string, string>
  body: string
}

export interface BrandResponse {
  files: string[]
  tokens: BrandTokens
  assets: BrandAsset[]
}

export interface AssetFilters {
  kind?: Kind
  look?: string
  origin?: Origin
  q?: string
  limit?: number
  offset?: number
}

export const getToday = () => get<TodayResponse>('/api/studio/today')

export const getCalendar = (from: string, to: string) =>
  get<CalendarResponse>(`/api/studio/calendar${query([['from', from], ['to', to]])}`)

export const fillCalendar = (days = 14) => post<{ agent_run: AgentRun }>('/api/studio/calendar/fill', { days })

export const skipSlot = (day: string, name: string) =>
  post<{ ok: boolean }>(`/api/studio/slots/${segment(day)}/${segment(name)}/skip`)

export const runSlot = (day: string, name: string) =>
  post<RunResponse>(`/api/studio/slots/${segment(day)}/${segment(name)}/run`)

export const getCanvas = (from?: string, to?: string, kind?: Kind) =>
  get<CanvasResponse>(`/api/studio/canvas${query([['from', from], ['to', to], ['kind', kind]])}`)

export const getThreads = () => get<{ threads: ThreadRow[] }>('/api/studio/threads')

export const createThread = () => post<{ thread: ThreadRow }>('/api/studio/threads')

export const getThread = (seq: number) => get<Thread>(`/api/studio/threads/${seq}`)

export const sendTurn = (seq: number, text: string) => post<TurnResponse>(`/api/studio/threads/${seq}`, { text })

export const getAssets = ({ kind, look, origin, q, limit, offset }: AssetFilters = {}) =>
  get<AssetsResponse>(
    `/api/assets${query([['kind', kind], ['look', look], ['origin', origin], ['q', q], ['limit', limit], ['offset', offset]])}`,
  )

export const getAsset = (seq: number) => get<Asset>(`/api/assets/${seq}`)

export const assetFileUrl = (seq: number, version: number, path: string) =>
  `/api/assets/${seq}/versions/${version}/files/${path.split('/').map(segment).join('/')}`

export const editAsset = (seq: number, text: string) => post<VersionResponse>(`/api/assets/${seq}/edit`, { text })

export const resizeAsset = (seq: number, ratio: string) => post<VersionResponse>(`/api/assets/${seq}/resize`, { ratio })

export const sendFeedback = (seq: number, text: string) => post<Asset>(`/api/assets/${seq}/feedback`, { text })

export const getSkills = () => get<SkillsResponse>('/api/skills')

export const getSkill = (name: string) => get<Skill>(`/api/skills/${segment(name)}`)

export const runSkill = (name: string, input: string, look?: string, ratio?: string) =>
  post<RunResponse>(`/api/skills/${segment(name)}/run`, { input, look, ratio })

export const getSkillRuns = (limit: number, skill?: string) =>
  get<{ runs: SkillRunRow[] }>(`/api/skill-runs${query([['limit', limit], ['skill', skill]])}`)

export const getSkillRun = (seq: number) => get<SkillRun>(`/api/skill-runs/${seq}`)

export const getAgentRuns = (limit: number) => get<{ runs: AgentRun[] }>(`/api/agent-runs${query([['limit', limit]])}`)

export const getLooks = () => get<LooksResponse>('/api/looks')

export const getLook = (name: string) => get<Look>(`/api/looks/${segment(name)}`)

export const getBrand = () => get<BrandResponse>('/api/brand')

export const getBrandFile = (name: string) => get<BrandFile>(`/api/brand/${segment(name)}`)
