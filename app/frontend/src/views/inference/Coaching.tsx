import { useEffect, useState, type ReactNode } from 'react'
import { asApiError, get, post, type ApiError } from '@/api'
import { SectionCard } from '@/components/SectionCard'
import { ErrorBanner } from '@/components/ui/banner'
import { Button } from '@/components/ui/button'
import { Empty } from '@/components/ui/empty'
import { Loading } from '@/components/ui/loading'
import { Mono } from '@/components/ui/mono'
import { Chip, Pill } from '@/components/ui/pill'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { STICKY_HEAD, Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
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
  read_manifest: { metrics: Record<string, unknown>; goals: Record<string, unknown>; findings: unknown[] }
  generated_at: string
}

interface Briefing {
  briefing: string
  model: string
  prompt_version: string
  generated_at: string
  read: ReadCounts
}

const fromStored = (b: StoredBriefing): Briefing => ({
  briefing: b.briefing,
  model: b.model,
  prompt_version: b.prompt_version,
  generated_at: b.generated_at,
  read: {
    metrics: Object.keys(b.read_manifest.metrics).length,
    goals: Object.keys(b.read_manifest.goals).length,
    findings: b.read_manifest.findings.length,
  },
})

const day = (iso: string) => new Date(iso).toLocaleDateString('en-US', { month: 'short', day: 'numeric' })

function Journal({ entries, fresh }: { entries: Briefing[]; fresh: boolean }) {
  return (
    <Table className="table-fixed" wrapperClassName="overflow-x-visible">
      <TableHeader className={STICKY_HEAD}>
        <TableRow>
          <TableHead className="w-36">Generated ({num(entries.length)})</TableHead>
          <TableHead>Briefing</TableHead>
          <TableHead className="w-44">Read</TableHead>
          <TableHead className="w-40">Model</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {entries.map((b, i) => (
          <TableRow key={`${b.generated_at}|${i}`}>
            <TableCell className="align-top">
              <span className="block font-medium text-dbb-charcoal" title={b.generated_at}>
                {relTime(b.generated_at)}
              </span>
              <span className="block">{day(b.generated_at)}</span>
              {fresh && i === 0 && (
                <Pill tone="ok" className="mt-1">
                  just generated
                </Pill>
              )}
            </TableCell>
            <TableCell className="align-top">
              <p className="max-w-prose whitespace-pre-wrap text-sm leading-relaxed text-dbb-charcoal">{b.briefing}</p>
            </TableCell>
            <TableCell className="align-top">
              <span className="block">{num(b.read.metrics)} metrics</span>
              <span className="block">{num(b.read.goals)} goals</span>
              <span className="block">{num(b.read.findings)} findings</span>
            </TableCell>
            <TableCell className="align-top">
              <Mono className="block">{b.model}</Mono>
              <Mono className="block">{b.prompt_version}</Mono>
            </TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
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
        <Journal entries={entries} fresh={fresh} />
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
