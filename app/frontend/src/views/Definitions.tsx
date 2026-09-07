import { useEffect, useState, type ReactNode } from 'react'
import { useSearchParams } from 'react-router-dom'
import { get } from '@/api'
import { ALL } from '@/components/Filter'
import { SectionCard } from '@/components/SectionCard'
import { ErrorBanner } from '@/components/ui/banner'
import { Loading } from '@/components/ui/loading'
import { Mono } from '@/components/ui/mono'
import { PAGE, Pager } from '@/components/ui/pager'
import { Chip, Pill, type Tone } from '@/components/ui/pill'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { STICKY_HEAD, Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { num } from '@/lib/format'
import { useScrollTo } from '@/lib/useScrollTo'
import { useTab } from '@/lib/useTab'
import { cn } from '@/lib/utils'
import { DEFINITIONS_ROUTE } from '@/routes'
import { useLoad } from './inference/shared'
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
const PAGE_FILL = 'lg:flex lg:flex-col lg:h-[calc(100vh-11.25rem-1px)]'
const TAB_FILL = 'lg:min-h-0 lg:flex-1 lg:overflow-y-auto'
const FILL = 'min-w-0 lg:flex lg:h-full lg:flex-col lg:min-h-0'
const BODY = 'lg:min-h-0 lg:overflow-y-auto lg:-mx-6 lg:px-6 lg:-mb-6 lg:pb-6 lg:rounded-b-xl'

const severityTone = (s: string): Tone => (s === 'high' ? 'err' : s === 'medium' ? 'warn' : 'neutral')

const describe = (c: Condition) =>
  Object.entries(c)
    .filter(([k]) => k !== 'attr')
    .map(([op, v]) => `${c.attr} ${op} ${JSON.stringify(v)}`)

const paramValue = (v: unknown) => (typeof v === 'number' ? num(v) : String(v))

const marked = (name: string, selected: string | null) => ({
  'data-name': name,
  'data-state': name === selected ? 'selected' : undefined,
  'aria-selected': name === selected,
})

function useSelected(table: string, param: string) {
  const [params] = useSearchParams()
  const selected = params.get(param)
  useScrollTo(table, 'name', selected)
  return selected
}

function Loaded<T>({ got, children }: { got: ReturnType<typeof useLoad<T>>; children: (d: T) => ReactNode }) {
  if (got.error)
    return (
      <SectionCard>
        <ErrorBanner error={got.error} />
      </SectionCard>
    )
  if (!got.data)
    return (
      <SectionCard>
        <Loading />
      </SectionCard>
    )
  return children(got.data)
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
  const selected = useSelected('definitions-ontology-table', 'type')
  const entities = Object.entries(o.entities)
  return (
    <div className="space-y-6">
      <SectionCard
        title="Source priority"
        testId="source-priority"
        description="When sources disagree on an attribute, the most recently observed value wins. If they were observed at the same time, the source with the lower number wins: 1 beats 2."
      >
        <div className="flex flex-wrap gap-1.5">
          {o.source_priority.map((s, i) => (
            <Chip key={s}>
              {i + 1} <strong>{s}</strong>
            </Chip>
          ))}
        </div>
      </SectionCard>
      <SectionCard testId="definitions-ontology">
        <Table data-testid="definitions-ontology-table">
          <TableHeader>
            <TableRow>
              <TableHead hint="One kind of record, with its attribute count">Entity ({num(entities.length)})</TableHead>
              <TableHead hint="Fields this kind can carry, each with its type">Attributes</TableHead>
              <TableHead hint="Attributes that tell one apart from another">Identity</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {entities.map(([name, spec]) => {
              const attrs = Object.entries(spec.attrs)
              return (
                <TableRow key={name} {...marked(name, selected)}>
                  <TableCell className={cn(keyCol, 'whitespace-nowrap align-top')}>
                    <Pill>{name}</Pill> <span className="font-normal text-dbb-muted">{num(attrs.length)}</span>
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
      </SectionCard>
      <SectionCard testId="definitions-relationships">
        <Table data-testid="definitions-relationships-table">
          <TableHeader>
            <TableRow>
              <TableHead hint="Name of the link between two record kinds">Relationship ({num(o.relationships.length)})</TableHead>
              <TableHead hint="The kind of record the link starts from">From</TableHead>
              <TableHead hint="The kind of record the link points to">To</TableHead>
              <TableHead hint="How many on each side, like many to one">Cardinality</TableHead>
              <TableHead hint="Which attribute connects the two, by reference or match">Grounding</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {o.relationships.map((r) => (
              <TableRow key={`${r.rel}|${r.from}|${r.to}`}>
                <TableCell className={keyCol}>
                  <Mono>{r.rel}</Mono>
                </TableCell>
                <TableCell>
                  <Pill>{r.from}</Pill>
                </TableCell>
                <TableCell>
                  <Pill>{r.to}</Pill>
                </TableCell>
                <TableCell>{r.cardinality}</TableCell>
                <TableCell>
                  <Grounding value={r.grounding} />
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </SectionCard>
    </div>
  )
}

function MappingsTab({ m }: { m: Mappings }) {
  const [source, setSource] = useState('')
  const bySource = new Map<string, number>()
  for (const l of m.lines) bySource.set(l.source, (bySource.get(l.source) ?? 0) + 1)
  const sources = [...bySource.keys()].sort()
  const lines = source ? m.lines.filter((l) => l.source === source) : m.lines
  return (
      <SectionCard
        title={
          <Select value={source || ALL} onValueChange={(v) => setSource(v === ALL ? '' : v)}>
            <SelectTrigger className="h-6 w-48 font-normal" data-testid="mappings-source-filter">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value={ALL} data-testid="mappings-source-filter-option" data-value={ALL}>
                all sources ({num(m.lines.length)})
              </SelectItem>
              {sources.map((s) => (
                <SelectItem key={s} value={s} data-testid="mappings-source-filter-option" data-value={s}>
                  {s} ({num(bySource.get(s) ?? 0)})
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        }
        className={FILL}
        bodyClassName={BODY}
        testId="definitions-mappings"
      >
        <Table className="table-fixed" wrapperClassName="overflow-x-visible" data-testid="definitions-mappings-table">
          <TableHeader className={STICKY_HEAD}>
            <TableRow>
              <TableHead className="w-28" hint="The tool the data comes from">Source ({num(lines.length)})</TableHead>
              <TableHead className="w-32" hint="The object kind inside that tool, like contacts">Source type</TableHead>
              <TableHead className="w-64" hint="Where in the tool's payload the value lives">Path</TableHead>
              <TableHead className="w-48" hint="The record kind and field this value fills">Attribute</TableHead>
              <TableHead className="w-32" hint="The function that cleans the value before storing">Transform</TableHead>
              <TableHead className="w-24" hint="Straight from the payload, or computed by a hook">Origin</TableHead>
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
      </SectionCard>
  )
}

function TransformsTab({ t }: { t: Transforms }) {
  const [offset, setOffset] = useState(0)
  const [size, setSize] = useState(PAGE * 2)
  const registry = Object.entries(t.registry)
  const labels = Object.entries(t.labels).sort(([a], [b]) => a.localeCompare(b))
  const page = labels.slice(offset, offset + size)
  const changeSize = (n: number) => {
    setSize(n)
    setOffset(0)
  }
  useEffect(() => {
    setOffset(0)
    setSize(PAGE * 2)
  }, [t.labels])
  return (
    <div className="space-y-6">
      <SectionCard testId="definitions-transforms">
        <Table className="table-fixed" data-testid="definitions-transforms-table">
          <TableHeader>
            <TableRow>
              <TableHead className="w-56" hint="The attribute name this cleanup applies to">Label ({num(labels.length)})</TableHead>
              <TableHead className="w-48" hint="The code that cleans values for this label">Function</TableHead>
              <TableHead className="w-48" hint="The kind of value that comes out, like date">Produces</TableHead>
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
        <Pager
          offset={offset}
          count={page.length}
          total={labels.length}
          onPage={setOffset}
          size={size}
          allSize={labels.length}
          onSize={changeSize}
          pageSize={PAGE * 2}
        />
      </SectionCard>
      <SectionCard testId="definitions-transforms-functions">
        <Table className="table-fixed" data-testid="definitions-transforms-functions-table">
          <TableHeader>
            <TableRow>
              <TableHead className="w-56" hint="Every cleanup function the system can apply">Function ({num(registry.length)})</TableHead>
              <TableHead hint="The kind of value that comes out, like number">Produces</TableHead>
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
      </SectionCard>
    </div>
  )
}

function MetricsTab({ m }: { m: MetricDefinitions }) {
  const selected = useSelected('definitions-metrics-table', 'metric')
  const definitions = Object.entries(m.definitions)
  return (
    <SectionCard className={FILL} bodyClassName={BODY} testId="definitions-metrics">
      <Table className="table-fixed" wrapperClassName="overflow-x-visible" data-testid="definitions-metrics-table">
        <TableHeader className={STICKY_HEAD}>
          <TableRow>
            <TableHead className="w-56" hint="The measure's display name and its internal key">Metric ({num(definitions.length)})</TableHead>
            <TableHead className="w-28" hint="The kind of record the measure is computed over">Entity</TableHead>
            <TableHead className="w-64" hint="How the number is computed, like SUM(amount)">Expression</TableHead>
            <TableHead className="w-48" hint="Only records matching these values are counted">Filter</TableHead>
            <TableHead className="w-48" hint="Observed from tool data, or inferred by the model">Kind</TableHead>
            <TableHead className="w-48" hint="The tool fields this number is read from">Raw fields</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {definitions.map(([name, d]) => {
            const p = m.provenance[name]
            return (
              <TableRow key={name} {...marked(name, selected)}>
                <TableCell className="align-top">
                  <span className="block font-medium text-dbb-charcoal">{d.label}</span>
                  <Mono className="block">{name}</Mono>
                </TableCell>
                <TableCell className="align-top">
                  <Pill>{d.entity}</Pill>
                </TableCell>
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
    </SectionCard>
  )
}

function RulesTab({ r }: { r: Rules }) {
  const selected = useSelected('definitions-rules-table', 'rule')
  const rules = Object.entries(r.rules)
  return (
    <SectionCard className={FILL} bodyClassName={BODY} testId="definitions-rules">
      <Table className="table-fixed" wrapperClassName="overflow-x-visible" data-testid="definitions-rules-table">
        <TableHeader className={STICKY_HEAD}>
          <TableRow>
            <TableHead className="w-96" hint="The check's display name and its internal key">Rule ({num(rules.length)})</TableHead>
            <TableHead className="w-28" hint="The kind of record the check looks at">Entity</TableHead>
            <TableHead className="w-28" hint="How serious a finding from this check is">Severity</TableHead>
            <TableHead className="w-48" hint="What must be true for the rule to fire">Conditions</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {rules.map(([name, rule]) => (
            <TableRow key={name} {...marked(name, selected)}>
              <TableCell className="align-top">
                <span className="block font-medium text-dbb-charcoal">{rule.label}</span>
                <Mono className="block">{name}</Mono>
              </TableCell>
              <TableCell className="align-top">
                <Pill>{rule.entity}</Pill>
              </TableCell>
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
    </SectionCard>
  )
}

function GoalsTab({ g }: { g: Goals }) {
  const selected = useSelected('definitions-goals-table', 'goal')
  const goals = Object.entries(g.goals)
  return (
    <SectionCard className={FILL} bodyClassName={BODY} testId="definitions-goals">
      <Table className="table-fixed" wrapperClassName="overflow-x-visible" data-testid="definitions-goals-table">
        <TableHeader className={STICKY_HEAD}>
          <TableRow>
            <TableHead className="w-40" hint="The goal's internal key">Goal ({num(goals.length)})</TableHead>
            <TableHead className="w-40" hint="The measure the goal tracks">Metric</TableHead>
            <TableHead className="text-right w-24" hint="The number the metric is measured against">Target</TableHead>
            <TableHead className="w-32" hint="How met or missed is decided against the target">Strategy</TableHead>
            <TableHead className="w-64" hint="Extra settings the strategy uses, like band limits">Params</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {goals.map(([name, goal]) => {
            const params = Object.entries(goal.params)
            return (
              <TableRow key={name} {...marked(name, selected)}>
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
    </SectionCard>
  )
}

function EnrichmentTab({ v }: { v: Vocabulary }) {
  const selected = useSelected('definitions-enrichment-table', 'reading')
  return (
    <SectionCard className={FILL} bodyClassName={BODY} testId="definitions-enrichment">
      <Readings vocabulary={v} sticky testId="definitions-enrichment-table" selected={selected} />
    </SectionCard>
  )
}

export function Definitions() {
  const ontology = useLoad(() => get<Ontology>('/api/definitions/ontology'), [])
  const mappings = useLoad(() => get<Mappings>('/api/definitions/mappings'), [])
  const transforms = useLoad(() => get<Transforms>('/api/definitions/transforms'), [])
  const metrics = useLoad(() => get<MetricDefinitions>('/api/definitions/metrics'), [])
  const rules = useLoad(() => get<Rules>('/api/definitions/rules'), [])
  const goals = useLoad(() => get<Goals>('/api/definitions/goals'), [])
  const vocabulary = useLoad(() => get<Vocabulary>('/api/enrichment/vocabulary'), [])
  const [tab, setTab] = useTab(DEFINITIONS_ROUTE)

  return (
    <Tabs value={tab} onValueChange={setTab} className={PAGE_FILL}>
      <TabsList className="shrink-0">
        <TabsTrigger value="ontology" data-testid="tab-ontology">
          Ontology
        </TabsTrigger>
        <TabsTrigger value="mappings" data-testid="tab-mappings">
          Mappings
        </TabsTrigger>
        <TabsTrigger value="transforms" data-testid="tab-transforms">
          Transforms
        </TabsTrigger>
        <TabsTrigger value="metrics" data-testid="tab-metrics">
          Metrics
        </TabsTrigger>
        <TabsTrigger value="rules" data-testid="tab-rules">
          Rules
        </TabsTrigger>
        <TabsTrigger value="goals" data-testid="tab-goals">
          Goals
        </TabsTrigger>
        <TabsTrigger value="enrichment" data-testid="tab-enrichment">
          Enrichment
        </TabsTrigger>
      </TabsList>
      <TabsContent value="ontology" className={TAB_FILL} data-testid="tabpanel-ontology">
        <Loaded got={ontology}>{(o) => <OntologyTab o={o} />}</Loaded>
      </TabsContent>
      <TabsContent value="mappings" className={TAB_FILL} data-testid="tabpanel-mappings">
        <Loaded got={mappings}>{(m) => <MappingsTab m={m} />}</Loaded>
      </TabsContent>
      <TabsContent value="transforms" className={TAB_FILL} data-testid="tabpanel-transforms">
        <Loaded got={transforms}>{(t) => <TransformsTab t={t} />}</Loaded>
      </TabsContent>
      <TabsContent value="metrics" className={TAB_FILL} data-testid="tabpanel-metrics">
        <Loaded got={metrics}>{(m) => <MetricsTab m={m} />}</Loaded>
      </TabsContent>
      <TabsContent value="rules" className={TAB_FILL} data-testid="tabpanel-rules">
        <Loaded got={rules}>{(r) => <RulesTab r={r} />}</Loaded>
      </TabsContent>
      <TabsContent value="goals" className={TAB_FILL} data-testid="tabpanel-goals">
        <Loaded got={goals}>{(g) => <GoalsTab g={g} />}</Loaded>
      </TabsContent>
      <TabsContent value="enrichment" className={TAB_FILL} data-testid="tabpanel-enrichment">
        <Loaded got={vocabulary}>{(v) => <EnrichmentTab v={v} />}</Loaded>
      </TabsContent>
    </Tabs>
  )
}
