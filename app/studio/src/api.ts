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
    res = await fetch(path, { headers: { 'content-type': 'application/json' }, ...init })
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
  request<T>(path, { method: 'POST', body: body === undefined ? undefined : JSON.stringify(body) })

export const put = <T>(path: string, body?: unknown) =>
  request<T>(path, { method: 'PUT', body: body === undefined ? undefined : JSON.stringify(body) })

type Param = [string, string | undefined]

const query = (params: Param[]) => {
  const search = new URLSearchParams()
  for (const [key, value] of params) if (value !== undefined && value !== '') search.append(key, value)
  const text = search.toString()
  return text ? `?${text}` : ''
}

export type Kind = 'post' | 'newsletter' | 'blog' | 'image' | 'video' | 'ad'
export type Mode = 'draft' | 'build' | 'chat'
export type ProposalStatus = 'open' | 'approved' | 'rejected' | 'built'
export type RunStatus = 'running' | 'ok' | 'failed'
export type SlotState = 'empty' | 'proposed' | 'approved' | 'built' | 'skipped'

export interface DraftFile {
  path: string
  media_type: string
  bytes: number
}

export interface Evidence {
  kind: string
  ref: string
  detail: string
}

export interface Claim {
  text: string
  source_kind: string
  source_ref: string | null
  verified: boolean
}

export interface ProposalRow {
  seq: number
  kind: Kind
  title: string
  slot_date: string | null
  slot_name: string | null
  reactive: boolean
  skill: string
  skill_sha: string
  status: ProposalStatus
  created_at: string
  claims_verified: number
  claims_total: number
  evidence_summary: string
}

export interface Proposal extends ProposalRow {
  reason: string | null
  note: string | null
  decided_at: string | null
  look: string | null
  ancestor_ref: string | null
  drafts: DraftFile[]
  evidence: Evidence[]
  claims: Claim[]
  read: string[]
  theme: string | null
  build_cost: string | null
  asset_seq: number | null
  skill_run_seq: number | null
}

export interface ProposalsResponse {
  proposals: ProposalRow[]
  counts: Record<ProposalStatus, number>
}

export interface Slot {
  date: string
  name: string
  kind: Kind
  look: string | null
  theme: string | null
  reactive: boolean
  state: SlotState
  proposal_seq: number | null
  reason: string | null
  spec: string[]
}

export interface CalendarResponse {
  from: string
  to: string
  slots: Slot[]
  cadence: { kind: Kind; done: number; planned: number }[]
}

export interface AgentRunRow {
  seq: number
  agent: 'marketer' | 'taste'
  trigger: string
  read_detail: string
  proposed: number
  duration_ms: number
  cost_usd: number
  ok: boolean
  error: string | null
  created_at: string
}

export interface SkillRunRow {
  seq: number
  skill: string
  mode: Mode
  caller: string
  proposal_seq: number | null
  asset_seq: number | null
  stage: string | null
  status: RunStatus
  error: string | null
  duration_ms: number
  cost_usd: number
  started_at: string
  finished_at: string | null
}

export interface ToolCall {
  tool: string
  ok: boolean
  duration_ms: number
  detail: string | null
}

export interface SkillRun extends SkillRunRow {
  skill_sha: string
  stages: { name: string; state: 'done' | 'running' | 'waiting'; detail: string | null }[]
  tool_calls: ToolCall[]
  files: DraftFile[]
}

export interface TodayResponse {
  today: string
  last_run: AgentRunRow | null
  open: ProposalRow[]
  week: Slot[]
  noticed: { text: string; proposal_seq: number | null }[]
  building: SkillRunRow[]
  built_today: { seq: number; name: string; kind: Kind }[]
  skill_proposals: { skill: string; line: string; proposal_refs: number[]; url: string }[]
}

export interface AssetRow {
  seq: number
  name: string
  kind: Kind
  look: string | null
  origin: 'proposal' | 'chat'
  proposal_seq: number | null
  status: 'building' | 'built'
  created_at: string
  preview: string | null
}

export interface AssetVersion {
  version: number
  note: string | null
  created_at: string
  files: DraftFile[]
}

export interface Asset extends AssetRow {
  ancestor_ref: string | null
  skill: string
  skill_sha: string
  read: string[]
  claims: Claim[]
  versions: AssetVersion[]
  feedback: string | null
  skill_run_seq: number | null
}

export interface AssetsResponse {
  assets: AssetRow[]
  total: number
}

export interface CanvasNode {
  id: string
  group: string
  date: string
  kind: string
  label: string
  media_type: string
  url: string | null
  asset_seq: number | null
  proposal_seq: number | null
}

export interface CanvasEdge {
  from: string
  to: string
  rel: 'ancestor' | 'draft' | 'build'
}

export interface CanvasResponse {
  nodes: CanvasNode[]
  edges: CanvasEdge[]
  frames: { id: string; label: string; nodes: string[] }[]
  layout: Record<string, { x: number; y: number }>
}

export interface SwipeRow {
  id: string
  competitor: string
  platform: string
  format: string
  days_running: number
  first_seen: string
  last_seen: string | null
  running: boolean
  headline: string
  body: string
  angle: string | null
  hook: string | null
  offer: string | null
  proof: string | null
  url: string
}

export interface SwipeLabel {
  field: string
  label: string
  quote: string | null
}

export interface SwipeItem extends SwipeRow {
  labels: SwipeLabel[]
  raw_events: number
  landing_url: string | null
  counter: string | null
}

export interface SwipeResponse {
  items: SwipeRow[]
  total: number
  facets: Record<string, string[]>
}

export interface CompetitorRow {
  slug: string
  name: string
  domain: string
  sources: { source: string; ok: boolean; last_sync: string | null; rows: number }[]
}

export interface CompetitorsResponse {
  us: { name: string; domain: string }
  competitors: CompetitorRow[]
}

export interface AdsResponse {
  active: number
  new_7d: number
  long_running: number
  by_competitor: { competitor: string; active: number; long_running: number; platforms: Record<string, number> }[]
  angle_mix: Record<string, number>
  new_per_week: { week: string; count: number }[]
}

export interface RankingsResponse {
  engine: string
  location: string
  keywords: {
    keyword: string
    positions: Record<string, number | null>
    history: { date: string; position: number | null }[]
  }[]
  domains: string[]
}

export interface AnswersResponse {
  engines: string[]
  prompts: { prompt: string; named: Record<string, Record<string, boolean>> }[]
  mention_rate: Record<string, number>
  cited: { url: string; count: number }[]
}

export interface ContentResponse {
  pages: number
  posts: number
  changes: { competitor: string; url: string; on: string; before: string; after: string }[]
  recent_posts: { competitor: string; text: string; posted_at: string; likes: number; url: string }[]
}

export interface BrandFile {
  name: string
  title: string
  updated: string
  used_by: string[]
  reads: number
  pending_pr: boolean
}

export interface BrandResponse {
  files: BrandFile[]
}

export interface SkillRow {
  name: string
  description: string
  modes: Mode[]
  runs: number
  approval_rate: number | null
  median_edits: number | null
  cost_per_build: number | null
  proposed_lesson: { line: string; evidence: number[]; url: string } | null
}

export interface SkillsResponse {
  skills: SkillRow[]
}

export interface Skill extends SkillRow {
  body: string
  lessons: string[]
  sha: string
}

export interface LookRow {
  name: string
  medium: 'video' | 'image'
  ratio: string
  voice_confirmed: boolean | null
  scenes: string[]
  limits_measured: string | null
  used_by: number
  built: number
  build_cost: string | null
}

export interface LooksResponse {
  looks: LookRow[]
}

export interface McpResponse {
  endpoint: string
  tools: { name: string; group: 'context' | 'skill'; description: string }[]
  calls_7d: number
  recent: { name: string; client: string; detail: string; at: string }[]
  config: Record<string, unknown>
}

export interface SourceRow {
  source: string
  label: string
  ok: boolean
  last_sync: string | null
  rows: number
  detail: string
  error: string | null
}

export interface StudioSourcesResponse {
  competitor_sources: SourceRow[]
  estate_sources: number
}

const encode = encodeURIComponent

export const getToday = () => get<TodayResponse>('/api/studio/today')

export const getCalendar = (from: string, to: string) =>
  get<CalendarResponse>(`/api/studio/calendar${query([['from', from], ['to', to]])}`)

export const fillCalendar = (days: number) => post<{ agent_run: number }>('/api/studio/calendar/fill', { days })

export const skipSlot = (date: string, name: string) =>
  post<{ ok: boolean }>(`/api/studio/slots/${encode(date)}/${encode(name)}/skip`)

export const getProposals = (status?: string, kind?: string) =>
  get<ProposalsResponse>(`/api/studio/proposals${query([['status', status], ['kind', kind]])}`)

export const getProposal = (seq: number) => get<Proposal>(`/api/studio/proposals/${seq}`)

export const editDraft = (seq: number, path: string, text: string) =>
  put<Proposal>(`/api/studio/proposals/${seq}/draft`, { path, text })

export const approveProposal = (seq: number) =>
  post<{ skill_run: number }>(`/api/studio/proposals/${seq}/approve`)

export const rejectProposal = (seq: number, reason: string) =>
  post<Proposal>(`/api/studio/proposals/${seq}/reject`, { reason })

export const redoProposal = (seq: number, note: string) =>
  post<{ skill_run: number }>(`/api/studio/proposals/${seq}/redo`, { note })

export const getCanvas = (from?: string, to?: string, kind?: string, skill?: string) =>
  get<CanvasResponse>(`/api/studio/canvas${query([['from', from], ['to', to], ['kind', kind], ['skill', skill]])}`)

export const saveLayout = (layout: Record<string, { x: number; y: number }>) =>
  put<{ ok: boolean }>('/api/studio/canvas/layout', { layout })

export const getAssets = (kind?: string, look?: string, origin?: string, q?: string) =>
  get<AssetsResponse>(`/api/assets${query([['kind', kind], ['look', look], ['origin', origin], ['q', q]])}`)

export const getAsset = (seq: number) => get<Asset>(`/api/assets/${seq}`)

export const assetFileUrl = (seq: number, path: string) => `/api/assets/${seq}/files/${path}`

export const rebuildAsset = (seq: number, note: string) =>
  post<{ skill_run: number }>(`/api/assets/${seq}/rebuild`, { note })

export const sendFeedback = (seq: number, text: string) =>
  post<Asset>(`/api/assets/${seq}/feedback`, { text })

export const getCompetitors = () => get<CompetitorsResponse>('/api/competitors')

export const getSwipe = (filters: Record<string, string | undefined> = {}) =>
  get<SwipeResponse>(`/api/competitors/swipe${query(Object.entries(filters) as Param[])}`)

export const getSwipeItem = (id: string) => get<SwipeItem>(`/api/competitors/swipe/${encode(id)}`)

export const remixSwipeItem = (
  id: string,
  body: { kind: Kind; look: string | null; slot: string | null; keep: string[] },
) => post<{ proposal: number }>(`/api/competitors/swipe/${encode(id)}/remix`, body)

export const getAds = (competitor?: string, platform?: string) =>
  get<AdsResponse>(`/api/competitors/ads${query([['competitor', competitor], ['platform', platform]])}`)

export const getRankings = (keyword?: string) =>
  get<RankingsResponse>(`/api/competitors/rankings${query([['keyword', keyword]])}`)

export const getAnswers = (prompt?: string) =>
  get<AnswersResponse>(`/api/competitors/answers${query([['prompt', prompt]])}`)

export const getContent = () => get<ContentResponse>('/api/competitors/content')

export const getBrand = () => get<BrandResponse>('/api/brand')

export const getBrandFile = (name: string) =>
  get<{ name: string; title: string; updated: string; body: string; used_by: string[]; reads: number }>(
    `/api/brand/${encode(name)}`,
  )

export const getSkills = () => get<SkillsResponse>('/api/skills')

export const getSkill = (name: string) => get<Skill>(`/api/skills/${encode(name)}`)

export const runSkill = (name: string, body: { mode: Mode; input: string; look?: string; slot?: string }) =>
  post<{ skill_run: number }>(`/api/skills/${encode(name)}/run`, body)

export const getLooks = () => get<LooksResponse>('/api/looks')

export const getLook = (name: string) => get<LookRow & { layouts: string; preview: string }>(`/api/looks/${encode(name)}`)

export const getSkillRuns = (limit = 50, skill?: string, mode?: string) =>
  get<{ runs: SkillRunRow[] }>(`/api/skill-runs${query([['limit', String(limit)], ['skill', skill], ['mode', mode]])}`)

export const getSkillRun = (seq: number) => get<SkillRun>(`/api/skill-runs/${seq}`)

export const getAgentRuns = (limit = 50) =>
  get<{ runs: AgentRunRow[] }>(`/api/agent-runs${query([['limit', String(limit)]])}`)

export const getStudioSources = () => get<StudioSourcesResponse>('/api/studio/sources')

export const getMcp = () => get<McpResponse>('/api/mcp')
