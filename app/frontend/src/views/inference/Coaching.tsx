import { useEffect, useState } from 'react'
import { asApiError, get, post, type ApiError } from '@/api'
import { SectionCard } from '@/components/SectionCard'
import { ErrorBanner } from '@/components/ui/banner'
import { Button } from '@/components/ui/button'
import { Empty } from '@/components/ui/empty'
import { Loading } from '@/components/ui/loading'
import { Chip, Pill } from '@/components/ui/pill'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
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

const JOURNAL = `${FULL} lg:min-h-0 lg:flex-1`

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

const stored = (role: string) =>
  get<StoredBriefing>(`/api/coaching/${encodeURIComponent(role)}`)
    .then(fromStored)
    .catch((e) => {
      const error = asApiError(e)
      if (error.status === 404) return null
      throw error
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
      <Chip title={briefing.generated_at}>
        generated <strong>{relTime(briefing.generated_at)}</strong>
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

function RoleCard({ role, fresh, onGenerated }: { role: string; fresh: boolean; onGenerated: (briefing: Briefing) => void }) {
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
      onGenerated(b)
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
      title={role.toUpperCase()}
      className={JOURNAL}
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
  const [briefings, setBriefings] = useState<Record<string, Briefing | null>>({})
  const [loadError, setLoadError] = useState<ApiError | null>(null)
  const [selected, setSelected] = useState<string | null>(null)
  const [fresh, setFresh] = useState<string | null>(null)
  const roles = index.data?.roles ?? []
  const recipients = index.data?.recipients ?? {}

  useEffect(() => {
    if (index.data) onEnabled(index.data.enabled)
  }, [index.data, onEnabled])

  useEffect(() => {
    if (!index.data) return
    let live = true
    const names = index.data.roles
    Promise.all(names.map(stored))
      .then((loaded) => live && setBriefings(Object.fromEntries(names.map((role, i) => [role, loaded[i]]))))
      .catch((e) => live && setLoadError(asApiError(e)))
    return () => {
      live = false
    }
  }, [index.data])

  const generated = (role: string, briefing: Briefing) => {
    setBriefings((all) => ({ ...all, [role]: briefing }))
    setFresh(role)
  }

  return (
    <div className="flex flex-col gap-6 lg:h-full">
      <SectionCard className="shrink-0">
        <ErrorBanner error={index.error} className="mb-3" />
        <ErrorBanner error={loadError} className="mb-3" />
        {index.loading && <Loading />}
        {index.data && roles.length === 0 && <Empty>no role prompts found</Empty>}
        {roles.length > 0 && (
          <Table className="table-fixed" wrapperClassName="overflow-x-visible">
            <TableHeader>
              <TableRow>
                <TableHead className="w-48">Role ({num(roles.length)})</TableHead>
                <TableHead>Email</TableHead>
                <TableHead className="w-32">Generated</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {roles.map((role) => {
                const b = briefings[role]
                const emails = recipients[role] ?? []
                return (
                  <TableRow
                    key={role}
                    className="cursor-pointer"
                    data-state={role === selected ? 'selected' : undefined}
                    aria-selected={role === selected}
                    onClick={() => setSelected(role)}
                  >
                    <TableCell className="font-medium uppercase text-dbb-charcoal">{role}</TableCell>
                    <TableCell>
                      {emails.length === 0 ? (
                        '—'
                      ) : (
                        <span className="inline-flex flex-wrap gap-1">
                          {emails.map((e) => (
                            <Chip key={e}>{e}</Chip>
                          ))}
                        </span>
                      )}
                    </TableCell>
                    <TableCell className="whitespace-nowrap" title={b?.generated_at}>
                      {b ? relTime(b.generated_at) : 'never'}
                    </TableCell>
                  </TableRow>
                )
              })}
            </TableBody>
          </Table>
        )}
      </SectionCard>
      {selected === null ? (
        <SectionCard className={JOURNAL} bodyClassName={BODY}>
          <Empty>select a role</Empty>
        </SectionCard>
      ) : (
        <RoleCard key={selected} role={selected} fresh={fresh === selected} onGenerated={(b) => generated(selected, b)} />
      )}
    </div>
  )
}
