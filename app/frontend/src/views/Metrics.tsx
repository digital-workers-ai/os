import { useEffect, useState } from 'react'
import { asApiError, get, post, type ApiError } from '../api'
import { Json } from '../components/Json'
import { Empty, Panel, num, relTime } from '../components/Panel'
import { Status } from '../components/Status'
import './Metrics.css'

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

const plural = (n: number, word: string) => `${n} ${word}${n === 1 ? '' : 's'}`

const verdict = (s: Series) =>
  s.runs.length === 0
    ? 'no snapshots yet'
    : `${plural(s.runs.length, 'run')} — ${s.comparable ? 'comparable' : 'not comparable'}, ${plural(s.breaks, 'break')}`

function Value({ value }: { value: number | null | undefined }) {
  return value === null || value === undefined ? <span className="pill">unknown</span> : <>{num(value)}</>
}

function InferredBadge({
  reading,
  sha,
  producedBy,
}: {
  reading?: string
  sha?: string | null
  producedBy?: string | null
}) {
  return (
    <span className="inferred">
      <span className="pill warn">inferred</span>
      {reading && <code>{reading}</code>}
      {sha && <code className="dim">{sha.slice(0, 12)}</code>}
      {producedBy && <code className="dim">{producedBy}</code>}
    </span>
  )
}

function Unavailable({ row }: { row: MetricRow }) {
  return (
    <>
      {row.error && <span className="reason err">{row.error}</span>}
      {row.mixed_currencies && <span className="reason">mixed currencies: {row.mixed_currencies.join(', ')}</span>}
      {row.note && <span className="reason">{row.note}</span>}
    </>
  )
}

const W = 240
const H = 40
const PAD = 5

function Sparkline({ points }: { points: Point[] }) {
  const values = points.map((p) => p.value)
  const known = values.filter((v): v is number => v !== null)
  if (known.length === 0) return <span className="dim">no values to plot</span>
  const min = Math.min(...known)
  const max = Math.max(...known)
  const x = (i: number) => (points.length === 1 ? W / 2 : PAD + (i * (W - 2 * PAD)) / (points.length - 1))
  const y = (v: number) => (max === min ? H / 2 : H - PAD - ((v - min) / (max - min)) * (H - 2 * PAD))
  const segments: string[] = []
  let current: string[] = []
  values.forEach((v, i) => {
    if (v === null) {
      if (current.length) segments.push(current.join(' '))
      current = []
      return
    }
    current.push(`${x(i)},${y(v)}`)
  })
  if (current.length) segments.push(current.join(' '))
  return (
    <svg className="spark" width={W} height={H} viewBox={`0 0 ${W} ${H}`} role="img" aria-label={`${points.length} points, ${num(min)} to ${num(max)}`}>
      {segments.map((d, i) => (
        <polyline key={i} points={d} />
      ))}
      {values.map((v, i) => (
        <circle key={i} className={v === null ? 'gap' : undefined} cx={x(i)} cy={v === null ? H / 2 : y(v)} r={2.5}>
          <title>{`${v === null ? 'unknown' : num(v)} · ${points[i].recorded_at}`}</title>
        </circle>
      ))}
    </svg>
  )
}

function RunSection({ run, index }: { run: Run; index: number }) {
  return (
    <>
      <h3>
        run {index + 1} <span className="dim">({plural(run.points.length, 'point')})</span>{' '}
        {run.inferred ? (
          <InferredBadge sha={run.vocabulary_sha} producedBy={run.produced_by} />
        ) : (
          <span className="pill">measured</span>
        )}
      </h3>
      <div className="run">
        <Sparkline points={run.points} />
        <table>
          <thead>
            <tr>
              <th className="num">Value</th>
              <th className="num">Entities</th>
              <th>Recorded</th>
            </tr>
          </thead>
          <tbody>
            {run.points.map((p) => (
              <tr key={p.recorded_at}>
                <td className="num">
                  <Value value={p.value} />
                </td>
                <td className="num">{num(p.entities)}</td>
                <td>
                  <code>{p.recorded_at}</code> <span className="dim">{relTime(p.recorded_at)}</span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </>
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
    <>
      <Panel
        title={`Metrics${metrics ? ` (${rows.length})` : ''}`}
        actions={
          <>
            {written !== null && <span className="dim">{plural(written, 'snapshot')} written</span>}
            <button className="btn" disabled={snapping || !metrics} onClick={snapshot}>
              {snapping ? 'snapshotting…' : 'Snapshot now'}
            </button>
          </>
        }
      >
        <div className="panel-body">
          <Status error={metricsError} />
          <Status error={snapError} />
          {metrics && <p className="dim">click a metric to open its series</p>}
        </div>
        {!metrics && !metricsError ? (
          <Empty>loading…</Empty>
        ) : (
          <table>
            <thead>
              <tr>
                <th>Metric</th>
                <th className="num">Value</th>
                <th className="num">Entities</th>
                <th>Provenance</th>
                <th>Unavailable</th>
              </tr>
            </thead>
            <tbody>
              {rows.map(([name, m]) => (
                <tr key={name} className="metric-row" aria-selected={name === selected} onClick={() => setSelected(name)}>
                  <td>
                    <strong>{m.label}</strong> <code className="dim">{name}</code>
                    {m.entity && <span className="dim"> · {m.entity}</span>}
                  </td>
                  <td className="num">
                    <Value value={m.value} />
                  </td>
                  <td className="num">{m.entities === undefined ? '—' : num(m.entities)}</td>
                  <td>
                    {m.inferred ? (
                      <InferredBadge reading={m.reading} sha={m.vocabulary_sha} producedBy={m.produced_by?.join(', ') || null} />
                    ) : (
                      <span className="pill">measured</span>
                    )}
                  </td>
                  <td>
                    <Unavailable row={m} />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </Panel>

      {selected && (
        <Panel
          title={`Series — ${row?.label ?? selected}`}
          actions={
            <button className="btn" onClick={() => loadSeries(selected)}>
              Refresh
            </button>
          }
        >
          <div className="panel-body">
            <Status error={seriesError} />
            {!open && !seriesError && <Empty>loading…</Empty>}
            {open && (
              <p>
                <strong>{verdict(open)}</strong>
                {open.inferred && <span className="dim"> · inferred series</span>}
              </p>
            )}
            {open && open.runs.map((run, i) => <RunSection key={i} run={run} index={i} />)}
            {row && <Json value={row} label="receipts" />}
          </div>
        </Panel>
      )}
    </>
  )
}
