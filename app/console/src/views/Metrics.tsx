import { useEffect, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { asApiError, get, type ApiError } from '@/api'
import { SectionCard } from '@/components/SectionCard'
import { Section } from '@/components/SectionHeading'
import { Banner, ErrorBanner } from '@/components/ui/banner'
import { Empty } from '@/components/ui/empty'
import { Loading } from '@/components/ui/loading'
import { Mono } from '@/components/ui/mono'
import { Pill } from '@/components/ui/pill'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { num, relTime } from '@/lib/format'
import { useScrollTo } from '@/lib/useScrollTo'
import { LINK, ROW } from '@/search/vocab'

interface InferredFrom {
  reading: string
  reads: string
  vocabulary: string
  vocabulary_sha: string
  fields: string[]
}

interface MetricRow {
  label: string
  description?: string | null
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
  group_by?: string
  grain?: string
  group_by_via?: string
  breakdown?: Record<string, number | null>
  ungrouped_entities?: number
  group_bad_values?: number
  window_days?: number
  window_direction?: string
  window_from?: string
  window_to?: string
  window_bad_values?: number
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

const SPLIT = 'grid items-start gap-6 lg:grid-cols-[0.65fr_0.35fr]'
const FILL = 'lg:flex lg:flex-col lg:h-[calc(100vh-11.25rem-1px)]'
const CAP = 'lg:flex lg:flex-col lg:max-h-[calc(100vh-11.25rem-1px)]'
const BODY = 'lg:min-h-0 lg:overflow-y-auto lg:-mx-6 lg:px-6 lg:-mb-6 lg:pb-6 lg:rounded-b-xl'

const recordedAt = (iso: string) => {
  const secs = (Date.now() - new Date(iso).getTime()) / 1000
  if (Number.isNaN(secs)) return 'never'
  return secs < 7 * 86400 ? relTime(iso) : new Date(iso).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })
}

function Value({ value }: { value: number | null | undefined }) {
  return value === null || value === undefined ? <Pill tone="unknown">unknown</Pill> : <>{num(value)}</>
}

const W = 720
const H = 140
const PAD = 8

function Sparkline({ points }: { points: Point[] }) {
  const values = points.map((p) => p.value)
  const known = values.filter((v): v is number => v !== null)
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
      className="h-32 w-full sm:h-40"
      viewBox={`0 0 ${W} ${H}`}
      data-testid="series-chart"
      preserveAspectRatio="none"
      role="img"
      aria-label={`${points.length} points, ${num(min)} to ${num(max)}`}
    >
      {segments.map((seg, i) => {
        const line = seg.map((p) => `${p.x},${p.y}`).join(' ')
        return (
          <g key={i}>
            <polygon points={`${line} ${seg[seg.length - 1].x},${H} ${seg[0].x},${H}`} fill="rgba(26,26,26,0.08)" />
            <polyline points={line} fill="none" stroke="#1A1A1A" strokeWidth={3} strokeLinejoin="round" strokeLinecap="round" />
          </g>
        )
      })}
      {values.map((v, i) => (
        <circle
          key={i}
          cx={x(i)}
          cy={v === null ? H / 2 : y(v)}
          r={5}
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

function slicePills(m: MetricRow) {
  if (!m.group_by && !m.window_days) return undefined
  return (
    <span className="inline-flex flex-wrap items-center gap-1.5">
      {m.group_by ? <Pill>{`by ${m.group_by}${m.grain ? ` · ${m.grain}` : ''}`}</Pill> : null}
      {m.window_days ? <Pill>{`${num(m.window_days)}d ${m.window_direction}`}</Pill> : null}
    </span>
  )
}

function Breakdown({ m }: { m: MetricRow }) {
  const buckets = Object.entries(m.breakdown ?? {})
  if (buckets.length === 0) return null
  const top = Math.max(0, ...buckets.map(([, v]) => v ?? 0))
  const notes: string[] = []
  if (m.group_by_via) notes.push(`walks ${m.group_by_via}`)
  if (m.ungrouped_entities) notes.push(`${num(m.ungrouped_entities)} without a value`)
  if (m.group_bad_values) notes.push(`${num(m.group_bad_values)} unreadable dates`)
  return (
    <Section title="Breakdown" testId="series-breakdown">
      <Table className="table-fixed" data-testid="series-breakdown-table">
        <TableHeader>
          <TableRow>
            <TableHead hint="Which group this row covers">Bucket</TableHead>
            <TableHead className="w-48 text-right" hint="The metric's value inside this group">Value</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {buckets.map(([bucket, value]) => (
            <TableRow key={bucket}>
              <TableCell className="break-words text-ink">{bucket}</TableCell>
              <TableCell className="text-right">
                <span className="inline-flex items-center gap-2">
                  <span className="block h-1.5 w-16 rounded-full bg-wash">
                    <span className="block h-full rounded-full bg-ink" style={{ width: `${top > 0 ? ((value ?? 0) / top) * 100 : 0}%` }} />
                  </span>
                  <span className="tabular-nums text-ink">
                    <Value value={value} />
                  </span>
                </span>
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
      {notes.length > 0 && <p className="mt-3 text-xs text-muted">{notes.join(' · ')}</p>}
    </Section>
  )
}

function RunSection({ run }: { run: Run }) {
  if (!run.points.some((p) => p.value !== null)) return null
  return (
    <div className="mt-6 first:mt-0">
      <div className="flex flex-col gap-4">
        <Sparkline points={run.points} />
        <div className="min-w-0">
          <Table className="table-fixed" data-testid="series-table">
            <TableHeader>
              <TableRow>
                <TableHead className="w-28 text-right" hint="The metric's value at that time">Value</TableHead>
                <TableHead className="w-24 text-right" hint="How many things were counted at that time">Entities</TableHead>
                <TableHead className="w-32" hint="When this value was recorded">Recorded</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {run.points.map((p) => (
                <TableRow key={p.recorded_at}>
                  <TableCell className="text-right tabular-nums text-ink">
                    <Value value={p.value} />
                  </TableCell>
                  <TableCell className="text-right tabular-nums">{num(p.entities)}</TableCell>
                  <TableCell title={p.recorded_at}>{recordedAt(p.recorded_at)}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      </div>
    </div>
  )
}

export function Metrics() {
  const [params, setParams] = useSearchParams()
  const selected = params.get(LINK.metric)
  const [metrics, setMetrics] = useState<MetricsResponse | null>(null)
  const [metricsError, setMetricsError] = useState<ApiError | null>(null)
  const [series, setSeries] = useState<Series | null>(null)
  const [seriesError, setSeriesError] = useState<ApiError | null>(null)

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

  useScrollTo('metrics-table', ROW.name, selected, !!metrics)

  const select = (name: string) => setParams({ [LINK.metric]: name }, { replace: true })

  const rows = Object.entries(metrics?.metrics ?? {})
  const seriesRow = series ? metrics?.metrics[series.metric] : undefined

  return (
    <div className={SPLIT}>
      <SectionCard className={FILL} bodyClassName={BODY} testId="metrics">
        <ErrorBanner error={metricsError} className="mb-3" />
        {!metrics && !metricsError ? (
          <Loading />
        ) : (
          <>
            <Table className="table-fixed" wrapperClassName="overflow-x-visible" data-testid="metrics-table">
              <TableHeader className="[&_th]:sticky [&_th]:top-0 [&_th]:z-10 [&_th]:bg-card [&_th]:shadow-[inset_0_-1px_0_theme(colors.line)]">
                <TableRow>
                  <TableHead className="w-64" hint="The metric's name, with its id below">Metric ({num(rows.length)})</TableHead>
                  <TableHead className="w-32" hint="What kind of thing the metric measures">Entity</TableHead>
                  <TableHead className="w-24 text-right" hint="The metric's latest value">Value</TableHead>
                  <TableHead className="w-28 text-right" hint="How many things were counted">Entities</TableHead>
                  <TableHead className="w-28 text-center" hint="Which reading this value was inferred from, if any">Inferred from</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {rows.map(([name, m]) => {
                  const warns = Boolean(m.error || m.mixed_currencies || m.note)
                  return (
                    <TableRow
                      key={name}
                      className="cursor-pointer"
                      data-testid="metrics-row"
                      data-name={name}
                      data-state={name === selected ? 'selected' : undefined}
                      aria-selected={name === selected}
                      onClick={() => select(name)}
                    >
                      <TableCell>
                        <span className="flex items-center gap-1.5">
                          {warns && (
                            <button
                              type="button"
                              aria-label="show warning"
                              className="leading-none"
                              data-testid="metrics-warning"
                              onClick={() => select(name)}
                            >
                              ⚠️
                            </button>
                          )}
                          <span className="font-medium text-ink">{m.label}</span>
                        </span>
                        <Mono className="block">{name}</Mono>
                      </TableCell>
                      <TableCell>{m.entity && <Pill>{m.entity}</Pill>}</TableCell>
                      <TableCell className="text-right tabular-nums text-ink">
                        <Value value={m.value} />
                      </TableCell>
                      <TableCell className="text-right tabular-nums">{m.entities === undefined ? '—' : num(m.entities)}</TableCell>
                      <TableCell className="text-center">{m.inferred && m.reading ? <Mono>{m.reading}</Mono> : '—'}</TableCell>
                    </TableRow>
                  )
                })}
              </TableBody>
            </Table>
          </>
        )}
      </SectionCard>

      {seriesError && selected ? (
        <SectionCard title={metrics?.metrics[selected]?.label ?? selected} className={`min-w-0 ${CAP}`} bodyClassName={BODY} testId="series">
          <ErrorBanner error={seriesError} />
        </SectionCard>
      ) : series && seriesRow ? (
        <SectionCard
          title={seriesRow.label}
          description={seriesRow.description}
          headerRight={slicePills(seriesRow)}
          className={`min-w-0 ${CAP}`}
          bodyClassName={BODY}
          testId="series"
        >
          {seriesRow.error && (
            <Banner tone="err" className="mb-3" testId="series-error">
              {seriesRow.error}
            </Banner>
          )}
          {!seriesRow.error && seriesRow.mixed_currencies && (
            <Banner className="mb-3" testId="series-mixed">mixed currencies: {seriesRow.mixed_currencies.join(', ')}</Banner>
          )}
          {!seriesRow.error && seriesRow.note && (
            <Banner className="mb-3" testId="series-note">
              {seriesRow.note}
            </Banner>
          )}
          <Breakdown m={seriesRow} />
          {series.runs.map((run, i) => <RunSection key={i} run={run} />)}
          <Section title="Receipts" testId="series-receipts">
            <p className="mb-3 text-sm text-muted">
              How this number was produced: what was counted, which fields were read, and whether it was inferred.
            </p>
            <pre className="overflow-auto rounded-lg bg-surface p-3 font-mono text-xs">{JSON.stringify(seriesRow, null, 2)}</pre>
          </Section>
        </SectionCard>
      ) : (
        <SectionCard className={`min-w-0 ${CAP}`} bodyClassName={BODY} testId="series">
          <Empty>select a metric</Empty>
        </SectionCard>
      )}
    </div>
  )
}
