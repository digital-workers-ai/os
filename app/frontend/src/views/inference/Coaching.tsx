import { useEffect, useState, type ReactNode } from 'react'
import { asApiError, get, post, type ApiError } from '@/api'
import { SectionCard } from '@/components/SectionCard'
import { ErrorBanner } from '@/components/ui/banner'
import { Button } from '@/components/ui/button'
import { Empty } from '@/components/ui/empty'
import { Loading } from '@/components/ui/loading'
import { Chip, Pill } from '@/components/ui/pill'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { num, relTime } from '@/lib/format'
import { BODY, FULL, LayerOff, useLoad } from './shared'

interface CoachingIndex {
  enabled: boolean
  roles: string[]
  recipients: Record<string, string[]>
}

interface ReadCounts {
  metrics: number
  goals: number
  findings: number
}

interface StoredBriefing {
  briefing: string
  model: string
  prompt_version: string
  input_sha: string
  read_manifest: { metrics: Record<string, unknown>; goals: Record<string, unknown>; findings: unknown[] }
  generated_at: string
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

const day = (iso: string) => new Date(iso).toLocaleDateString('en-US', { month: 'short', day: 'numeric' })

function Chips({ briefing, fresh }: { briefing: Briefing; fresh: boolean }) {
  return (
    <p className="mt-3 flex flex-wrap items-center gap-1.5">
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
    </p>
  )
}

function Entry({ briefing, fresh }: { briefing: Briefing; fresh: boolean }) {
  return (
    <div className="py-4 first:pt-0 last:pb-0">
      <p className="text-sm font-medium text-dbb-charcoal" title={briefing.generated_at}>
        {relTime(briefing.generated_at)} · {day(briefing.generated_at)}
      </p>
      <p className="max-w-prose whitespace-pre-wrap text-sm leading-relaxed text-dbb-charcoal">{briefing.briefing}</p>
      <Chips briefing={briefing} fresh={fresh} />
    </div>
  )
}

function RoleCard({ role, title, fresh, onGenerated }: { role: string; title: ReactNode; fresh: boolean; onGenerated: () => void }) {
  const history = useLoad(() => get<{ briefings: StoredBriefing[] }>(`/api/coaching/${encodeURIComponent(role)}/history`), [role])
  const [items, setItems] = useState<Briefing[]>([])
  const [generated, setGenerated] = useState<Briefing | null>(null)
  const [generating, setGenerating] = useState(false)
  const [generateError, setGenerateError] = useState<ApiError | null>(null)
  const entries = generated ? [generated, ...items] : items

  useEffect(() => {
    if (!history.data) return
    setItems(history.data.briefings.map(fromStored))
    setGenerated(null)
  }, [history.data])

  const generate = async () => {
    setGenerating(true)
    setGenerateError(null)
    try {
      const b = await post<Briefing>(`/api/coaching/${encodeURIComponent(role)}`)
      onGenerated()
      setGenerated(b)
      history.reload()
    } catch (e) {
      setGenerateError(asApiError(e))
    } finally {
      setGenerating(false)
    }
  }

  return (
    <SectionCard
      title={title}
      className={FULL}
      bodyClassName={BODY}
      headerRight={
        <Button size="sm" disabled={generating} onClick={generate}>
          {generating ? 'generating…' : 'Generate'}
        </Button>
      }
    >
      <LayerOff error={generateError} />
      <ErrorBanner error={history.error} className="mb-3" />
      {history.loading && entries.length === 0 ? (
        <Loading />
      ) : entries.length === 0 ? (
        <Empty>no briefing yet</Empty>
      ) : (
        <div className="divide-y divide-dbb-warm">
          {entries.map((b, i) => (
            <Entry key={i} briefing={b} fresh={fresh && i === 0} />
          ))}
        </div>
      )}
    </SectionCard>
  )
}

export function Coaching({ onEnabled }: { onEnabled: (on: boolean) => void }) {
  const index = useLoad(() => get<CoachingIndex>('/api/coaching'), [])
  const [selected, setSelected] = useState<string | null>(null)
  const [fresh, setFresh] = useState<string | null>(null)
  const roles = index.data?.roles ?? []
  const emails = selected ? (index.data?.recipients[selected] ?? []) : []

  useEffect(() => {
    if (index.data) onEnabled(index.data.enabled)
  }, [index.data, onEnabled])

  useEffect(() => {
    const first = index.data?.roles[0]
    if (first && selected === null) setSelected(first)
  }, [index.data, selected])

  if (selected === null) {
    return (
      <SectionCard className={FULL} bodyClassName={BODY}>
        <ErrorBanner error={index.error} className="mb-3" />
        {index.data && roles.length === 0 ? <Empty>no role prompts found</Empty> : !index.error && <Loading />}
      </SectionCard>
    )
  }

  return (
    <RoleCard
      key={selected}
      role={selected}
      fresh={fresh === selected}
      onGenerated={() => setFresh(selected)}
      title={
        <div className="flex items-center gap-2">
          <Select value={selected} onValueChange={setSelected}>
            <SelectTrigger className="h-6 w-44 font-normal">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {roles.map((role) => (
                <SelectItem key={role} value={role}>
                  {role.toUpperCase()}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
          {emails.length > 0 && (
            <span className="inline-flex flex-wrap gap-1">
              {emails.map((e) => (
                <Chip key={e}>{e}</Chip>
              ))}
            </span>
          )}
        </div>
      }
    />
  )
}
