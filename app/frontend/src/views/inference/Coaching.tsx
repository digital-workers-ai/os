import { useState } from 'react'
import { asApiError, get, post, type ApiError } from '@/api'
import { SectionCard } from '@/components/SectionCard'
import { ErrorBanner } from '@/components/ui/banner'
import { Button } from '@/components/ui/button'
import { Empty } from '@/components/ui/empty'
import { Mono } from '@/components/ui/mono'
import { Chip, Pill } from '@/components/ui/pill'
import { num, relTime } from '@/lib/format'
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
    <div className="space-y-3">
      <div className="flex flex-wrap items-center gap-1.5">
        {fresh && <Pill tone="ok">just generated</Pill>}
        <Chip>
          model <strong>{briefing.model}</strong>
        </Chip>
        <Chip>
          prompt <strong>{briefing.prompt_version}</strong>
        </Chip>
        <Chip>
          input <strong>{briefing.input_sha}</strong>
        </Chip>
        <Chip>
          read <strong>{num(briefing.read.metrics)}</strong> metrics · <strong>{num(briefing.read.goals)}</strong> goals ·{' '}
          <strong>{num(briefing.read.findings)}</strong> findings
        </Chip>
        <Chip title={briefing.generated_at}>
          generated <strong>{relTime(briefing.generated_at)}</strong>
        </Chip>
      </div>
      <p className="text-sm leading-relaxed whitespace-pre-wrap text-dbb-charcoal">{briefing.briefing}</p>
    </div>
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
    <SectionCard
      title={role}
      headerRight={
        <Button size="sm" disabled={generating} onClick={generate}>
          {generating ? 'generating…' : 'Generate'}
        </Button>
      }
    >
      <div className="space-y-3">
        <LayerOff error={error} />
        {stored.loading && <Empty>loading…</Empty>}
        {!briefing && stored.error && (stored.error.status === 404 ? <Empty>{stored.error.detail}</Empty> : <ErrorBanner error={stored.error} />)}
        {briefing && <BriefingView briefing={briefing} fresh={generated !== null} />}
      </div>
    </SectionCard>
  )
}

export function Coaching() {
  const index = useLoad(() => get<CoachingIndex>('/api/coaching'), [])
  const data = index.data
  return (
    <SectionCard title="Coaching">
      <div className="space-y-4">
        <ErrorBanner error={index.error} />
        {index.loading && <Empty>loading…</Empty>}
        {data && (
          <>
            <div className="flex flex-wrap items-center gap-x-2 gap-y-1 text-sm text-dbb-muted">
              <Enabled on={data.enabled} />
              <span>
                model <Mono>{data.model}</Mono>
              </span>
              <span>
                · prompt <Mono>{data.prompt_version}</Mono>
              </span>
              <span>
                · prompts sha <Mono>{data.prompts_sha}</Mono>
              </span>
            </div>
            <div className="flex flex-wrap items-center gap-2 text-sm text-dbb-muted">
              {data.inferred && <Pill tone="warn">inferred</Pill>}
              <span>{data.note}</span>
            </div>
            {data.roles.length === 0 ? (
              <Empty>no role prompts found</Empty>
            ) : (
              <div className="grid gap-4 md:grid-cols-2">
                {data.roles.map((role) => (
                  <Role key={role} role={role} />
                ))}
              </div>
            )}
          </>
        )}
      </div>
    </SectionCard>
  )
}
