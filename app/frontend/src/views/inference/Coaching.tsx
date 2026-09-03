import { useState } from 'react'
import { asApiError, get, post, type ApiError } from '@/api'
import { SectionCard } from '@/components/SectionCard'
import { Section } from '@/components/SectionHeading'
import { ErrorBanner } from '@/components/ui/banner'
import { Button } from '@/components/ui/button'
import { Empty } from '@/components/ui/empty'
import { Loading } from '@/components/ui/loading'
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
      <p className="flex flex-wrap items-center gap-1.5">
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
      </p>
      <p className="max-w-prose whitespace-pre-wrap text-sm leading-relaxed text-dbb-charcoal">{briefing.briefing}</p>
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
    <Section
      title={role}
      right={
        <Button size="sm" disabled={generating} onClick={generate}>
          {generating ? 'generating…' : 'Generate'}
        </Button>
      }
    >
      <div className="space-y-3">
        <LayerOff error={error} />
        {stored.loading && <Loading />}
        {!briefing &&
          stored.error &&
          (stored.error.status === 404 ? <p className="text-sm text-dbb-muted">{stored.error.detail}</p> : <ErrorBanner error={stored.error} />)}
        {briefing && <BriefingView briefing={briefing} fresh={generated !== null} />}
      </div>
    </Section>
  )
}

export function Coaching() {
  const index = useLoad(() => get<CoachingIndex>('/api/coaching'), [])
  const data = index.data
  return (
    <SectionCard
      title="Coaching"
      description={
        data && (
          <span className="inline-flex flex-wrap items-center gap-x-2 gap-y-1">
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
            {data.inferred && <Pill tone="warn">inferred</Pill>}
            <span>{data.note}</span>
          </span>
        )
      }
    >
      <ErrorBanner error={index.error} className="mb-3" />
      {index.loading && <Loading />}
      {data && data.roles.length === 0 && <Empty>no role prompts found</Empty>}
      {data?.roles.map((role) => (
        <Role key={role} role={role} />
      ))}
    </SectionCard>
  )
}
