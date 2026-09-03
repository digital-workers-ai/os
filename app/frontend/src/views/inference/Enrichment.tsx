import { useState } from 'react'
import { asApiError, get, post, type ApiError } from '../../api'
import { Json } from '../../components/Json'
import { Empty, Panel, num, relTime } from '../../components/Panel'
import { Status } from '../../components/Status'
import { Enabled, LayerOff, short, useLoad } from './shared'

interface Gloss {
  label: string
  means: string
}

interface Field {
  name: string
  type: string
  description: string
  labels: Gloss[]
}

interface Reading {
  entity: string
  input: string
  description: string
  sha: string
  fields: Field[]
}

interface Vocabulary {
  enabled: boolean
  model: string
  readings: Record<string, Reading>
}

interface LastRun {
  at: string
  read: number
  failed: number
  truncated_at_cap: boolean
  model: string
  prompt_version: string
}

interface Coverage {
  reading: string
  vocabulary_sha: string
  eligible: number
  read_under_current_vocabulary: number
  read_under_a_retired_vocabulary: number
  never_read: number
  last_run: LastRun | null
}

interface RunReading {
  eligible: number
  pending: number
  reconciled: number
  read: number
  rows: number
  failed: number
  unverified_quotes: number
  truncated_at_cap: boolean
  errors: string[]
}

interface RunReport {
  readings: Record<string, RunReading>
  calls: number
  rows: number
  failed: number
  unverified_quotes: number
  reconciled: number
  duration_ms: number
  truncated_at_cap?: boolean
}

interface Fact {
  canonical_id: string
  entity_type: string
  reading: string
  attr: string
  value: string
  quote: string | null
  quote_verified: boolean
  model: string
  prompt_version: string
  vocabulary_sha: string
}

interface FactsResponse {
  total: number
  limit: number
  offset: number
  unverified_quotes: number
  by_value: Record<string, number>
  inferred: boolean
  counts: string
  facts: Fact[]
}

interface EntityFact {
  reading: string
  attr: string
  value: string
  quote: string | null
  quote_verified: boolean
  model: string
  prompt_version: string
  vocabulary_sha: string
  input_sha: string
  created_at: string
}

interface EntityReadings {
  canonical_id: string
  inferred: boolean
  facts: EntityFact[]
}

const PAGE = 50

function Verified({ ok }: { ok: boolean }) {
  return <span className={'pill ' + (ok ? 'ok' : 'err')}>{ok ? 'verified' : 'unverified'}</span>
}

function CoverageTable({ rows }: { rows: Coverage[] }) {
  return (
    <table>
      <thead>
        <tr>
          <th>Reading</th>
          <th>Vocabulary</th>
          <th className="num">Eligible</th>
          <th className="num">Read under current vocabulary</th>
          <th className="num">Read under a retired vocabulary</th>
          <th className="num">Never read</th>
          <th>Last run</th>
        </tr>
      </thead>
      <tbody>
        {rows.map((r) => (
          <tr key={r.reading}>
            <td>
              <strong>{r.reading}</strong>
            </td>
            <td>
              <code>{r.vocabulary_sha}</code>
            </td>
            <td className="num">{num(r.eligible)}</td>
            <td className="num">{num(r.read_under_current_vocabulary)}</td>
            <td className="num">{num(r.read_under_a_retired_vocabulary)}</td>
            <td className="num">{num(r.never_read)}</td>
            <td>
              {r.last_run === null ? (
                <span className="dim">never</span>
              ) : (
                <>
                  <span title={r.last_run.at}>{relTime(r.last_run.at)}</span> · {num(r.last_run.read)} read ·{' '}
                  {num(r.last_run.failed)} failed
                  {r.last_run.truncated_at_cap && <span className="pill warn"> truncated at cap</span>}{' '}
                  <span className="dim">
                    {r.last_run.model} {r.last_run.prompt_version}
                  </span>
                </>
              )}
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  )
}

function RunResult({ report }: { report: RunReport }) {
  return (
    <>
      <p>
        {num(report.calls)} calls · {num(report.rows)} rows · {num(report.failed)} failed ·{' '}
        {num(report.unverified_quotes)} unverified quotes · {num(report.reconciled)} reconciled ·{' '}
        {num(report.duration_ms)} ms
        {report.truncated_at_cap && <span className="pill warn"> truncated at cap</span>}
      </p>
      <table>
        <thead>
          <tr>
            <th>Reading</th>
            <th className="num">Eligible</th>
            <th className="num">Pending</th>
            <th className="num">Read</th>
            <th className="num">Rows</th>
            <th className="num">Failed</th>
            <th className="num">Unverified</th>
            <th className="num">Reconciled</th>
            <th>Errors</th>
          </tr>
        </thead>
        <tbody>
          {Object.entries(report.readings).map(([name, r]) => (
            <tr key={name}>
              <td>
                <strong>{name}</strong>
                {r.truncated_at_cap && <span className="pill warn"> truncated at cap</span>}
              </td>
              <td className="num">{num(r.eligible)}</td>
              <td className="num">{num(r.pending)}</td>
              <td className="num">{num(r.read)}</td>
              <td className="num">{num(r.rows)}</td>
              <td className="num">{num(r.failed)}</td>
              <td className="num">{num(r.unverified_quotes)}</td>
              <td className="num">{num(r.reconciled)}</td>
              <td className="dim">{r.errors.join('; ')}</td>
            </tr>
          ))}
        </tbody>
      </table>
      <Json value={report} label="raw run report" />
    </>
  )
}

function VocabularyPanel({ vocabulary }: { vocabulary: Vocabulary }) {
  const readings = Object.entries(vocabulary.readings)
  return (
    <Panel title={`Vocabulary (${readings.length})`}>
      {readings.map(([name, r]) => (
        <details key={name} className="reading">
          <summary>
            <strong>{name}</strong> <span className="dim">reads</span> <code>{r.entity}.{r.input}</code>{' '}
            <span className="dim">sha</span> <code>{short(r.sha)}</code> <span className="dim">· {r.fields.length} fields</span>
          </summary>
          <div className="panel-body">
            <p>{r.description}</p>
            {r.fields.map((f) => (
              <div key={f.name} className="card">
                <h3>
                  {f.name} <span className="pill">{f.type}</span>
                </h3>
                <p className="dim">{f.description}</p>
                <table className="glosses">
                  <tbody>
                    {f.labels.map((g) => (
                      <tr key={g.label}>
                        <td>
                          <code>{g.label}</code>
                        </td>
                        <td>{g.means}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ))}
          </div>
        </details>
      ))}
    </Panel>
  )
}

function Facts({ vocabulary, onPick }: { vocabulary: Vocabulary | null; onPick: (id: string) => void }) {
  const [attr, setAttr] = useState('')
  const [value, setValue] = useState('')
  const [unverified, setUnverified] = useState(false)
  const [offset, setOffset] = useState(0)

  const params = new URLSearchParams({ limit: String(PAGE), offset: String(offset) })
  if (attr) params.set('attr', attr)
  if (value) params.set('value', value)
  if (unverified) params.set('unverified_only', 'true')
  const query = params.toString()
  const facts = useLoad(() => get<FactsResponse>(`/api/enrichment?${query}`), [query])

  const fields = Object.values(vocabulary?.readings ?? {}).flatMap((r) => r.fields)
  const attrs = [...new Set(fields.map((f) => f.name))]
  const labels = [...new Set(fields.filter((f) => !attr || f.name === attr).flatMap((f) => f.labels.map((g) => g.label)))]
  const data = facts.data
  const byValue = Object.entries(data?.by_value ?? {})

  return (
    <Panel
      title={`Enriched facts${data ? ` (${num(data.total)})` : ''}`}
      actions={
        <div className="form">
          <select
            value={attr}
            onChange={(e) => {
              setAttr(e.target.value)
              setValue('')
              setOffset(0)
            }}
          >
            <option value="">any attr</option>
            {attrs.map((a) => (
              <option key={a} value={a}>
                {a}
              </option>
            ))}
          </select>
          <select
            value={value}
            onChange={(e) => {
              setValue(e.target.value)
              setOffset(0)
            }}
          >
            <option value="">any value</option>
            {labels.map((l) => (
              <option key={l} value={l}>
                {l}
              </option>
            ))}
          </select>
          <label>
            <input
              type="checkbox"
              checked={unverified}
              onChange={(e) => {
                setUnverified(e.target.checked)
                setOffset(0)
              }}
            />
            unverified quotes only
          </label>
          <button className="btn" disabled={offset === 0} onClick={() => setOffset(Math.max(0, offset - PAGE))}>
            prev
          </button>
          <button className="btn" disabled={!data || offset + PAGE >= data.total} onClick={() => setOffset(offset + PAGE)}>
            next
          </button>
        </div>
      }
    >
      <div className="panel-body">
        <Status error={facts.error} />
        {data && (
          <>
            <p>
              <span className="pill warn">inferred</span> {data.counts}
            </p>
            <p>
              {num(data.total)} facts · {num(data.unverified_quotes)} unverified quotes · showing {num(data.offset)}–
              {num(Math.min(data.offset + data.facts.length, data.total))}
            </p>
            {byValue.length > 0 && (
              <div className="chips">
                {byValue.map(([k, v]) => (
                  <span key={k} className="chip">
                    {k} <strong>{num(v)}</strong>
                  </span>
                ))}
              </div>
            )}
          </>
        )}
      </div>
      {facts.loading && <Empty>loading…</Empty>}
      {data && data.facts.length === 0 && <Empty>no enriched facts match</Empty>}
      {data && data.facts.length > 0 && (
        <table>
          <thead>
            <tr>
              <th>Entity</th>
              <th>Reading</th>
              <th>Attr</th>
              <th>Value</th>
              <th>Quote</th>
              <th>Model</th>
              <th>Vocabulary</th>
            </tr>
          </thead>
          <tbody>
            {data.facts.map((f, i) => (
              <tr key={i}>
                <td>
                  <button className="btn" onClick={() => onPick(f.canonical_id)}>
                    <code>{f.canonical_id.slice(0, 8)}</code>
                  </button>{' '}
                  <span className="dim">{f.entity_type}</span>
                </td>
                <td>{f.reading}</td>
                <td>
                  <code>{f.attr}</code>
                </td>
                <td>
                  <code>{f.value}</code>
                </td>
                <td>
                  <Verified ok={f.quote_verified} /> {f.quote ?? ''}
                </td>
                <td className="dim">
                  {f.model} {f.prompt_version}
                </td>
                <td>
                  <code>{f.vocabulary_sha}</code>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </Panel>
  )
}

function EntityFacts({ id }: { id: string }) {
  const entity = useLoad(() => get<EntityReadings>(`/api/enrichment/${encodeURIComponent(id)}`), [id])
  const rows = entity.data?.facts ?? []
  return (
    <>
      <div className="panel-body">
        <Status error={entity.error} />
        {entity.data && (
          <p>
            <span className="pill warn">inferred</span> readings for <code>{entity.data.canonical_id}</code>
          </p>
        )}
      </div>
      {entity.loading && <Empty>loading…</Empty>}
      {entity.data && rows.length === 0 && <Empty>no readings stored for this entity</Empty>}
      {rows.length > 0 && (
        <table>
          <thead>
            <tr>
              <th>Reading</th>
              <th>Attr</th>
              <th>Value</th>
              <th>Quote</th>
              <th>Model</th>
              <th>Vocabulary</th>
              <th>Input</th>
              <th>Read</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((f, i) => (
              <tr key={i}>
                <td>{f.reading}</td>
                <td>
                  <code>{f.attr}</code>
                </td>
                <td>
                  <code>{f.value}</code>
                </td>
                <td>
                  <Verified ok={f.quote_verified} /> {f.quote ?? ''}
                </td>
                <td className="dim">
                  {f.model} {f.prompt_version}
                </td>
                <td>
                  <code>{f.vocabulary_sha}</code>
                </td>
                <td>
                  <code>{f.input_sha}</code>
                </td>
                <td title={f.created_at}>{relTime(f.created_at)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </>
  )
}

export function Enrichment() {
  const vocab = useLoad(() => get<Vocabulary>('/api/enrichment/vocabulary'), [])
  const coverage = useLoad(() => get<{ readings: Coverage[] }>('/api/enrichment/coverage'), [])
  const [reading, setReading] = useState('')
  const [force, setForce] = useState(false)
  const [limit, setLimit] = useState('')
  const [running, setRunning] = useState(false)
  const [report, setReport] = useState<RunReport | null>(null)
  const [runError, setRunError] = useState<ApiError | null>(null)
  const [entityInput, setEntityInput] = useState('')
  const [entityId, setEntityId] = useState('')

  const run = async () => {
    setRunning(true)
    setRunError(null)
    setReport(null)
    const params = new URLSearchParams()
    if (reading) params.set('reading', reading)
    if (force) params.set('force', 'true')
    if (limit) params.set('limit', limit)
    try {
      setReport(await post<RunReport>(`/api/enrichment/run?${params}`))
    } catch (e) {
      setRunError(asApiError(e))
    } finally {
      setRunning(false)
      coverage.reload()
    }
  }

  const pick = (id: string) => {
    setEntityInput(id)
    setEntityId(id)
  }

  const readings = Object.keys(vocab.data?.readings ?? {})

  return (
    <>
      <Panel
        title="Enrichment"
        actions={
          <form
            className="form"
            onSubmit={(e) => {
              e.preventDefault()
              run()
            }}
          >
            <select value={reading} onChange={(e) => setReading(e.target.value)}>
              <option value="">all readings</option>
              {readings.map((r) => (
                <option key={r} value={r}>
                  {r}
                </option>
              ))}
            </select>
            <label>
              <input type="checkbox" checked={force} onChange={(e) => setForce(e.target.checked)} />
              force
            </label>
            <input
              type="number"
              min={1}
              max={1000}
              placeholder="limit"
              value={limit}
              onChange={(e) => setLimit(e.target.value)}
            />
            <button className="btn" type="submit" disabled={running}>
              {running ? 'running…' : 'Run'}
            </button>
          </form>
        }
      >
        <div className="panel-body">
          <Status error={vocab.error} />
          {vocab.data && (
            <p>
              <Enabled on={vocab.data.enabled} /> model <code>{vocab.data.model}</code>
              {!vocab.data.enabled && <span className="dim"> · the one layer that calls a model; nothing is read until it is switched on</span>}
            </p>
          )}
          <LayerOff error={runError} />
          {report && <RunResult report={report} />}
          <h3>Coverage</h3>
          <p className="dim">
            Four separate claims per reading, not one number: eligible entities carry input text; read under the current
            vocabulary; read under a retired vocabulary; never read at all.
          </p>
          <Status error={coverage.error} />
        </div>
        {coverage.loading && <Empty>loading…</Empty>}
        {coverage.data && <CoverageTable rows={coverage.data.readings} />}
      </Panel>

      {vocab.data && <VocabularyPanel vocabulary={vocab.data} />}

      <Facts vocabulary={vocab.data} onPick={pick} />

      <Panel
        title="Readings for one entity"
        actions={
          <form
            className="form"
            onSubmit={(e) => {
              e.preventDefault()
              setEntityId(entityInput.trim())
            }}
          >
            <input
              className="wide"
              placeholder="canonical id"
              value={entityInput}
              onChange={(e) => setEntityInput(e.target.value)}
            />
            <button className="btn" type="submit" disabled={!entityInput.trim()}>
              Load
            </button>
          </form>
        }
      >
        {entityId ? <EntityFacts id={entityId} /> : <Empty>paste a canonical id, or pick one from the facts above</Empty>}
      </Panel>
    </>
  )
}
