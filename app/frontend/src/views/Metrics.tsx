import { useEffect, useState } from 'react'
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

const SPLIT = 'grid items-start gap-6 lg:grid-cols-[0.65fr_0.35fr]'
const FILL = 'lg:flex lg:flex-col lg:max-h-[calc(100vh-12.75rem-1px)]'
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

function RunSection({ run }: { run: Run }) {
  if (!run.points.some((p) => p.value !== null)) return null
  return (
    <div className="mt-6 first:mt-0">
      <div className="flex flex-col gap-4">
        <Sparkline points={run.points} />
        <div className="min-w-0">
          <Table className="table-fixed">
            <TableHeader>
              <TableRow>
                <TableHead className="w-28 text-right">Value</TableHead>
                <TableHead className="w-24 text-right">Entities</TableHead>
                <TableHead className="w-32">Recorded</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {run.points.map((p) => (
                <TableRow key={p.recorded_at}>
                  <TableCell className="text-right tabular-nums text-dbb-charcoal">
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
  const [metrics, setMetrics] = useState<MetricsResponse | null>(null)
  const [metricsError, setMetricsError] = useState<ApiError | null>(null)
  const [selected, setSelected] = useState<string | null>(null)
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

  const rows = Object.entries(metrics?.metrics ?? {})
  const row = selected ? metrics?.metrics[selected] : undefined
  const open = series && series.metric === selected ? series : null

  return (
    <div className={SPLIT}>
      <SectionCard className={FILL} bodyClassName={BODY}>
        <ErrorBanner error={metricsError} className="mb-3" />
        {!metrics && !metricsError ? (
          <Loading />
        ) : (
          <>
            <Table className="table-fixed" wrapperClassName="overflow-x-visible">
              <TableHeader className="[&_th]:sticky [&_th]:top-0 [&_th]:z-10 [&_th]:bg-card [&_th]:shadow-[inset_0_-1px_0_theme(colors.dbb.warm)]">
                <TableRow>
                  <TableHead className="w-64">Metric</TableHead>
                  <TableHead className="w-32">Entity</TableHead>
                  <TableHead className="w-24 text-right">Value</TableHead>
                  <TableHead className="w-28 text-right">Entities</TableHead>
                  <TableHead className="w-28">Inferred from</TableHead>
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
        <SectionCard title={row?.label ?? selected} className={`min-w-0 ${FILL}`} bodyClassName={BODY}>
          {!open && !seriesError ? (
            <Loading />
          ) : (
            <>
              <ErrorBanner error={seriesError} className="mb-3" />
              {row?.error && (
                <Banner tone="err" className="mb-3">
                  {row.error}
                </Banner>
              )}
              {!row?.error && row?.mixed_currencies && <Banner className="mb-3">mixed currencies: {row.mixed_currencies.join(', ')}</Banner>}
              {!row?.error && row?.note && <Banner className="mb-3">{row.note}</Banner>}
              {open && open.runs.map((run, i) => <RunSection key={i} run={run} />)}
              {row && (
                <Section title="Receipts">
                  <p className="mb-3 text-sm text-dbb-muted">
                    How this number was produced: what was counted, which fields were read, and whether it was inferred.
                  </p>
                  <pre className="overflow-auto rounded-lg bg-dbb-surface p-3 font-mono text-xs">{JSON.stringify(row, null, 2)}</pre>
                </Section>
              )}
            </>
          )}
        </SectionCard>
      ) : (
        <SectionCard title="Series" className={`min-w-0 ${FILL}`} bodyClassName={BODY}>
          <Empty>select a metric</Empty>
        </SectionCard>
      )}
    </div>
  )
}
