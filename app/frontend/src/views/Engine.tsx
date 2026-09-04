import { useEffect, useState, type ReactNode } from 'react'
import { get } from '@/api'
import { SectionCard } from '@/components/SectionCard'
import { ErrorBanner } from '@/components/ui/banner'
import { Loading } from '@/components/ui/loading'
import { Mono } from '@/components/ui/mono'
import { PAGE, Pager } from '@/components/ui/pager'
import { Chip, Pill, type Tone } from '@/components/ui/pill'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { num } from '@/lib/format'
import { cn } from '@/lib/utils'
import { ALL, Enabled, useLoad } from './inference/shared'
import { Readings, type Vocabulary } from './inference/Vocabulary'

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

type Condition = { attr: string } & Record<string, unknown>

interface RuleDefinition {
  label: string
  entity: string
  severity: string
  all: Condition[]
  any: Condition[]
}

interface Rules {
  rules: Record<string, RuleDefinition>
}

interface GoalDeclaration {
  metric: string
  target: number
  strategy: string
  params: Record<string, unknown>
}

interface Goals {
  goals: Record<string, GoalDeclaration>
}

const keyCol = 'font-medium text-dbb-charcoal'

const severityTone = (s: string): Tone => (s === 'high' ? 'err' : s === 'medium' ? 'warn' : 'neutral')

const describe = (c: Condition) =>
  Object.entries(c)
    .filter(([k]) => k !== 'attr')
    .map(([op, v]) => `${c.attr} ${op} ${JSON.stringify(v)}`)

const paramValue = (v: unknown) => (typeof v === 'number' ? num(v) : String(v))

function Loaded<T>({ got, children }: { got: ReturnType<typeof useLoad<T>>; children: (d: T) => ReactNode }) {
  return <SectionCard>{got.error ? <ErrorBanner error={got.error} /> : got.data ? children(got.data) : <Loading />}</SectionCard>
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
    <>
      <div className="mt-6 flex flex-wrap gap-1.5 first:mt-0">
        {o.source_priority.map((s, i) => (
          <Chip key={s}>
            {i + 1} <strong>{s}</strong>
          </Chip>
        ))}
      </div>
      <div className="mt-6 first:mt-0">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Entity ({num(entities.length)})</TableHead>
              <TableHead>Attributes</TableHead>
              <TableHead>Identity</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {entities.map(([name, spec]) => {
              const attrs = Object.entries(spec.attrs)
              return (
                <TableRow key={name}>
                  <TableCell className={cn(keyCol, 'whitespace-nowrap align-top')}>
                    {name} <span className="font-normal text-dbb-muted">{num(attrs.length)}</span>
                  </TableCell>
                  <TableCell className="align-top">
                    <span className="flex flex-wrap gap-1">
                      {attrs.map(([attr, type]) => (
                        <Chip key={attr} className="font-mono">
                          <strong>{attr}</strong>:{type}
                        </Chip>
                      ))}
                    </span>
                  </TableCell>
                  <TableCell className="whitespace-nowrap align-top">
                    {spec.identity.length === 0 ? (
                      '—'
                    ) : (
                      <span className="inline-flex flex-wrap gap-1">
                        {spec.identity.map((a) => (
                          <Pill key={a} tone="ok">
                            {a}
                          </Pill>
                        ))}
                      </span>
                    )}
                  </TableCell>
                </TableRow>
              )
            })}
          </TableBody>
        </Table>
      </div>
      <div className="mt-6 first:mt-0">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Relationship ({num(o.relationships.length)})</TableHead>
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
    </>
  )
}

function MappingsTab({ m }: { m: Mappings }) {
  const [source, setSource] = useState('')
  const [offset, setOffset] = useState(0)
  const [size, setSize] = useState(PAGE)
  const sources = [...new Set(m.lines.map((l) => l.source))].sort()
  const lines = source ? m.lines.filter((l) => l.source === source) : m.lines
  const page = lines.slice(offset, offset + size)
  const changeSize = (n: number) => {
    setSize(n)
    setOffset(0)
  }
  useEffect(() => {
    setOffset(0)
    setSize(PAGE)
  }, [m.lines])
  return (
    <>
      <div className="mt-6 first:mt-0">
        <div className="mb-3">
          <Select
            value={source || ALL}
            onValueChange={(v) => {
              setSource(v === ALL ? '' : v)
              setOffset(0)
            }}
          >
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
        </div>
        <Table className="table-fixed">
          <TableHeader>
            <TableRow>
              <TableHead className="w-28">Source ({num(lines.length)})</TableHead>
              <TableHead className="w-32">Source type</TableHead>
              <TableHead className="w-64">Path</TableHead>
              <TableHead className="w-48">Attribute</TableHead>
              <TableHead className="w-32">Transform</TableHead>
              <TableHead className="w-24">Origin</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {page.map((l) => (
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
        <Pager offset={offset} count={page.length} total={lines.length} onPage={setOffset} size={size} allSize={lines.length} onSize={changeSize} />
      </div>
      <div className="mt-6 first:mt-0">
        {m.hook_sources.length === 0 ? (
          <p className="text-sm text-dbb-muted">no hook sources</p>
        ) : (
          <div className="flex flex-wrap gap-1.5">
            {m.hook_sources.map((s) => (
              <Chip key={s}>
                <strong>{s}</strong>
              </Chip>
            ))}
          </div>
        )}
      </div>
    </>
  )
}

function TransformsTab({ t }: { t: Transforms }) {
  const [offset, setOffset] = useState(0)
  const [size, setSize] = useState(PAGE)
  const registry = Object.entries(t.registry)
  const labels = Object.entries(t.labels).sort(([a], [b]) => a.localeCompare(b))
  const page = labels.slice(offset, offset + size)
  const changeSize = (n: number) => {
    setSize(n)
    setOffset(0)
  }
  useEffect(() => {
    setOffset(0)
    setSize(PAGE)
  }, [t.labels])
  return (
    <>
      <div className="mt-6 first:mt-0">
        <Table className="table-fixed">
          <TableHeader>
            <TableRow>
              <TableHead className="w-56">Function ({num(registry.length)})</TableHead>
              <TableHead>Produces</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {registry.map(([fn, r]) => (
              <TableRow key={fn}>
                <TableCell className={keyCol}>
                  <Mono>{fn}</Mono>
                </TableCell>
                <TableCell>{r.produces}</TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>
      <div className="mt-6 first:mt-0">
        <Table className="table-fixed">
          <TableHeader>
            <TableRow>
              <TableHead className="w-56">Label ({num(labels.length)})</TableHead>
              <TableHead className="w-48">Function</TableHead>
              <TableHead className="w-48">Produces</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {page.map(([label, fn]) => (
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
        <Pager offset={offset} count={page.length} total={labels.length} onPage={setOffset} size={size} allSize={labels.length} onSize={changeSize} />
      </div>
    </>
  )
}

function MetricsTab({ m }: { m: MetricDefinitions }) {
  const [offset, setOffset] = useState(0)
  const [size, setSize] = useState(PAGE)
  const definitions = Object.entries(m.definitions)
  const page = definitions.slice(offset, offset + size)
  const changeSize = (n: number) => {
    setSize(n)
    setOffset(0)
  }
  useEffect(() => {
    setOffset(0)
    setSize(PAGE)
  }, [m.definitions])
  return (
    <>
      <Table className="table-fixed">
        <TableHeader>
          <TableRow>
            <TableHead className="w-56">Metric ({num(definitions.length)})</TableHead>
            <TableHead className="w-28">Entity</TableHead>
            <TableHead className="w-64">Expression</TableHead>
            <TableHead className="w-48">Filter</TableHead>
            <TableHead className="w-64">Kind</TableHead>
            <TableHead className="w-56">Raw fields</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {page.map(([name, d]) => {
            const p = m.provenance[name]
            return (
              <TableRow key={name}>
                <TableCell className="align-top">
                  <span className="block font-medium text-dbb-charcoal">{d.label}</span>
                  <Mono className="block">{name}</Mono>
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
                    <Pill tone="ok">observed</Pill>
                  )}
                </TableCell>
                <TableCell className="align-top">
                  {p && p.raw_fields.length > 0 ? (
                    <span className="flex flex-col items-start gap-1">
                      {p.raw_fields.map((f) => (
                        <Mono key={f}>{f}</Mono>
                      ))}
                    </span>
                  ) : (
                    '—'
                  )}
                </TableCell>
              </TableRow>
            )
          })}
        </TableBody>
      </Table>
      <Pager offset={offset} count={page.length} total={definitions.length} onPage={setOffset} size={size} allSize={definitions.length} onSize={changeSize} />
    </>
  )
}

function RulesTab({ r }: { r: Rules }) {
  const [offset, setOffset] = useState(0)
  const [size, setSize] = useState(PAGE)
  const rules = Object.entries(r.rules)
  const page = rules.slice(offset, offset + size)
  const changeSize = (n: number) => {
    setSize(n)
    setOffset(0)
  }
  useEffect(() => {
    setOffset(0)
    setSize(PAGE)
  }, [r.rules])
  return (
    <>
      <Table className="table-fixed">
        <TableHeader>
          <TableRow>
            <TableHead className="w-48">Rule ({num(rules.length)})</TableHead>
            <TableHead className="w-28">Entity</TableHead>
            <TableHead className="w-28">Severity</TableHead>
            <TableHead className="w-96">Conditions</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {page.map(([name, rule]) => (
            <TableRow key={name}>
              <TableCell className="align-top">
                <span className="block font-medium text-dbb-charcoal">{rule.label}</span>
                <Mono className="block">{name}</Mono>
              </TableCell>
              <TableCell className="align-top">{rule.entity}</TableCell>
              <TableCell className="align-top">
                <Pill tone={severityTone(rule.severity)}>{rule.severity}</Pill>
              </TableCell>
              <TableCell className="align-top">
                <span className="flex flex-col items-start gap-1">
                  {rule.all.flatMap(describe).map((text) => (
                    <Chip key={'all ' + text}>
                      all: <strong>{text}</strong>
                    </Chip>
                  ))}
                  {rule.any.flatMap(describe).map((text) => (
                    <Chip key={'any ' + text}>
                      any: <strong>{text}</strong>
                    </Chip>
                  ))}
                </span>
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
      <Pager offset={offset} count={page.length} total={rules.length} onPage={setOffset} size={size} allSize={rules.length} onSize={changeSize} />
    </>
  )
}

function GoalsTab({ g }: { g: Goals }) {
  const [offset, setOffset] = useState(0)
  const [size, setSize] = useState(PAGE)
  const goals = Object.entries(g.goals)
  const page = goals.slice(offset, offset + size)
  const changeSize = (n: number) => {
    setSize(n)
    setOffset(0)
  }
  useEffect(() => {
    setOffset(0)
    setSize(PAGE)
  }, [g.goals])
  return (
    <>
      <Table className="table-fixed">
        <TableHeader>
          <TableRow>
            <TableHead className="w-40">Goal ({num(goals.length)})</TableHead>
            <TableHead className="w-40">Metric</TableHead>
            <TableHead className="text-right w-24">Target</TableHead>
            <TableHead className="w-32">Strategy</TableHead>
            <TableHead className="w-64">Params</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {page.map(([name, goal]) => {
            const params = Object.entries(goal.params)
            return (
              <TableRow key={name}>
                <TableCell className="align-top">
                  <Mono>{name}</Mono>
                </TableCell>
                <TableCell className="align-top">
                  <Mono>{goal.metric}</Mono>
                </TableCell>
                <TableCell className="text-right align-top tabular-nums">{num(goal.target)}</TableCell>
                <TableCell className="align-top">{goal.strategy}</TableCell>
                <TableCell className="align-top">
                  {params.length > 0 ? (
                    <span className="flex flex-col items-start gap-1">
                      {params.map(([k, v]) => (
                        <Chip key={k}>
                          {k}=<strong>{paramValue(v)}</strong>
                        </Chip>
                      ))}
                    </span>
                  ) : (
                    '—'
                  )}
                </TableCell>
              </TableRow>
            )
          })}
        </TableBody>
      </Table>
      <Pager offset={offset} count={page.length} total={goals.length} onPage={setOffset} size={size} allSize={goals.length} onSize={changeSize} />
    </>
  )
}

function EnrichmentTab({ v }: { v: Vocabulary }) {
  return (
    <>
      <p className="mb-3 flex flex-wrap items-center gap-2 text-sm text-dbb-muted">
        <Enabled on={v.enabled} />
        <span>
          model <Mono>{v.model}</Mono>
        </span>
      </p>
      <Readings vocabulary={v} />
    </>
  )
}

export function Engine() {
  const ontology = useLoad(() => get<Ontology>('/api/knowledge/ontology'), [])
  const mappings = useLoad(() => get<Mappings>('/api/knowledge/mappings'), [])
  const transforms = useLoad(() => get<Transforms>('/api/knowledge/transforms'), [])
  const metrics = useLoad(() => get<MetricDefinitions>('/api/knowledge/metrics'), [])
  const rules = useLoad(() => get<Rules>('/api/knowledge/rules'), [])
  const goals = useLoad(() => get<Goals>('/api/knowledge/goals'), [])
  const vocabulary = useLoad(() => get<Vocabulary>('/api/enrichment/vocabulary'), [])

  return (
    <Tabs defaultValue="ontology">
      <TabsList>
        <TabsTrigger value="ontology">Ontology</TabsTrigger>
        <TabsTrigger value="mappings">Mappings</TabsTrigger>
        <TabsTrigger value="transforms">Transforms</TabsTrigger>
        <TabsTrigger value="metrics">Metrics</TabsTrigger>
        <TabsTrigger value="rules">Rules</TabsTrigger>
        <TabsTrigger value="goals">Goals</TabsTrigger>
        <TabsTrigger value="enrichment">Enrichment</TabsTrigger>
      </TabsList>
      <TabsContent value="ontology">
        <Loaded got={ontology}>{(o) => <OntologyTab o={o} />}</Loaded>
      </TabsContent>
      <TabsContent value="mappings">
        <Loaded got={mappings}>{(m) => <MappingsTab m={m} />}</Loaded>
      </TabsContent>
      <TabsContent value="transforms">
        <Loaded got={transforms}>{(t) => <TransformsTab t={t} />}</Loaded>
      </TabsContent>
      <TabsContent value="metrics">
        <Loaded got={metrics}>{(m) => <MetricsTab m={m} />}</Loaded>
      </TabsContent>
      <TabsContent value="rules">
        <Loaded got={rules}>{(r) => <RulesTab r={r} />}</Loaded>
      </TabsContent>
      <TabsContent value="goals">
        <Loaded got={goals}>{(g) => <GoalsTab g={g} />}</Loaded>
      </TabsContent>
      <TabsContent value="enrichment">
        <Loaded got={vocabulary}>{(v) => <EnrichmentTab v={v} />}</Loaded>
      </TabsContent>
    </Tabs>
  )
}
