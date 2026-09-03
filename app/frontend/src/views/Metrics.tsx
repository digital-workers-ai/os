import { useEffect, useState, type ReactNode } from 'react'
import { asApiError, get, post, type ApiError } from '../api'
import { SectionCard } from '@/components/SectionCard'
import { Button } from '@/components/ui/button'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { cn } from '@/lib/utils'

interface InferredFrom {
  reading: string
  reads: string
  vocabulary: string
  vocabulary_sha: string
  fields: string[]
}

interface MetricRow {
  label: string
  entity?: string
  value?: number | null
  entities?: number
  error?: string
  note?: string
  mixed_currencies?: string[]
  population?: string
  population_size?: number
  inferred?: boolean
  reading?: string
  vocabulary_sha?: string
  produced_by?: string[]
  raw_fields?: string[]
  attrs?: string[]
  inferred_from?: InferredFrom
}

interface MetricsResponse {
  metrics: Record<string, MetricRow>
}

interface Point {
  value: number | null
  entities: number
  recorded_at: string
}

interface Run {
  inferred: boolean
  vocabulary_sha: string | null
  produced_by: string | null
  points: Point[]
}

interface Series {
  metric: string
  runs: Run[]
  comparable: boolean
  breaks: number
  inferred: boolean
}

interface SnapshotResponse {
  written: number
}

const num = (n: number) => n.toLocaleString()
const plural = (n: number, word: string) => `${n} ${word}${n === 1 ? '' : 's'}`

const relTime = (iso: string) => {
  const then = new Date(iso).getTime()
  if (Number.isNaN(then)) return 'never'
  const secs = Math.max(0, Math.round((Date.now() - then) / 1000))
  if (secs < 60) return `${secs}s ago`
  if (secs < 3600) return `${Math.round(secs / 60)}m ago`
  if (secs < 86400) return `${Math.round(secs / 3600)}h ago`
  return `${Math.round(secs / 86400)}d ago`
}

const verdict = (s: Series) =>
  s.runs.length === 0
    ? 'no snapshots yet'
    : `${plural(s.runs.length, 'run')} — ${s.comparable ? 'comparable' : 'not comparable'}, ${plural(s.breaks, 'break')}`

type Tone = 'warn' | 'unknown' | 'neutral'

const TONES: Record<Tone, string> = {
  warn: 'bg-amber-50 text-amber-800',
  unknown: 'border border-dashed border-dbb-warm text-dbb-muted',
  neutral: 'bg-dbb-sand text-dbb-charcoal',
}

function Pill({ tone, children }: { tone: Tone; children: ReactNode }) {
  return <span className={cn('inline-flex items-center rounded-full px-2 py-0.5 text-[11px] font-medium', TONES[tone])}>{children}</span>
}

function ErrorLine({ error }: { error: ApiError | null }) {
  if (!error) return null
  return (
    <p role="alert" className="mb-3 text-sm text-dbb-clay">
      <span className="font-mono text-xs">{error.status || 'network'}</span> {error.detail}
    </p>
  )
}

function Muted({ children }: { children: ReactNode }) {
  return <p className="text-sm text-dbb-muted">{children}</p>
}

function Value({ value }: { value: number | null | undefined }) {
  return value === null || value === undefined ? <Pill tone="unknown">unknown</Pill> : <>{num(value)}</>
}

function Inferred({ reading, sha, producedBy }: { reading?: string; sha?: string | null; producedBy?: string | null }) {
  return (
    <span className="inline-flex flex-wrap items-center gap-1.5">
      <Pill tone="warn">inferred</Pill>
      {reading && <span className="font-mono text-xs text-dbb-charcoal">{reading}</span>}
      {sha && <span className="font-mono text-xs">{sha.slice(0, 12)}</span>}
      {producedBy && <span className="font-mono text-xs">{producedBy}</span>}
    </span>
  )
}

function Unavailable({ row }: { row: MetricRow }) {
  return (
    <>
      {row.error && <p className="text-dbb-clay">{row.error}</p>}
      {row.mixed_currencies && <p>mixed currencies: {row.mixed_currencies.join(', ')}</p>}
      {row.note && <p>{row.note}</p>}
    </>
  )
}

const W = 240
const H = 40
const PAD = 5

function Sparkline({ points }: { points: Point[] }) {
  const values = points.map((p) => p.value)
  const known = values.filter((v): v is number => v !== null)
  if (known.length === 0) return <Muted>no values to plot</Muted>
  const min = Math.min(...known)
  const max = Math.max(...known)
  const x = (i: number) => (points.length === 1 ? W / 2 : PAD + (i * (W - 2 * PAD)) / (points.length - 1))
  const y = (v: number) => (max === min ? H / 2 : H - PAD - ((v - min) / (max - min)) * (H - 2 * PAD))
  const segments: { x: number; y: number }[][] = []
  let current: { x: number; y: number }[] = []
  values.forEach((v, i) => {
    if (v === null) {
      if (current.length) segments.push(current)
      current = []
      return
    }
    current.push({ x: x(i), y: y(v) })
  })
  if (current.length) segments.push(current)
  return (
    <svg
      className="shrink-0 overflow-visible"
      width={W}
      height={H}
      viewBox={`0 0 ${W} ${H}`}
      role="img"
      aria-label={`${points.length} points, ${num(min)} to ${num(max)}`}
    >
      {segments.map((seg, i) => {
        const line = seg.map((p) => `${p.x},${p.y}`).join(' ')
        return (
          <g key={i}>
            <polygon points={`${line} ${seg[seg.length - 1].x},${H} ${seg[0].x},${H}`} fill="rgba(26,26,26,0.08)" />
            <polyline points={line} fill="none" stroke="#1A1A1A" strokeWidth={2} strokeLinejoin="round" strokeLinecap="round" />
          </g>
        )
      })}
      {values.map((v, i) => (
        <circle
          key={i}
          cx={x(i)}
          cy={v === null ? H / 2 : y(v)}
          r={2.5}
          fill={v === null ? '#FFFFFF' : '#1A1A1A'}
          stroke={v === null ? '#807F74' : 'none'}
          strokeWidth={1.5}
        >
          <title>{`${v === null ? 'unknown' : num(v)} · ${points[i].recorded_at}`}</title>
        </circle>
      ))}
    </svg>
  )
}

function RunSection({ run, index }: { run: Run; index: number }) {
  return (
    <section>
      <h4 className="text-xs uppercase tracking-wide text-dbb-muted">
        Run {index + 1} · {plural(run.points.length, 'point')} ·{' '}
        {run.inferred ? (
          <>
            inferred{run.vocabulary_sha && <span className="ml-1 font-mono normal-case">{run.vocabulary_sha.slice(0, 12)}</span>}
            {run.produced_by && <span className="ml-1 font-mono normal-case">{run.produced_by}</span>}
          </>
        ) : (
          'measured'
        )}
      </h4>
      <div className="mt-2 flex flex-col gap-4 sm:flex-row sm:items-start">
        <Sparkline points={run.points} />
        <div className="min-w-0 flex-1">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead className="text-right">Value</TableHead>
                <TableHead className="text-right">Entities</TableHead>
                <TableHead>Recorded</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {run.points.map((p) => (
                <TableRow key={p.recorded_at}>
                  <TableCell className="text-right tabular-nums text-dbb-charcoal">
                    <Value value={p.value} />
                  </TableCell>
                  <TableCell className="text-right tabular-nums">{num(p.entities)}</TableCell>
                  <TableCell>
                    <span className="font-mono text-xs">{p.recorded_at}</span> {relTime(p.recorded_at)}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      </div>
    </section>
  )
}

export function Metrics() {
  const [metrics, setMetrics] = useState<MetricsResponse | null>(null)
  const [metricsError, setMetricsError] = useState<ApiError | null>(null)
  const [selected, setSelected] = useState<string | null>(null)
  const [series, setSeries] = useState<Series | null>(null)
  const [seriesError, setSeriesError] = useState<ApiError | null>(null)
  const [snapping, setSnapping] = useState(false)
  const [written, setWritten] = useState<number | null>(null)
  const [snapError, setSnapError] = useState<ApiError | null>(null)

  const loadMetrics = () =>
    get<MetricsResponse>('/api/metrics')
      .then((r) => {
        setMetrics(r)
        setMetricsError(null)
      })
      .catch((e) => setMetricsError(asApiError(e)))

  const loadSeries = (name: string) =>
    get<Series>(`/api/metrics/history/${encodeURIComponent(name)}`)
      .then((s) => {
        setSeries(s)
        setSeriesError(null)
      })
      .catch((e) => setSeriesError(asApiError(e)))

  useEffect(() => {
    loadMetrics()
  }, [])

  useEffect(() => {
    if (selected) loadSeries(selected)
  }, [selected])

  const snapshot = async () => {
    setSnapping(true)
    setSnapError(null)
    try {
      setWritten((await post<SnapshotResponse>('/api/metrics/snapshots')).written)
    } catch (e) {
      setSnapError(asApiError(e))
    } finally {
      setSnapping(false)
      loadMetrics()
      if (selected) loadSeries(selected)
    }
  }

  const rows = Object.entries(metrics?.metrics ?? {})
  const row = selected ? metrics?.metrics[selected] : undefined
  const open = series && series.metric === selected ? series : null

  return (
    <div className="space-y-6">
      <SectionCard
        title={`Metrics${metrics ? ` (${rows.length})` : ''}`}
        headerRight={
          <div className="flex items-center gap-3">
            {written !== null && <span className="text-sm text-dbb-muted">{plural(written, 'snapshot')} written</span>}
            <Button size="sm" disabled={snapping || !metrics} onClick={snapshot}>
              {snapping ? 'snapshotting…' : 'Snapshot now'}
            </Button>
          </div>
        }
      >
        <ErrorLine error={metricsError} />
        <ErrorLine error={snapError} />
        {!metrics && !metricsError ? (
          <Muted>loading…</Muted>
        ) : (
          <>
            <p className="mb-3 text-sm text-dbb-muted">click a metric to open its series</p>
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Metric</TableHead>
                  <TableHead className="text-right">Value</TableHead>
                  <TableHead className="text-right">Entities</TableHead>
                  <TableHead>Provenance</TableHead>
                  <TableHead>Unavailable</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {rows.map(([name, m]) => (
                  <TableRow
                    key={name}
                    className="cursor-pointer"
                    data-state={name === selected ? 'selected' : undefined}
                    aria-selected={name === selected}
                    onClick={() => setSelected(name)}
                  >
                    <TableCell>
                      <span className="font-medium text-dbb-charcoal">{m.label}</span> <span className="font-mono text-xs">{name}</span>
                      {m.entity && ` · ${m.entity}`}
                    </TableCell>
                    <TableCell className="text-right tabular-nums text-dbb-charcoal">
                      <Value value={m.value} />
                    </TableCell>
                    <TableCell className="text-right tabular-nums">{m.entities === undefined ? '—' : num(m.entities)}</TableCell>
                    <TableCell>
                      {m.inferred ? (
                        <Inferred reading={m.reading} sha={m.vocabulary_sha} producedBy={m.produced_by?.join(', ') || null} />
                      ) : (
                        <Pill tone="neutral">measured</Pill>
                      )}
                    </TableCell>
                    <TableCell>
                      <Unavailable row={m} />
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </>
        )}
      </SectionCard>

      {selected && (
        <SectionCard
          title={`Series — ${row?.label ?? selected}`}
          headerRight={
            <Button variant="outline" size="sm" onClick={() => loadSeries(selected)}>
              Refresh
            </Button>
          }
        >
          <ErrorLine error={seriesError} />
          {!open && !seriesError && <Muted>loading…</Muted>}
          {open && (
            <p className="text-sm font-medium text-dbb-charcoal">
              {verdict(open)}
              {open.inferred && <span className="font-normal text-dbb-muted"> · inferred series</span>}
            </p>
          )}
          <Tabs defaultValue="points">
            <TabsList className="mt-4">
              <TabsTrigger value="points">Points</TabsTrigger>
              <TabsTrigger value="receipts">Receipts</TabsTrigger>
            </TabsList>
            <TabsContent value="points" className="space-y-6">
              {open && open.runs.map((run, i) => <RunSection key={i} run={run} index={i} />)}
            </TabsContent>
            <TabsContent value="receipts">
              {row && <pre className="overflow-auto rounded-lg bg-dbb-surface p-3 font-mono text-xs">{JSON.stringify(row, null, 2)}</pre>}
            </TabsContent>
          </Tabs>
        </SectionCard>
      )}
    </div>
  )
}
