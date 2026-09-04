import { useEffect, useState } from 'react'
import { asApiError, get, post, type ApiError } from '@/api'
import { SectionCard } from '@/components/SectionCard'
import { ErrorBanner } from '@/components/ui/banner'
import { Button } from '@/components/ui/button'
import { Empty } from '@/components/ui/empty'
import { Loading } from '@/components/ui/loading'
import { Chip, Pill } from '@/components/ui/pill'
import { STICKY_HEAD, Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { num, relTime } from '@/lib/format'
import { BODY, Enabled, FILL, FULL, LayerOff, useLoad } from './shared'

interface CoachingIndex {
  enabled: boolean
  roles: string[]
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

const SPLIT = 'grid items-start gap-6 lg:grid-cols-[0.35fr_0.65fr] lg:grid-rows-[minmax(0,1fr)] lg:h-full'

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

export function Coaching() {
  const index = useLoad(() => get<CoachingIndex>('/api/coaching'), [])
  const [briefings, setBriefings] = useState<Record<string, Briefing | null>>({})
  const [loadError, setLoadError] = useState<ApiError | null>(null)
  const [selected, setSelected] = useState<string | null>(null)
  const [fresh, setFresh] = useState<string | null>(null)
  const [generating, setGenerating] = useState(false)
  const [generateError, setGenerateError] = useState<ApiError | null>(null)
  const roles = index.data?.roles ?? []

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

  const select = (role: string) => {
    setSelected(role)
    setGenerateError(null)
  }

  const generate = async (role: string) => {
    setGenerating(true)
    setGenerateError(null)
    try {
      const briefing = await post<Briefing>(`/api/coaching/${encodeURIComponent(role)}`)
      setBriefings((all) => ({ ...all, [role]: briefing }))
      setFresh(role)
    } catch (e) {
      setGenerateError(asApiError(e))
    } finally {
      setGenerating(false)
    }
  }

  const briefing = selected ? briefings[selected] : null

  return (
    <div className={SPLIT}>
      <SectionCard className={FULL} bodyClassName={BODY}>
        <ErrorBanner error={index.error} className="mb-3" />
        <ErrorBanner error={loadError} className="mb-3" />
        {index.loading && <Loading />}
        {index.data && roles.length === 0 && <Empty>no role prompts found</Empty>}
        {roles.length > 0 && (
          <Table className="table-fixed" wrapperClassName="overflow-x-visible">
            <TableHeader className={STICKY_HEAD}>
              <TableRow>
                <TableHead>Role ({num(roles.length)})</TableHead>
                <TableHead className="w-36">Model</TableHead>
                <TableHead className="w-24">Generated</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {roles.map((role) => {
                const b = briefings[role]
                return (
                  <TableRow
                    key={role}
                    className="cursor-pointer"
                    data-state={role === selected ? 'selected' : undefined}
                    aria-selected={role === selected}
                    onClick={() => select(role)}
                  >
                    <TableCell className="font-medium uppercase text-dbb-charcoal">{role}</TableCell>
                    <TableCell>{b ? b.model : '—'}</TableCell>
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
        <SectionCard className={FILL} bodyClassName={BODY}>
          <Empty>select a role</Empty>
        </SectionCard>
      ) : (
        <SectionCard
          title={selected.toUpperCase()}
          className={FILL}
          bodyClassName={BODY}
          headerRight={
            <div className="flex items-center gap-2">
              {index.data && <Enabled on={index.data.enabled} />}
              <Button size="sm" disabled={generating} onClick={() => generate(selected)}>
                {generating ? 'generating…' : 'Generate'}
              </Button>
            </div>
          }
        >
          <LayerOff error={generateError} />
          {briefing ? (
            <>
              <p className="max-w-prose whitespace-pre-wrap text-sm leading-relaxed text-dbb-charcoal">{briefing.briefing}</p>
              <Chips briefing={briefing} fresh={fresh === selected} />
            </>
          ) : (
            <Empty>no briefing yet</Empty>
          )}
        </SectionCard>
      )}
    </div>
  )
}
