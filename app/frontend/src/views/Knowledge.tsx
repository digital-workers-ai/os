import { useEffect, useState, type ReactNode } from 'react'
import { asApiError, get, type ApiError } from '../api'
import { Json } from '../components/Json'
import { Empty, num } from '../components/Panel'
import { Status } from '../components/Status'
import './Knowledge.css'

interface EntitySpec {
  identity: string[]
  attrs: Record<string, string>
}

interface Relationship {
  rel: string
  from: string
  to: string
  cardinality: string
  grounding: string
}

interface Ontology {
  source_priority: string[]
  entities: Record<string, EntitySpec>
  relationships: Relationship[]
}

interface MappingLine {
  entity: string
  source: string
  object_type: string
  path: string
  label: string
  transform: string | null
  from_hook: boolean
}

interface Mappings {
  lines: MappingLine[]
  hook_sources: string[]
}

interface Transforms {
  labels: Record<string, string>
  registry: Record<string, { produces: string }>
}

interface Term {
  expression: string
  filter?: Record<string, string>
}

interface MetricDef {
  label: string
  entity: string
  expression?: string
  filter?: Record<string, string>
  source?: string
  inferred?: boolean
  reading?: string
  op?: string
  terms?: Term[]
}

interface InferredFrom {
  reading: string
  reads: string
  vocabulary: string
  vocabulary_sha: string
  fields: string[]
}

interface Provenance {
  label: string
  raw_fields: string[]
  attrs: string[]
  inferred?: boolean
  inferred_from?: InferredFrom
}

interface MetricDefinitions {
  definitions: Record<string, MetricDef>
  provenance: Record<string, Provenance>
}

interface VocabLabel {
  label: string
  means: string
}

interface VocabField {
  name: string
  type: string
  description: string
  labels: VocabLabel[]
}

interface Reading {
  entity: string
  input: string
  description: string
  sha: string
  fields: VocabField[]
}

interface Vocabulary {
  enabled: boolean
  model: string
  readings: Record<string, Reading>
}

function useGet<T>(path: string) {
  const [got, setGot] = useState<{ path: string; data: T | null; error: ApiError | null } | null>(null)
  useEffect(() => {
    let live = true
    get<T>(path)
      .then((data) => live && setGot({ path, data, error: null }))
      .catch((e) => live && setGot({ path, data: null, error: asApiError(e) }))
    return () => {
      live = false
    }
  }, [path])
  const fresh = got?.path === path ? got : null
  return { data: fresh?.data ?? null, error: fresh?.error ?? null, loading: !fresh }
}

function Section({
  title,
  count,
  error,
  loading,
  children,
}: {
  title: string
  count?: string
  error: ApiError | null
  loading: boolean
  children: ReactNode
}) {
  return (
    <details className="panel section" open>
      <summary className="panel-head">
        <h2>{title}</h2>
        {count && <span className="dim">{count}</span>}
        <div className="spacer" />
        {error && <span className="pill err">not served</span>}
      </summary>
      {error && (
        <div className="panel-body">
          <Status error={error} />
        </div>
      )}
      {loading && !error && <Empty>loading…</Empty>}
      {!loading && !error && children}
    </details>
  )
}

function Grounding({ value }: { value: string }) {
  const [kind, attr] = value.split(':', 2)
  return (
    <>
      <span className="pill">{kind}</span> <code>{attr ?? ''}</code>
    </>
  )
}

const filterText = (f?: Record<string, string>) =>
  f && Object.keys(f).length
    ? Object.entries(f)
        .map(([k, v]) => `${k}=${v}`)
        .join(', ')
    : ''

const expressionText = (m: MetricDef) =>
  m.terms
    ? m.terms
        .map((t) => {
          const f = filterText(t.filter)
          return f ? `${t.expression} where ${f}` : t.expression
        })
        .join(` ${m.op ?? '?'} `)
    : (m.expression ?? '')

function OntologyView({ o }: { o: Ontology }) {
  const entities = Object.entries(o.entities)
  return (
    <>
      <div className="panel-body">
        <h3>
          Source priority <span className="dim">({o.source_priority.length})</span>
        </h3>
        <div className="chips">
          {o.source_priority.map((s, i) => (
            <span key={s} className="chip">
              <span className="dim">{i + 1}</span> {s}
            </span>
          ))}
        </div>
        <h3>
          Entities <span className="dim">({entities.length})</span>
        </h3>
        <div className="grid">
          {entities.map(([name, spec]) => (
            <div key={name} className="card">
              <h3>
                {name} <span className="dim">({Object.keys(spec.attrs).length})</span>
              </h3>
              <table>
                <tbody>
                  {Object.entries(spec.attrs).map(([attr, type]) => (
                    <tr key={attr}>
                      <td>
                        <code>{attr}</code>
                        {spec.identity.includes(attr) && (
                          <>
                            {' '}
                            <span className="pill ok">identity</span>
                          </>
                        )}
                      </td>
                      <td className="dim">{type}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
              {spec.identity.length === 0 && <div className="dim">no identity attrs</div>}
            </div>
          ))}
        </div>
        <h3>
          Relationships <span className="dim">({o.relationships.length})</span>
        </h3>
      </div>
      <table>
        <thead>
          <tr>
            <th>Relationship</th>
            <th>From</th>
            <th>To</th>
            <th>Cardinality</th>
            <th>Grounding</th>
          </tr>
        </thead>
        <tbody>
          {o.relationships.map((r) => (
            <tr key={`${r.rel}|${r.from}|${r.to}`}>
              <td>
                <code>{r.rel}</code>
              </td>
              <td>{r.from}</td>
              <td>{r.to}</td>
              <td className="dim">{r.cardinality}</td>
              <td>
                <Grounding value={r.grounding} />
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </>
  )
}

function MappingsView({ m }: { m: Mappings }) {
  const [source, setSource] = useState('')
  const sources = [...new Set(m.lines.map((l) => l.source))].sort()
  const lines = source ? m.lines.filter((l) => l.source === source) : m.lines
  const hooked = lines.filter((l) => l.from_hook).length
  return (
    <>
      <div className="panel-body">
        <div className="filters">
          <select value={source} onChange={(e) => setSource(e.target.value)}>
            <option value="">all sources ({sources.length})</option>
            {sources.map((s) => (
              <option key={s} value={s}>
                {s}
              </option>
            ))}
          </select>
          <span>
            {num(lines.length)} lines · {num(hooked)} hook-produced fields
          </span>
        </div>
        <p className="dim">
          hook sources ({m.hook_sources.length}): {m.hook_sources.join(', ')}
        </p>
      </div>
      <table>
        <thead>
          <tr>
            <th>Source</th>
            <th>Object type</th>
            <th>Path</th>
            <th>Entity.label</th>
            <th>Transform</th>
            <th>Origin</th>
          </tr>
        </thead>
        <tbody>
          {lines.map((l) => (
            <tr key={`${l.source}|${l.object_type}|${l.path}|${l.entity}|${l.label}`}>
              <td>
                <code>{l.source}</code>
              </td>
              <td>
                <code>{l.object_type}</code>
              </td>
              <td>
                <code>{l.path}</code>
              </td>
              <td>
                {l.entity}.<strong>{l.label}</strong>
              </td>
              <td>{l.transform ? <code>{l.transform}</code> : <span className="dim">—</span>}</td>
              <td>{l.from_hook ? <span className="pill warn">hook</span> : <span className="dim">payload</span>}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </>
  )
}

function TransformsView({ t }: { t: Transforms }) {
  const labels = Object.entries(t.labels).sort(([a], [b]) => a.localeCompare(b))
  const users = (fn: string) => labels.filter(([, f]) => f === fn).length
  return (
    <>
      <div className="panel-body">
        <h3>
          Registry <span className="dim">({Object.keys(t.registry).length})</span>
        </h3>
        <div className="chips">
          {Object.entries(t.registry).map(([fn, r]) => (
            <span key={fn} className="chip">
              {fn} → <strong>{r.produces}</strong> <span className="dim">×{users(fn)}</span>
            </span>
          ))}
        </div>
        <h3>
          Labels <span className="dim">({labels.length})</span>
        </h3>
      </div>
      <table>
        <thead>
          <tr>
            <th>Label</th>
            <th>Function</th>
            <th>Produces</th>
          </tr>
        </thead>
        <tbody>
          {labels.map(([label, fn]) => (
            <tr key={label}>
              <td>
                <code>{label}</code>
              </td>
              <td>
                <code>{fn}</code>
              </td>
              <td>{t.registry[fn]?.produces ?? <span className="pill err">unregistered</span>}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </>
  )
}

function MetricsView({ m }: { m: MetricDefinitions }) {
  return (
    <table>
      <thead>
        <tr>
          <th>Name</th>
          <th>Entity</th>
          <th>Expression</th>
          <th>Filter</th>
          <th>Kind</th>
          <th>Raw fields</th>
        </tr>
      </thead>
      <tbody>
        {Object.entries(m.definitions).map(([name, d]) => {
          const p = m.provenance[name]
          return (
            <tr key={name}>
              <td>
                <strong>{d.label}</strong> <code className="dim">{name}</code>
              </td>
              <td>{d.entity}</td>
              <td>
                <code>{expressionText(d)}</code>
              </td>
              <td>{filterText(d.filter) ? <code>{filterText(d.filter)}</code> : <span className="dim">—</span>}</td>
              <td>
                {d.inferred ? (
                  <>
                    <span className="pill warn">inferred</span>{' '}
                    <span className="dim">
                      reading <code>{d.reading}</code>
                      {p?.inferred_from && (
                        <>
                          {' '}
                          reads <code>{p.inferred_from.reads}</code> · {p.inferred_from.vocabulary}{' '}
                          <code>{p.inferred_from.vocabulary_sha}</code>
                        </>
                      )}
                    </span>
                  </>
                ) : (
                  <span className="pill ok">observed</span>
                )}
              </td>
              <td>
                {p && p.raw_fields.length > 0 ? (
                  <ul className="list plain">
                    {p.raw_fields.map((f) => (
                      <li key={f}>
                        <code>{f}</code>
                      </li>
                    ))}
                  </ul>
                ) : (
                  <span className="dim">none</span>
                )}
              </td>
            </tr>
          )
        })}
      </tbody>
    </table>
  )
}

function VocabularyView({ v }: { v: Vocabulary }) {
  const readings = Object.entries(v.readings)
  return (
    <div className="panel-body">
      <p>
        <span className={'pill ' + (v.enabled ? 'ok' : 'warn')}>{v.enabled ? 'enabled' : 'disabled'}</span> model{' '}
        <code>{v.model}</code> · {readings.length} {readings.length === 1 ? 'reading' : 'readings'}
      </p>
      {readings.map(([name, r]) => (
        <div key={name} className="card reading">
          <h3>
            {name} <span className="dim">reads</span> {r.entity}.{r.input} <span className="dim">sha</span>{' '}
            <code title={r.sha}>{r.sha.slice(0, 12)}</code>
          </h3>
          <p className="gloss">{r.description}</p>
          {r.fields.map((f) => (
            <div key={f.name} className="field">
              <h3>
                <code>{f.name}</code> <span className="pill">{f.type}</span>{' '}
                <span className="dim">({f.labels.length} labels)</span>
              </h3>
              <p className="gloss">{f.description}</p>
              <table>
                <tbody>
                  {f.labels.map((l) => (
                    <tr key={l.label}>
                      <td className="label">
                        <code>{l.label}</code>
                      </td>
                      <td className="gloss">{l.means}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ))}
        </div>
      ))}
    </div>
  )
}

export function Knowledge() {
  const ontology = useGet<Ontology>('/api/knowledge/ontology')
  const mappings = useGet<Mappings>('/api/knowledge/mappings')
  const transforms = useGet<Transforms>('/api/knowledge/transforms')
  const metrics = useGet<MetricDefinitions>('/api/knowledge/metrics')
  const vocabulary = useGet<Vocabulary>('/api/enrichment/vocabulary')

  const files = [
    { name: 'ontology', ok: !!ontology.data },
    { name: 'mappings', ok: !!mappings.data },
    { name: 'transforms', ok: !!transforms.data },
    { name: 'metrics', ok: !!metrics.data },
    { name: 'enrichment', ok: !!vocabulary.data },
  ]
  const served = files.filter((f) => f.ok).length

  return (
    <>
      <div className="panel">
        <div className="panel-body served">
          <strong>
            {served} of {files.length} knowledge files served
          </strong>
          <div className="chips">
            {files.map((f) => (
              <span key={f.name} className={'chip ' + (f.ok ? '' : 'missing')}>
                {f.name}
              </span>
            ))}
          </div>
          <span className="dim">read-only view of the declarations as the backend serves them</span>
        </div>
      </div>

      <Section
        title="Ontology"
        count={
          ontology.data
            ? `${Object.keys(ontology.data.entities).length} entities · ${ontology.data.relationships.length} relationships · ${ontology.data.source_priority.length} sources`
            : undefined
        }
        error={ontology.error}
        loading={ontology.loading}
      >
        {ontology.data && <OntologyView o={ontology.data} />}
      </Section>

      <Section
        title="Mappings"
        count={
          mappings.data
            ? `${num(mappings.data.lines.length)} lines · ${num(mappings.data.lines.filter((l) => l.from_hook).length)} hook-produced`
            : undefined
        }
        error={mappings.error}
        loading={mappings.loading}
      >
        {mappings.data && <MappingsView m={mappings.data} />}
      </Section>

      <Section
        title="Transforms"
        count={
          transforms.data
            ? `${Object.keys(transforms.data.registry).length} functions · ${Object.keys(transforms.data.labels).length} labels`
            : undefined
        }
        error={transforms.error}
        loading={transforms.loading}
      >
        {transforms.data && <TransformsView t={transforms.data} />}
      </Section>

      <Section
        title="Metrics"
        count={
          metrics.data
            ? `${Object.keys(metrics.data.definitions).length} definitions · ${Object.values(metrics.data.definitions).filter((d) => d.inferred).length} inferred`
            : undefined
        }
        error={metrics.error}
        loading={metrics.loading}
      >
        {metrics.data && <MetricsView m={metrics.data} />}
      </Section>

      <Section
        title="Enrichment vocabulary"
        count={
          vocabulary.data
            ? `${Object.keys(vocabulary.data.readings).length} readings · ${Object.values(vocabulary.data.readings).reduce((n, r) => n + r.fields.length, 0)} fields`
            : undefined
        }
        error={vocabulary.error}
        loading={vocabulary.loading}
      >
        {vocabulary.data && (
          <>
            <VocabularyView v={vocabulary.data} />
            <div className="panel-body">
              <Json value={vocabulary.data} label="vocabulary as served" />
            </div>
          </>
        )}
      </Section>
    </>
  )
}
