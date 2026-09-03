import { useEffect, useState } from 'react'
import { asApiError, get, post, type ApiError } from '@/api'
import { SectionCard } from '@/components/SectionCard'
import { Section } from '@/components/SectionHeading'
import { Banner, ErrorBanner } from '@/components/ui/banner'
import { Button } from '@/components/ui/button'
import { Empty } from '@/components/ui/empty'
import { Mono } from '@/components/ui/mono'
import { Pill } from '@/components/ui/pill'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { num, plural, relTime, short } from '@/lib/format'

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

const SPLIT = 'grid gap-6 lg:grid-cols-[0.45fr_1.55fr]'

const verdict = (s: Series) =>
  s.runs.length === 0
    ? 'no snapshots yet'
    : `${plural(s.runs.length, 'run')} — ${s.comparable ? 'comparable' : 'not comparable'}, ${plural(s.breaks, 'break')}`

function Value({ value }: { value: number | null | undefined }) {
  return value === null || value === undefined ? <Pill tone="unknown">unknown</Pill> : <>{num(value)}</>
}

const W = 240
const H = 40
const PAD = 5

function Sparkline({ points }: { points: Point[] }) {
  const values = points.map((p) => p.value)
  const known = values.filter((v): v is number => v !== null)
  if (known.length === 0) return <p className="text-sm text-dbb-muted">no values to plot</p>
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
    <Section
      title={
        <>
          Run {index + 1} · {plural(run.points.length, 'point')} ·{' '}
          {run.inferred ? (
            <>
              inferred
              {run.vocabulary_sha && <Mono className="ml-1 normal-case">{short(run.vocabulary_sha, 12)}</Mono>}
              {run.produced_by && <Mono className="ml-1 normal-case">{run.produced_by}</Mono>}
            </>
          ) : (
            'measured'
          )}
        </>
      }
    >
      <div className="flex flex-col gap-4 sm:flex-row sm:items-start">
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
                    <Mono>{p.recorded_at}</Mono> {relTime(p.recorded_at)}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      </div>
    </Section>
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
    <div className={SPLIT}>
      <SectionCard
        title={`Metrics${metrics ? ` (${rows.length})` : ''}`}
        description="click a metric to open its series"
        headerRight={
          <div className="flex items-center gap-3">
            {written !== null && <span className="text-sm text-dbb-muted">{plural(written, 'snapshot')} written</span>}
            <Button size="sm" disabled={snapping || !metrics} onClick={snapshot}>
              {snapping ? 'snapshotting…' : 'Snapshot now'}
            </Button>
          </div>
        }
      >
        <ErrorBanner error={metricsError} className="mb-3" />
        <ErrorBanner error={snapError} className="mb-3" />
        {!metrics && !metricsError ? (
          <Empty>loading…</Empty>
        ) : (
          <>
            <Table className="table-fixed">
              <TableHeader>
                <TableRow>
                  <TableHead className="w-56">Metric</TableHead>
                  <TableHead className="w-32">Entity</TableHead>
                  <TableHead className="w-24 text-right">Value</TableHead>
                  <TableHead className="w-28 text-right">Entities</TableHead>
                  <TableHead className="w-56">Inferred from</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {rows.map(([name, m]) => {
                  const warns = Boolean(m.error || m.mixed_currencies || m.note)
                  return (
                    <TableRow
                      key={name}
                      className="cursor-pointer"
                      data-state={name === selected ? 'selected' : undefined}
                      aria-selected={name === selected}
                      onClick={() => setSelected(name)}
                    >
                      <TableCell>
                        <span className="flex items-center gap-1.5">
                          {warns && (
                            <button type="button" aria-label="show warning" className="leading-none" onClick={() => setSelected(name)}>
                              ⚠️
                            </button>
                          )}
                          <span className="font-medium text-dbb-charcoal">{m.label}</span>
                        </span>
                        <Mono className="block">{name}</Mono>
                      </TableCell>
                      <TableCell>{m.entity && <Mono>{m.entity}</Mono>}</TableCell>
                      <TableCell className="text-right tabular-nums text-dbb-charcoal">
                        <Value value={m.value} />
                      </TableCell>
                      <TableCell className="text-right tabular-nums">{m.entities === undefined ? '—' : num(m.entities)}</TableCell>
                      <TableCell>{m.inferred && m.reading && <Mono>{m.reading}</Mono>}</TableCell>
                    </TableRow>
                  )
                })}
              </TableBody>
            </Table>
          </>
        )}
      </SectionCard>

      {selected ? (
        <SectionCard
          title={`Series — ${row?.label ?? selected}`}
          className="min-w-0"
          description={
            open && (
              <>
                {verdict(open)}
                {open.inferred && ' · inferred series'}
              </>
            )
          }
          headerRight={
            <Button variant="outline" size="sm" onClick={() => loadSeries(selected)}>
              Refresh
            </Button>
          }
        >
          <ErrorBanner error={seriesError} className="mb-3" />
          {row?.error && (
            <Banner tone="err" className="mb-3">
              {row.error}
            </Banner>
          )}
          {!row?.error && row?.mixed_currencies && <Banner className="mb-3">mixed currencies: {row.mixed_currencies.join(', ')}</Banner>}
          {!row?.error && row?.note && <Banner className="mb-3">{row.note}</Banner>}
          {!open && !seriesError && <Empty>loading…</Empty>}
          {open && open.runs.map((run, i) => <RunSection key={i} run={run} index={i} />)}
          {row && (
            <Section title="Receipts">
              <pre className="overflow-auto rounded-lg bg-dbb-surface p-3 font-mono text-xs">{JSON.stringify(row, null, 2)}</pre>
            </Section>
          )}
        </SectionCard>
      ) : (
        <SectionCard title="Series" className="min-w-0">
          <Empty>select a metric</Empty>
        </SectionCard>
      )}
    </div>
  )
}
