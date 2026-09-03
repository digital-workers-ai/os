import './Estate.css'
import { useEffect, useState } from 'react'
import {
  api,
  asApiError,
  type ApiError,
  type EngineReport,
  type RebuildResponse,
  type ReportResponse,
  type SourcesResponse,
  type SyncResponse,
} from '../api'
import { Json } from '../components/Json'
import { Empty, Panel, num, relTime } from '../components/Panel'
import { Status } from '../components/Status'
import { Activity } from './estate/Activity'

const validationClass = (v: string) =>
  v === 'provider-validated' ? 'ok' : v === 'mock-validated' ? 'warn' : ''

function Counts({ title, rows }: { title: string; rows: Record<string, number> }) {
  const entries = Object.entries(rows || {})
  return (
    <div className="card">
      <h3>
        {title} <span className="dim">({entries.length})</span>
      </h3>
      {entries.length === 0 ? (
        <div className="dim">0</div>
      ) : (
        <table>
          <tbody>
            {entries.map(([k, v]) => (
              <tr key={k}>
                <td>
                  <code>{k}</code>
                </td>
                <td className="num">{num(v)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  )
}

const SECTIONED: (keyof EngineReport)[] = [
  'totals',
  'skips',
  'records_skipped',
  'identity_less',
  'dangling_refs',
  'quarantines',
  'oversized',
  'clears',
  'dead_paths',
  'disagreements',
  'match_rates',
  'counts',
]

function Report({ report }: { report: EngineReport }) {
  const other = Object.entries(report).filter(([k]) => !SECTIONED.includes(k as keyof EngineReport))
  return (
    <>
      <div className="panel-body">
        <h3>Totals</h3>
        <div className="chips">
          {Object.entries(report.totals).map(([k, v]) => (
            <span key={k} className="chip">
              {k} <strong>{num(v)}</strong>
            </span>
          ))}
        </div>

        <h3>Refusals by reason</h3>
        <div className="grid">
          <Counts title="skips" rows={report.skips} />
          <Counts title="records_skipped" rows={report.records_skipped} />
          <Counts title="identity_less" rows={report.identity_less} />
          <Counts title="dangling_refs" rows={report.dangling_refs} />
          <div className="card">
            <h3>
              quarantines <span className="dim">({report.quarantines.length})</span>
            </h3>
            {report.quarantines.length === 0 ? (
              <div className="dim">0</div>
            ) : (
              <ul className="list">
                {report.quarantines.map((q, i) => (
                  <li key={i}>
                    <strong>{q.rel}</strong> <code>{q.record}</code> — {q.detail}
                  </li>
                ))}
              </ul>
            )}
          </div>
          <div className="card">
            <h3>
              oversized <span className="dim">({report.oversized.length})</span>
            </h3>
            {report.oversized.length === 0 ? (
              <div className="dim">0</div>
            ) : (
              <ul className="list">
                {report.oversized.map((o, i) => (
                  <li key={i}>
                    <span className="pill warn">{o.kind}</span> <code>{JSON.stringify(o)}</code>
                  </li>
                ))}
              </ul>
            )}
          </div>
        </div>

        <h3>Cleared</h3>
        <div className="grid">
          <Counts title="clears" rows={report.clears} />
          <Counts title="disagreements" rows={report.disagreements} />
        </div>

        <h3>
          Dead paths <span className="dim">({report.dead_paths.length})</span>
        </h3>
        {report.dead_paths.length === 0 ? (
          <div className="dim">0</div>
        ) : (
          <ul className="list">
            {report.dead_paths.map((p) => (
              <li key={p}>
                <code>{p}</code>
              </li>
            ))}
          </ul>
        )}

        <h3>
          Match rates <span className="dim">({Object.keys(report.match_rates).length})</span>
        </h3>
      </div>
      <table>
        <thead>
          <tr>
            <th>Relationship</th>
            <th className="num">Candidates</th>
            <th className="num">Matched</th>
            <th className="num">Edges</th>
            <th className="num">Rate</th>
          </tr>
        </thead>
        <tbody>
          {Object.entries(report.match_rates).map(([rel, r]) => (
            <tr key={rel}>
              <td>{rel}</td>
              <td className="num">{num(r.candidates)}</td>
              <td className="num">{num(r.matched)}</td>
              <td className="num">{num(r.edges)}</td>
              <td className="num">{r.match_rate === null ? '—' : r.match_rate}</td>
            </tr>
          ))}
        </tbody>
      </table>
      <div className="panel-body">
        <h3>
          Counts <span className="dim">({Object.keys(report.counts).length})</span>
        </h3>
        <Json value={report.counts} label="counts" />
        {other.length > 0 && (
          <>
            <h3>Other keys</h3>
            <Json value={Object.fromEntries(other)} label={other.map(([k]) => k).join(', ')} open />
          </>
        )}
        <Json value={report} label="raw report" />
      </div>
    </>
  )
}

export function Estate() {
  const [sources, setSources] = useState<SourcesResponse | null>(null)
  const [sourcesError, setSourcesError] = useState<ApiError | null>(null)
  const [syncing, setSyncing] = useState<string | null>(null)
  const [sync, setSync] = useState<SyncResponse | null>(null)
  const [syncError, setSyncError] = useState<ApiError | null>(null)
  const [synced, setSynced] = useState(0)
  const [activitySource, setActivitySource] = useState('')
  const [rebuilding, setRebuilding] = useState(false)
  const [rebuild, setRebuild] = useState<RebuildResponse | null>(null)
  const [rebuildError, setRebuildError] = useState<ApiError | null>(null)
  const [report, setReport] = useState<ReportResponse | null>(null)
  const [reportError, setReportError] = useState<ApiError | null>(null)

  const loadSources = () =>
    api
      .sources()
      .then((r) => {
        setSources(r)
        setSourcesError(null)
      })
      .catch((e) => setSourcesError(asApiError(e)))

  const loadReport = () =>
    api
      .report()
      .then((r) => {
        setReport(r)
        setReportError(null)
      })
      .catch((e) => setReportError(asApiError(e)))

  useEffect(() => {
    loadSources()
    loadReport()
  }, [])

  const runSync = async (only?: string[]) => {
    setSyncing(only ? only.join(',') : 'all')
    setSyncError(null)
    try {
      setSync(await api.sync(only))
    } catch (e) {
      setSyncError(asApiError(e))
    } finally {
      setSyncing(null)
      setSynced((n) => n + 1)
      loadSources()
    }
  }

  const runRebuild = async () => {
    setRebuilding(true)
    setRebuildError(null)
    try {
      setRebuild(await api.rebuild())
    } catch (e) {
      setRebuildError(asApiError(e))
    } finally {
      setRebuilding(false)
      loadReport()
    }
  }

  const rows = sources?.sources ?? []

  return (
    <>
      <Panel
        title={`Sources${sources ? ` (${rows.length})` : ''}`}
        actions={
          <button className="btn" disabled={syncing !== null || !sources} onClick={() => runSync()}>
            {syncing === 'all' ? 'syncing…' : 'Sync all'}
          </button>
        }
      >
        <div className="panel-body">
          <Status error={sourcesError} />
          {sources && <p>{sources.validation_coverage.detail}</p>}
        </div>
        {!sources && !sourcesError ? (
          <Empty>loading…</Empty>
        ) : (
          <table>
            <thead>
              <tr>
                <th>Source</th>
                <th>Validation</th>
                <th>Entities</th>
                <th>Last sync</th>
                <th className="num">Attempts</th>
                <th>Rows</th>
                <th>Enabled</th>
                <th>Detail</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {rows.map((r) => {
                const last = sync?.results.find((s) => s.source === r.source)
                return (
                  <tr key={r.source}>
                    <td>
                      <strong>
                        <button className="link-btn" title="show activity" onClick={() => setActivitySource(r.source)}>
                          {r.label}
                        </button>
                      </strong>{' '}
                      <code className="dim">{r.source}</code>
                    </td>
                    <td>
                      <span className={'pill ' + validationClass(r.validation)}>{r.validation}</span>
                    </td>
                    <td>{r.entities.join(', ') || '—'}</td>
                    <td>
                      {r.last_attempt === null ? (
                        <span className="dim">never</span>
                      ) : (
                        <>
                          <span className={'pill ' + (r.last_success === r.last_attempt ? 'ok' : 'err')}>
                            {r.last_success === r.last_attempt ? 'ok' : 'failed'}
                          </span>{' '}
                          {relTime(r.last_attempt)}
                        </>
                      )}
                    </td>
                    <td className="num">{num(r.attempts)}</td>
                    <td>
                      {last ? (
                        <>
                          {num(last.rows_written)} written / {num(last.rows_fetched)} fetched
                          {last.rows_refused ? <span className="pill err"> {last.rows_refused} refused</span> : null}
                          {last.rows_colliding ? <span className="pill warn"> {last.rows_colliding} colliding</span> : null}
                        </>
                      ) : (
                        <span className="dim">new data {relTime(r.last_new_data)}</span>
                      )}
                    </td>
                    <td>{r.enabled_by_default ? 'on' : 'off'}</td>
                    <td className="dim">{r.detail || ''}</td>
                    <td>
                      <button
                        className="btn"
                        disabled={syncing !== null}
                        onClick={() => runSync([r.source])}
                      >
                        {syncing === r.source ? 'syncing…' : 'Sync'}
                      </button>
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        )}
      </Panel>

      <Activity sources={rows} source={activitySource} onSource={setActivitySource} tick={synced} />

      {(sync || syncError) && (
        <Panel title="Last sync">
          <div className="panel-body">
            <Status error={syncError} />
            {sync && (
              <p>
                {sync.ok} ok, {sync.failed} failed, {num(sync.rows_written)} rows written.
              </p>
            )}
          </div>
          {sync && (
            <table>
              <thead>
                <tr>
                  <th>Source</th>
                  <th>Ok</th>
                  <th className="num">Fetched</th>
                  <th className="num">Written</th>
                  <th className="num">Refused</th>
                  <th className="num">Colliding</th>
                  <th className="num">Pages</th>
                  <th>Truncated</th>
                  <th>Detail</th>
                </tr>
              </thead>
              <tbody>
                {sync.results.map((r) => (
                  <tr key={r.source}>
                    <td>
                      <code>{r.source}</code>
                    </td>
                    <td>
                      <span className={'pill ' + (r.ok ? 'ok' : 'err')}>{r.ok ? 'ok' : 'failed'}</span>
                    </td>
                    <td className="num">{num(r.rows_fetched)}</td>
                    <td className="num">{num(r.rows_written)}</td>
                    <td className="num">{num(r.rows_refused)}</td>
                    <td className="num">{num(r.rows_colliding)}</td>
                    <td className="num">{num(r.pages_read)}</td>
                    <td>{r.truncated ? 'yes' : 'no'}</td>
                    <td className="dim">{r.detail || ''}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </Panel>
      )}

      <Panel
        title="Rebuild"
        actions={
          <button className="btn" disabled={rebuilding} onClick={runRebuild}>
            {rebuilding ? 'rebuilding…' : 'Rebuild'}
          </button>
        }
      >
        <div className="panel-body">
          {rebuildError?.status === 409 ? (
            <div className="status">
              <code>409</code> rebuild in progress — {rebuildError.detail}
            </div>
          ) : (
            <Status error={rebuildError} />
          )}
          {rebuild ? (
            <p>
              {rebuild.ok ? 'ok' : 'failed'} · {num(rebuild.entities)} entities · {num(rebuild.canonical)} canonical ·{' '}
              {num(rebuild.links)} links · {num(rebuild.facts)} facts · {num(rebuild.raw_events_read)} raw events read ·{' '}
              {num(rebuild.duration_ms)} ms
            </p>
          ) : (
            !rebuildError && <p className="dim">no rebuild run from this page yet</p>
          )}
        </div>
      </Panel>

      <Panel title="Report" actions={<button className="btn" onClick={loadReport}>Refresh</button>}>
        <div className="panel-body">
          <Status error={reportError} />
          {!report && !reportError && <Empty>loading…</Empty>}
          {report && !report.ran && <Empty>{report.detail}</Empty>}
          {report && report.ran && (
            <p>
              {report.ok ? 'ok' : 'failed'} · ran {relTime(report.created_at)} · {num(report.duration_ms)} ms ·{' '}
              {num(report.raw_events_read)} raw events read · {num(report.entities)} entities · {num(report.facts)} facts
            </p>
          )}
        </div>
        {report && report.ran && <Report report={report.report} />}
      </Panel>
    </>
  )
}
