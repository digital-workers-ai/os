import { useEffect, useState } from 'react'
import { api, asApiError, type ApiError, type SourceRow, type SyncRunsResponse } from '../../api'
import { Empty, Panel, num, relTime } from '../../components/Panel'
import { Status } from '../../components/Status'

const PAGE = 50

export function Activity({
  sources,
  source,
  onSource,
  tick,
}: {
  sources: SourceRow[]
  source: string
  onSource: (source: string) => void
  tick: number
}) {
  const [offset, setOffset] = useState(0)
  const [page, setPage] = useState<SyncRunsResponse | null>(null)
  const [error, setError] = useState<ApiError | null>(null)

  useEffect(() => {
    setOffset(0)
  }, [source, tick])

  useEffect(() => {
    let live = true
    api
      .syncRuns(source, PAGE, offset)
      .then((r) => {
        if (!live) return
        setPage(r)
        setError(null)
      })
      .catch((e) => live && setError(asApiError(e)))
    return () => {
      live = false
    }
  }, [source, offset, tick])

  const labels = new Map(sources.map((s) => [s.source, s.label]))
  const runs = page?.runs ?? []
  const total = page?.total ?? 0

  return (
    <Panel
      title="Activity"
      actions={
        <div className="filters">
          <select value={source} onChange={(e) => onSource(e.target.value)}>
            <option value="">all sources</option>
            {sources.map((s) => (
              <option key={s.source} value={s.source}>
                {s.label}
              </option>
            ))}
          </select>
          {page && (
            <>
              <button className="btn" disabled={offset === 0} onClick={() => setOffset(Math.max(0, offset - PAGE))}>
                ‹ prev
              </button>
              <span className="dim">
                {total === 0 ? '0' : `${num(offset + 1)}–${num(offset + runs.length)}`} of {num(total)}
              </span>
              <button className="btn" disabled={offset + runs.length >= total} onClick={() => setOffset(offset + PAGE)}>
                next ›
              </button>
            </>
          )}
        </div>
      }
    >
      {error && (
        <div className="panel-body">
          <Status error={error} />
        </div>
      )}
      {!page && !error ? (
        <Empty>loading…</Empty>
      ) : runs.length === 0 ? (
        <Empty>no sync runs yet</Empty>
      ) : (
        <table className="feed">
          <thead>
            <tr>
              <th>When</th>
              <th>Source</th>
              <th>Outcome</th>
              <th className="num">Rows</th>
              <th>Detail</th>
            </tr>
          </thead>
          <tbody>
            {runs.map((r) => (
              <tr key={r.id} className={r.ok ? '' : 'failed'}>
                <td title={r.started_at}>{relTime(r.started_at)}</td>
                <td>
                  <strong>{labels.get(r.source) ?? r.source}</strong> <code className="dim">{r.source}</code>
                </td>
                <td>
                  <span className={'pill ' + (r.ok ? 'ok' : 'err')}>{r.ok ? 'ok' : 'failed'}</span>
                </td>
                <td className="num">{num(r.rows_written)}</td>
                <td className="dim">
                  {r.detail && (
                    <span className="clip" title={r.detail}>
                      {r.detail}
                    </span>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </Panel>
  )
}
