import { useState, type ReactNode } from 'react'
import { get } from '../api'
import { SectionCard } from '@/components/SectionCard'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { ALL, Chip, Empty, Enabled, Fail, Mono, Pill, num, short, useLoad } from './inference/shared'

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

const keyCol = 'font-medium text-dbb-charcoal'

function Heading({ children, count }: { children: ReactNode; count: number }) {
  return (
    <h4 className="text-sm font-medium text-dbb-charcoal">
      {children} <span className="font-normal text-dbb-muted">({num(count)})</span>
    </h4>
  )
}

function Loaded<T>({
  got,
  count,
  children,
}: {
  got: ReturnType<typeof useLoad<T>>
  count: (d: T) => string
  children: (d: T) => ReactNode
}) {
  if (got.error) return <Fail error={got.error} />
  if (!got.data) return <Empty>loading…</Empty>
  return (
    <div className="space-y-4">
      <p className="text-sm text-dbb-muted">{count(got.data)}</p>
      {children(got.data)}
    </div>
  )
}

function Grounding({ value }: { value: string }) {
  const [kind, attr] = value.split(':', 2)
  return (
    <span className="inline-flex items-center gap-1.5">
      <Pill>{kind}</Pill>
      <Mono>{attr ?? ''}</Mono>
    </span>
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

function OntologyTab({ o }: { o: Ontology }) {
  const entities = Object.entries(o.entities)
  return (
    <div className="space-y-6">
      <div className="space-y-2">
        <Heading count={o.source_priority.length}>Source priority</Heading>
        <div className="flex flex-wrap gap-1.5">
          {o.source_priority.map((s, i) => (
            <Chip key={s}>
              {i + 1} <strong>{s}</strong>
            </Chip>
          ))}
        </div>
      </div>
      <div className="space-y-2">
        <Heading count={entities.length}>Entities</Heading>
        <div className="flex flex-col gap-4 md:grid md:grid-cols-2 xl:grid-cols-3">
          {entities.map(([name, spec]) => (
            <div key={name} className="rounded-lg border border-dbb-warm p-3">
              <Heading count={Object.keys(spec.attrs).length}>{name}</Heading>
              <Table>
                <TableBody>
                  {Object.entries(spec.attrs).map(([attr, type]) => (
                    <TableRow key={attr}>
                      <TableCell className="py-1 font-mono text-xs text-dbb-charcoal">
                        <span className="inline-flex items-center gap-1.5">
                          {attr}
                          {spec.identity.includes(attr) && <Pill tone="up">identity</Pill>}
                        </span>
                      </TableCell>
                      <TableCell className="py-1">{type}</TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
              {spec.identity.length === 0 && <p className="mt-2 text-sm text-dbb-muted">no identity attrs</p>}
            </div>
          ))}
        </div>
      </div>
      <div className="space-y-2">
        <Heading count={o.relationships.length}>Relationships</Heading>
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Relationship</TableHead>
              <TableHead>From</TableHead>
              <TableHead>To</TableHead>
              <TableHead>Cardinality</TableHead>
              <TableHead>Grounding</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {o.relationships.map((r) => (
              <TableRow key={`${r.rel}|${r.from}|${r.to}`}>
                <TableCell className={keyCol}>
                  <Mono>{r.rel}</Mono>
                </TableCell>
                <TableCell>{r.from}</TableCell>
                <TableCell>{r.to}</TableCell>
                <TableCell>{r.cardinality}</TableCell>
                <TableCell>
                  <Grounding value={r.grounding} />
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>
    </div>
  )
}

function MappingsTab({ m }: { m: Mappings }) {
  const [source, setSource] = useState('')
  const sources = [...new Set(m.lines.map((l) => l.source))].sort()
  const lines = source ? m.lines.filter((l) => l.source === source) : m.lines
  const hooked = lines.filter((l) => l.from_hook).length
  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center gap-3 text-sm text-dbb-muted">
        <Select value={source || ALL} onValueChange={(v) => setSource(v === ALL ? '' : v)}>
          <SelectTrigger className="h-8 w-48">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value={ALL}>all sources ({sources.length})</SelectItem>
            {sources.map((s) => (
              <SelectItem key={s} value={s}>
                {s}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
        <span>
          {num(lines.length)} lines · {num(hooked)} hook-produced fields
        </span>
      </div>
      <p className="text-sm text-dbb-muted">
        hook sources ({m.hook_sources.length}): {m.hook_sources.join(', ')}
      </p>
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Source</TableHead>
            <TableHead>Object type</TableHead>
            <TableHead>Path</TableHead>
            <TableHead>Entity.label</TableHead>
            <TableHead>Transform</TableHead>
            <TableHead>Origin</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {lines.map((l) => (
            <TableRow key={`${l.source}|${l.object_type}|${l.path}|${l.entity}|${l.label}`}>
              <TableCell className={keyCol}>{l.source}</TableCell>
              <TableCell>
                <Mono>{l.object_type}</Mono>
              </TableCell>
              <TableCell>
                <Mono>{l.path}</Mono>
              </TableCell>
              <TableCell>
                {l.entity}.<span className={keyCol}>{l.label}</span>
              </TableCell>
              <TableCell>{l.transform ? <Mono>{l.transform}</Mono> : '—'}</TableCell>
              <TableCell>{l.from_hook ? <Pill tone="warn">hook</Pill> : <Pill>payload</Pill>}</TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </div>
  )
}

function TransformsTab({ t }: { t: Transforms }) {
  const labels = Object.entries(t.labels).sort(([a], [b]) => a.localeCompare(b))
  const users = (fn: string) => labels.filter(([, f]) => f === fn).length
  return (
    <div className="space-y-6">
      <div className="space-y-2">
        <Heading count={Object.keys(t.registry).length}>Registry</Heading>
        <div className="flex flex-wrap gap-1.5">
          {Object.entries(t.registry).map(([fn, r]) => (
            <Chip key={fn}>
              {fn} → <strong>{r.produces}</strong> ×{users(fn)}
            </Chip>
          ))}
        </div>
      </div>
      <div className="space-y-2">
        <Heading count={labels.length}>Labels</Heading>
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Label</TableHead>
              <TableHead>Function</TableHead>
              <TableHead>Produces</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {labels.map(([label, fn]) => (
              <TableRow key={label}>
                <TableCell className={keyCol}>
                  <Mono>{label}</Mono>
                </TableCell>
                <TableCell>
                  <Mono>{fn}</Mono>
                </TableCell>
                <TableCell>{t.registry[fn]?.produces ?? <Pill tone="err">unregistered</Pill>}</TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>
    </div>
  )
}

function MetricsTab({ m }: { m: MetricDefinitions }) {
  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead>Name</TableHead>
          <TableHead>Entity</TableHead>
          <TableHead>Expression</TableHead>
          <TableHead>Filter</TableHead>
          <TableHead>Kind</TableHead>
          <TableHead>Raw fields</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {Object.entries(m.definitions).map(([name, d]) => {
          const p = m.provenance[name]
          return (
            <TableRow key={name}>
              <TableCell className="align-top">
                <span className={keyCol}>{d.label}</span> <Mono>{name}</Mono>
              </TableCell>
              <TableCell className="align-top">{d.entity}</TableCell>
              <TableCell className="align-top">
                <Mono>{expressionText(d)}</Mono>
              </TableCell>
              <TableCell className="align-top">{filterText(d.filter) ? <Mono>{filterText(d.filter)}</Mono> : '—'}</TableCell>
              <TableCell className="align-top">
                {d.inferred ? (
                  <span className="inline-flex flex-wrap items-center gap-1.5">
                    <Pill tone="warn">inferred</Pill>
                    <span>
                      reading <Mono>{d.reading}</Mono>
                    </span>
                    {p?.inferred_from && (
                      <span>
                        reads <Mono>{p.inferred_from.reads}</Mono> · {p.inferred_from.vocabulary} <Mono>{p.inferred_from.vocabulary_sha}</Mono>
                      </span>
                    )}
                  </span>
                ) : (
                  <Pill tone="up">observed</Pill>
                )}
              </TableCell>
              <TableCell className="align-top">
                {p && p.raw_fields.length > 0 ? (
                  <ul className="space-y-0.5">
                    {p.raw_fields.map((f) => (
                      <li key={f}>
                        <Mono>{f}</Mono>
                      </li>
                    ))}
                  </ul>
                ) : (
                  '—'
                )}
              </TableCell>
            </TableRow>
          )
        })}
      </TableBody>
    </Table>
  )
}

function EnrichmentTab({ v }: { v: Vocabulary }) {
  const readings = Object.entries(v.readings)
  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-2 text-sm text-dbb-muted">
        <Enabled on={v.enabled} />
        <span>
          model <Mono>{v.model}</Mono>
        </span>
        <span>
          · {readings.length} {readings.length === 1 ? 'reading' : 'readings'}
        </span>
      </div>
      {readings.map(([name, r]) => (
        <div key={name} className="space-y-3 rounded-lg border border-dbb-warm p-3">
          <div className="flex flex-wrap items-center gap-x-2 gap-y-1 text-sm text-dbb-muted">
            <span className={keyCol}>{name}</span>
            <span>
              reads{' '}
              <Mono>
                {r.entity}.{r.input}
              </Mono>
            </span>
            <span>
              sha <Mono title={r.sha}>{short(r.sha)}</Mono>
            </span>
          </div>
          <p className="max-w-prose text-sm text-dbb-muted">{r.description}</p>
          {r.fields.map((f) => (
            <div key={f.name} className="space-y-1 border-t border-dbb-warm/30 pt-3">
              <div className="flex flex-wrap items-center gap-2 text-sm text-dbb-muted">
                <span className="font-mono text-xs text-dbb-charcoal">{f.name}</span>
                <Pill>{f.type}</Pill>
                <span>({f.labels.length} labels)</span>
              </div>
              <p className="max-w-prose text-sm text-dbb-muted">{f.description}</p>
              <Table>
                <TableBody>
                  {f.labels.map((l) => (
                    <TableRow key={l.label}>
                      <TableCell className="w-px whitespace-nowrap py-1 font-mono text-xs text-dbb-charcoal">{l.label}</TableCell>
                      <TableCell className="py-1">{l.means}</TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>
          ))}
        </div>
      ))}
    </div>
  )
}

export function Knowledge() {
  const ontology = useLoad(() => get<Ontology>('/api/knowledge/ontology'), [])
  const mappings = useLoad(() => get<Mappings>('/api/knowledge/mappings'), [])
  const transforms = useLoad(() => get<Transforms>('/api/knowledge/transforms'), [])
  const metrics = useLoad(() => get<MetricDefinitions>('/api/knowledge/metrics'), [])
  const vocabulary = useLoad(() => get<Vocabulary>('/api/enrichment/vocabulary'), [])

  const files = [
    { name: 'ontology', ...ontology },
    { name: 'mappings', ...mappings },
    { name: 'transforms', ...transforms },
    { name: 'metrics', ...metrics },
    { name: 'enrichment', ...vocabulary },
  ]
  const served = files.filter((f) => f.data).length

  return (
    <SectionCard
      title={`${served} of ${files.length} knowledge files served`}
      headerRight={
        <div className="flex flex-wrap gap-1.5">
          {files.map((f) => (
            <Pill key={f.name} tone={f.error ? 'err' : 'neutral'}>
              {f.name}
            </Pill>
          ))}
        </div>
      }
    >
      <Tabs defaultValue="ontology">
        <TabsList>
          <TabsTrigger value="ontology">Ontology</TabsTrigger>
          <TabsTrigger value="mappings">Mappings</TabsTrigger>
          <TabsTrigger value="transforms">Transforms</TabsTrigger>
          <TabsTrigger value="metrics">Metrics</TabsTrigger>
          <TabsTrigger value="enrichment">Enrichment</TabsTrigger>
        </TabsList>
        <TabsContent value="ontology">
          <Loaded
            got={ontology}
            count={(o) =>
              `${Object.keys(o.entities).length} entities · ${o.relationships.length} relationships · ${o.source_priority.length} sources`
            }
          >
            {(o) => <OntologyTab o={o} />}
          </Loaded>
        </TabsContent>
        <TabsContent value="mappings">
          <Loaded
            got={mappings}
            count={(m) => `${num(m.lines.length)} lines · ${num(m.lines.filter((l) => l.from_hook).length)} hook-produced`}
          >
            {(m) => <MappingsTab m={m} />}
          </Loaded>
        </TabsContent>
        <TabsContent value="transforms">
          <Loaded
            got={transforms}
            count={(t) => `${Object.keys(t.registry).length} functions · ${Object.keys(t.labels).length} labels`}
          >
            {(t) => <TransformsTab t={t} />}
          </Loaded>
        </TabsContent>
        <TabsContent value="metrics">
          <Loaded
            got={metrics}
            count={(m) =>
              `${Object.keys(m.definitions).length} definitions · ${Object.values(m.definitions).filter((d) => d.inferred).length} inferred`
            }
          >
            {(m) => <MetricsTab m={m} />}
          </Loaded>
        </TabsContent>
        <TabsContent value="enrichment">
          <Loaded
            got={vocabulary}
            count={(v) =>
              `${Object.keys(v.readings).length} readings · ${Object.values(v.readings).reduce((n, r) => n + r.fields.length, 0)} fields`
            }
          >
            {(v) => <EnrichmentTab v={v} />}
          </Loaded>
        </TabsContent>
      </Tabs>
    </SectionCard>
  )
}
