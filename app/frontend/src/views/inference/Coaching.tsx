import { useState } from 'react'
import { asApiError, get, post, type ApiError } from '../../api'
import { Empty, Panel, num, relTime } from '../../components/Panel'
import { Status } from '../../components/Status'
import { Enabled, LayerOff, useLoad } from './shared'

interface CoachingIndex {
  enabled: boolean
  model: string
  prompt_version: string
  prompts_sha: string
  roles: string[]
  inferred: boolean
  note: string
}

interface ReadCounts {
  metrics: number
  goals: number
  findings: number
}

interface StoredBriefing {
  role: string
  briefing: string
  model: string
  prompt_version: string
  input_sha: string
  read_manifest: { metrics: Record<string, unknown>; goals: Record<string, unknown>; findings: unknown[] }
  generated_at: string
}

interface GeneratedBriefing {
  role: string
  briefing: string
  generated_at: string
  model: string
  prompt_version: string
  input_sha: string
  read: ReadCounts
}

interface Briefing {
  briefing: string
  model: string
  prompt_version: string
  input_sha: string
  generated_at: string
  read: ReadCounts
}

const fromStored = (b: StoredBriefing): Briefing => ({
  briefing: b.briefing,
  model: b.model,
  prompt_version: b.prompt_version,
  input_sha: b.input_sha,
  generated_at: b.generated_at,
  read: {
    metrics: Object.keys(b.read_manifest.metrics).length,
    goals: Object.keys(b.read_manifest.goals).length,
    findings: b.read_manifest.findings.length,
  },
})

function BriefingView({ briefing, fresh }: { briefing: Briefing; fresh: boolean }) {
  return (
    <>
      <div className="chips">
        {fresh && <span className="pill ok">just generated</span>}
        <span className="chip">
          model <strong>{briefing.model}</strong>
        </span>
        <span className="chip">
          prompt <strong>{briefing.prompt_version}</strong>
        </span>
        <span className="chip">
          input <strong>{briefing.input_sha}</strong>
        </span>
        <span className="chip">
          read <strong>{num(briefing.read.metrics)}</strong> metrics · <strong>{num(briefing.read.goals)}</strong> goals ·{' '}
          <strong>{num(briefing.read.findings)}</strong> findings
        </span>
        <span className="chip" title={briefing.generated_at}>
          generated <strong>{relTime(briefing.generated_at)}</strong>
        </span>
      </div>
      <pre className="prose">{briefing.briefing}</pre>
    </>
  )
}

function Role({ role }: { role: string }) {
  const stored = useLoad(() => get<StoredBriefing>(`/api/coaching/${encodeURIComponent(role)}`), [role])
  const [generating, setGenerating] = useState(false)
  const [generated, setGenerated] = useState<Briefing | null>(null)
  const [error, setError] = useState<ApiError | null>(null)

  const generate = async () => {
    setGenerating(true)
    setError(null)
    try {
      const r = await post<GeneratedBriefing>(`/api/coaching/${encodeURIComponent(role)}`)
      setGenerated({
        briefing: r.briefing,
        model: r.model,
        prompt_version: r.prompt_version,
        input_sha: r.input_sha,
        generated_at: r.generated_at,
        read: r.read,
      })
    } catch (e) {
      setError(asApiError(e))
    } finally {
      setGenerating(false)
    }
  }

  const briefing = generated ?? (stored.data ? fromStored(stored.data) : null)

  return (
    <div className="card">
      <div className="card-head">
        <h3>{role}</h3>
        <div className="spacer" />
        <button className="btn" disabled={generating} onClick={generate}>
          {generating ? 'generating…' : 'Generate'}
        </button>
      </div>
      <LayerOff error={error} />
      {stored.loading && <Empty>loading…</Empty>}
      {!briefing && stored.error && (stored.error.status === 404 ? <Empty>{stored.error.detail}</Empty> : <Status error={stored.error} />)}
      {briefing && <BriefingView briefing={briefing} fresh={generated !== null} />}
    </div>
  )
}

export function Coaching() {
  const index = useLoad(() => get<CoachingIndex>('/api/coaching'), [])
  const data = index.data
  return (
    <Panel title={`Coaching${data ? ` (${data.roles.length} roles)` : ''}`}>
      <div className="panel-body">
        <Status error={index.error} />
        {index.loading && <Empty>loading…</Empty>}
        {data && (
          <>
            <p>
              <Enabled on={data.enabled} /> model <code>{data.model}</code> · prompt <code>{data.prompt_version}</code> ·
              prompts sha <code>{data.prompts_sha}</code>
            </p>
            <p>
              {data.inferred && <span className="pill warn">inferred</span>} {data.note}
            </p>
            {data.roles.length === 0 ? (
              <Empty>no role prompts found</Empty>
            ) : (
              <div className="grid">
                {data.roles.map((role) => (
                  <Role key={role} role={role} />
                ))}
              </div>
            )}
          </>
        )}
      </div>
    </Panel>
  )
}
