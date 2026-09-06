import { useEffect, useState, type MouseEvent } from 'react'
import { asApiError, get, type ApiError } from '@/api'
import { SectionCard } from '@/components/SectionCard'
import { Section } from '@/components/SectionHeading'
import { ErrorBanner } from '@/components/ui/banner'
import { Empty } from '@/components/ui/empty'
import { Loading } from '@/components/ui/loading'
import { Mono } from '@/components/ui/mono'
import { Chip, Pill } from '@/components/ui/pill'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { STICKY_HEAD, Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { anchorText, num, relTime, short } from '@/lib/format'
import { useGet } from '@/lib/useGet'
import { cn } from '@/lib/utils'
import { VisualizeTab } from './visualize/VisualizeTab'

interface EntityRow {
  canonical_id: string
  entity_type: string
  anchor: string
  label: string
  members: number
  facts: Record<string, unknown>
}

interface EntitiesResponse {
  total: number
  limit: number
  offset: number
  by_type: Record<string, number>
  entities: EntityRow[]
}

interface Fact {
  attr: string
  value: unknown
  source: string | null
  raw_event_id: string | null
  observed_at: string
  disagreements: number
}

interface Member {
  source: string
  source_id: string
  object_type: string
  evidence: string
}

interface Link {
  rel: string
  from?: string
  to?: string
  grounding: string
}

interface EntityDetail {
  canonical_id: string
  entity_type: string
  anchor: string
  label: string
  resolved_from_alias: string | null
  aliases: string[]
  facts: Fact[]
  members: Member[]
  links: { out: Link[]; in: Link[] }
}

interface RetiredEntity {
  canonical_id: string
  retired: true
  detail: string
}

type EntityResponse = EntityDetail | RetiredEntity

interface RecordRow {
  source: string
  entity_type: string
  source_id: string
  object_type: string
  facts: Record<string, unknown>
}

interface RecordsResponse {
  total: number
  limit: number
  offset: number
  by_type: Record<string, number>
  entities: RecordRow[]
}

interface RawEvent {
  id: string
  seq: number
  source: string
  object_type: string
  source_id: string
  ingested_at: string
  raw_payload: unknown
}

interface RawResponse {
  total: number
  limit: number
  offset: number
  events: RawEvent[]
}

interface Trace {
  id: string
  source: string
  objectType?: string
}

const SCAN = 500
const ALL = '*'

const query = (params: Record<string, string | number | undefined>) =>
  Object.entries(params)
    .filter(([, v]) => v !== undefined && v !== '')
    .map(([k, v]) => `${k}=${encodeURIComponent(String(v))}`)
    .join('&')

const show = (v: unknown) =>
  v === null || v === undefined ? '—' : typeof v === 'object' ? JSON.stringify(v) : String(v)

const MONO = 'font-mono text-xs'
const NUM = 'text-right tabular-nums'
const KEY = 'font-medium text-dbb-charcoal'
const LINK = 'text-dbb-charcoal underline decoration-dotted decoration-dbb-muted underline-offset-2 hover:decoration-solid'
const ROW = 'cursor-pointer hover:bg-dbb-sand/50'
const PRE = 'mt-4 max-h-[480px] overflow-auto rounded-lg bg-dbb-surface p-3 font-mono text-xs'
const WRAP = 'break-words'
const PAGE_FILL = 'lg:flex lg:flex-col lg:h-[calc(100vh-11.25rem-1px)]'
const SPLIT_FILL = 'grid items-start gap-6 lg:grid-cols-[1.02fr_1.18fr] lg:grid-rows-[minmax(0,1fr)] lg:h-full'
const FILL = 'min-w-0 lg:flex lg:flex-col lg:max-h-full'
const FULL = 'min-w-0 lg:flex lg:flex-col lg:h-full'
const BODY = 'lg:min-h-0 lg:overflow-y-auto lg:-mx-6 lg:px-6 lg:-mb-6 lg:pb-6 lg:rounded-b-xl'

const labelText = (label: string, anchor: string) => (label === anchor ? anchorText(anchor) : label)

function Id({ id, full = false }: { id: string; full?: boolean }) {
  const [copied, setCopied] = useState(false)
  const copy = (e: MouseEvent) => {
    e.stopPropagation()
    navigator.clipboard
      .writeText(id)
      .then(() => {
        setCopied(true)
        setTimeout(() => setCopied(false), 1200)
      })
      .catch(() => {})
  }
  return (
    <button
      type="button"
      className={cn(MONO, 'whitespace-nowrap text-dbb-muted hover:text-dbb-charcoal')}
      title={`${id} — click to copy`}
      onClick={copy}
    >
      {full ? id : short(id)}
      {copied && (
        <Pill tone="ok" className="ml-1.5">
          copied
        </Pill>
      )}
    </button>
  )
}

function Evidence({ value }: { value: string }) {
  const at = value.indexOf('=')
  return (
    <Chip>
      {at < 0 ? value : `${value.slice(0, at)}=`}
      {at >= 0 && <strong>{value.slice(at + 1)}</strong>}
    </Chip>
  )
}

function Grounding({ value }: { value: string }) {
  const [kind, attr] = value.split(':', 2)
  return (
    <>
      <Pill>{kind}</Pill> <Mono>{attr ?? ''}</Mono>
    </>
  )
}

async function findRaw({ id, source, objectType }: Trace): Promise<RawEvent | null> {
  for (let offset = 0; ; offset += SCAN) {
    const page = await get<RawResponse>(`/api/raw?${query({ source, object_type: objectType, limit: SCAN, offset })}`)
    const hit = page.events.find((e) => e.id === id)
    if (hit) return hit
    if (page.events.length === 0 || offset + page.events.length >= page.total) return null
  }
}

function RawEventView({ event }: { event: RawEvent }) {
  return (
    <>
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead hint="Unique id of this raw event">Id</TableHead>
            <TableHead hint="Order in which we received it" className={NUM}>Seq</TableHead>
            <TableHead hint="The tool that sent this event">Source</TableHead>
            <TableHead hint="Kind of object the tool sent">Source type</TableHead>
            <TableHead hint="The tool's own id for this object">Source id</TableHead>
            <TableHead hint="When we stored the event">Ingested</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          <TableRow>
            <TableCell>
              <Id id={event.id} full />
            </TableCell>
            <TableCell className={NUM}>{num(event.seq)}</TableCell>
            <TableCell>
              <Mono>{event.source}</Mono>
            </TableCell>
            <TableCell>
              <Mono>{event.object_type}</Mono>
            </TableCell>
            <TableCell className={KEY}>
              <Mono>{event.source_id}</Mono>
            </TableCell>
            <TableCell title={event.ingested_at}>{relTime(event.ingested_at)}</TableCell>
          </TableRow>
        </TableBody>
      </Table>
      <pre className={PRE}>{JSON.stringify(event.raw_payload, null, 2)}</pre>
    </>
  )
}

function RawTrace({ trace }: { trace: Trace }) {
  const [state, setState] = useState<{ id: string; event: RawEvent | null; error: ApiError | null } | null>(null)
  useEffect(() => {
    let live = true
    findRaw(trace)
      .then((event) => live && setState({ id: trace.id, event, error: null }))
      .catch((e) => live && setState({ id: trace.id, event: null, error: asApiError(e) }))
    return () => {
      live = false
    }
  }, [trace])
  const done = state?.id === trace.id ? state : null
  const filter = query({ source: trace.source, object_type: trace.objectType })
  return (
    <Section title="Raw event">
      <p className={cn('mb-3 text-sm text-dbb-muted', WRAP)}>
        <Mono>{trace.id}</Mono> looked up by scanning <Mono>/api/raw?{filter}</Mono>
      </p>
      <ErrorBanner error={done?.error ?? null} className="mb-3" />
      {!done && <Empty>scanning…</Empty>}
      {done && !done.error && !done.event && <Empty>no raw event with that id under this filter</Empty>}
      {done?.event && <RawEventView event={done.event} />}
    </Section>
  )
}

function Detail({
  id,
  trace,
  onOpen,
  onTrace,
}: {
  id: string
  trace: Trace | null
  onOpen: (id: string) => void
  onTrace: (t: Trace) => void
}) {
  const detail = useGet<EntityResponse>(`/api/entities/${id}`)
  const [anchors, setAnchors] = useState<Record<string, string>>({})
  const d = detail.data && !('retired' in detail.data) ? detail.data : null
  const retired = detail.data && 'retired' in detail.data ? detail.data : null

  useEffect(() => {
    if (!d) return
    const ids = [...new Set([...d.links.out.map((l) => l.to), ...d.links.in.map((l) => l.from)])].filter(
      (x): x is string => !!x,
    )
    let live = true
    Promise.all(
      ids.map((i) =>
        get<EntityResponse>(`/api/entities/${i}`)
          .then((r) => [i, 'retired' in r ? 'retired' : labelText(r.label, r.anchor)] as const)
          .catch(() => [i, ''] as const),
      ),
    ).then((pairs) => live && setAnchors(Object.fromEntries(pairs)))
    return () => {
      live = false
    }
  }, [d])

  const objectTypeFor = (source: string) => {
    const types = new Set(d?.members.filter((m) => m.source === source).map((m) => m.object_type))
    return types.size === 1 ? [...types][0] : undefined
  }

  const links = d
    ? [
        ...d.links.out.map((l) => ({ dir: 'out', rel: l.rel, other: l.to ?? '', grounding: l.grounding })),
        ...d.links.in.map((l) => ({ dir: 'in', rel: l.rel, other: l.from ?? '', grounding: l.grounding })),
      ]
    : []

  return (
    <SectionCard title={d ? labelText(d.label, d.anchor) : 'Entity'} className={FILL} bodyClassName={BODY} testId="entity-detail">
      <ErrorBanner error={detail.error} className="mb-3" />
      {detail.loading && !detail.data && <Loading />}
      {retired && (
        <p className="text-sm text-dbb-muted">
          <Pill tone="warn">retired</Pill> {retired.detail}
        </p>
      )}
      {d && (
        <>
          {(d.resolved_from_alias || d.aliases.length > 0) && (
            <div className="space-y-1 text-sm text-dbb-muted">
              {d.resolved_from_alias && (
                <p>
                  <Pill tone="warn">alias</Pill> resolved from <Mono>{d.resolved_from_alias}</Mono>
                </p>
              )}
              {d.aliases.length > 0 && (
                <p>
                  aliases:{' '}
                  {d.aliases.map((a) => (
                    <Mono key={a}>{a} </Mono>
                  ))}
                </p>
              )}
            </div>
          )}
          <div className="mt-6 first:mt-0">
            <Table data-testid="detail-sources">
              <TableHeader>
                <TableRow>
                  <TableHead hint="A tool holding a record of this entity">Source ({num(d.members.length)})</TableHead>
                  <TableHead hint="The tool's own id for that record">Source id</TableHead>
                  <TableHead hint="Kind of object the tool holds">Source type</TableHead>
                  <TableHead hint="The values used to match this record in">Evidence</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {d.members.map((m) => (
                  <TableRow key={`${m.source}|${m.object_type}|${m.source_id}`}>
                    <TableCell>
                      <Mono>{m.source}</Mono>
                    </TableCell>
                    <TableCell className={KEY}>
                      <Mono>{m.source_id}</Mono>
                    </TableCell>
                    <TableCell>
                      <Mono>{m.object_type}</Mono>
                    </TableCell>
                    <TableCell>
                      <Evidence value={m.evidence} />
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
          <div className="mt-6 first:mt-0">
            {d.facts.length === 0 ? (
              <Empty>no facts</Empty>
            ) : (
              <Table data-testid="detail-facts">
                <TableHeader>
                  <TableRow>
                    <TableHead hint="One attribute of this entity" className="w-[100px] min-w-[100px]">Fact ({num(d.facts.length)})</TableHead>
                    <TableHead hint="The value we kept for this attribute">Value</TableHead>
                    <TableHead hint="The tool whose value we kept">Winning source</TableHead>
                    <TableHead hint="When the winning value was seen">Observed</TableHead>
                    <TableHead hint="How many other tools gave a different value" className={NUM}>Disagreements</TableHead>
                    <TableHead hint="The event the winning value came from">Raw event</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {d.facts.map((f) => {
                    const { raw_event_id: rid, source } = f
                    return (
                      <TableRow key={f.attr}>
                        <TableCell className={cn(KEY, 'whitespace-nowrap')}>
                          <Mono>{f.attr}</Mono>
                        </TableCell>
                        <TableCell>
                          <span className={cn('block max-w-[40ch]', WRAP)}>{show(f.value)}</span>
                        </TableCell>
                        <TableCell>{source ? <Mono>{source}</Mono> : '—'}</TableCell>
                        <TableCell className="whitespace-nowrap" title={f.observed_at}>
                          {relTime(f.observed_at)}
                        </TableCell>
                        <TableCell className={NUM}>
                          {f.disagreements > 0 ? <Pill tone="warn">{num(f.disagreements)}</Pill> : '0'}
                        </TableCell>
                        <TableCell>
                          {rid && source ? (
                            <button
                              type="button"
                              className={cn(LINK, MONO)}
                              title={`${rid} — open raw event`}
                              onClick={() => onTrace({ id: rid, source, objectType: objectTypeFor(source) })}
                            >
                              {short(rid)}
                            </button>
                          ) : (
                            '—'
                          )}
                        </TableCell>
                      </TableRow>
                    )
                  })}
                </TableBody>
              </Table>
            )}
          </div>
          <div className="mt-6 first:mt-0">
            {links.length === 0 ? (
              <Empty>no links</Empty>
            ) : (
              <Table data-testid="detail-links">
                <TableHeader>
                  <TableRow>
                    <TableHead hint="Whether the link points out from here or in">Link ({num(links.length)})</TableHead>
                    <TableHead hint="How the two entities are related">Relationship</TableHead>
                    <TableHead hint="The other entity in the relationship">Target</TableHead>
                    <TableHead hint="The kind and field that back this link">Grounding</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {links.map((l) => (
                    <TableRow key={`${l.dir}|${l.rel}|${l.other}`}>
                      <TableCell>
                        <Pill>{l.dir}</Pill>
                      </TableCell>
                      <TableCell>
                        <Mono>{l.rel}</Mono>
                      </TableCell>
                      <TableCell>
                        <button type="button" className={LINK} title={l.other} onClick={() => onOpen(l.other)}>
                          {anchors[l.other] || short(l.other)}
                        </button>
                      </TableCell>
                      <TableCell className="whitespace-nowrap">
                        <Grounding value={l.grounding} />
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            )}
          </div>
          {trace && <RawTrace trace={trace} />}
        </>
      )}
    </SectionCard>
  )
}

function Canonical() {
  const [type, setType] = useState('')
  const [selected, setSelected] = useState<string | null>(null)
  const [trace, setTrace] = useState<Trace | null>(null)
  const list = useGet<EntitiesResponse>(`/api/entities?${query({ entity_type: type, limit: SCAN })}`)

  const pick = (t: string) => setType(t)
  const open = (id: string) => {
    setSelected(id)
    setTrace(null)
  }

  const byType = Object.entries(list.data?.by_type ?? {})
  const all = byType.reduce((n, [, c]) => n + c, 0)
  const rows = list.data?.entities ?? []

  return (
    <div className={SPLIT_FILL}>
      <SectionCard
        title="Canonical entities"
        testId="entities"
        headerRight={
          <Select value={type || ALL} onValueChange={(v) => pick(v === ALL ? '' : v)}>
            <SelectTrigger className="h-6 w-44" data-testid="entities-type-filter">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value={ALL} data-testid="entities-type-filter-option" data-value={ALL}>
                all types ({num(all)})
              </SelectItem>
              {byType.map(([t, n]) => (
                <SelectItem key={t} value={t} data-testid="entities-type-filter-option" data-value={t}>
                  {t} ({num(n)})
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        }
        className={FULL}
        bodyClassName={BODY}
      >
        <ErrorBanner error={list.error} className="mb-3" />
        {list.loading && !list.data ? (
          <Loading />
        ) : rows.length === 0 ? (
          <Empty>no entities</Empty>
        ) : (
          <Table className="table-fixed" wrapperClassName="overflow-x-visible" data-testid="entities-table">
            <TableHeader className={STICKY_HEAD}>
              <TableRow>
                <TableHead hint="The thing's name, merged across tools" className="w-28">Entity ({num(list.data?.total ?? rows.length)})</TableHead>
                <TableHead hint="Source, type and id that pin this entity" className="w-64">Anchor</TableHead>
                <TableHead hint="How many tools hold a record of it" className={cn(NUM, 'w-24')}>Sources</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {rows.map((r) => {
                return (
                  <TableRow
                    key={r.canonical_id}
                    className={ROW}
                    data-testid="entities-row"
                    data-id={r.canonical_id}
                    data-state={r.canonical_id === selected ? 'selected' : undefined}
                    aria-selected={r.canonical_id === selected}
                    onClick={() => open(r.canonical_id)}
                  >
                    <TableCell>
                      <Pill>{r.entity_type}</Pill>
                    </TableCell>
                    <TableCell className={KEY}>
                      {labelText(r.label, r.anchor)}
                      {r.label !== r.anchor ? <span className={cn(MONO, 'block font-normal text-dbb-muted')}>{anchorText(r.anchor)}</span> : null}
                    </TableCell>
                    <TableCell className={NUM}>{num(r.members)}</TableCell>
                  </TableRow>
                )
              })}
            </TableBody>
          </Table>
        )}
        {list.data && list.data.total > rows.length && (
          <p className="mt-3 text-sm text-dbb-muted">
            showing the first {num(rows.length)} of {num(list.data.total)}
          </p>
        )}
      </SectionCard>
      {selected ? (
        <Detail id={selected} trace={trace} onOpen={open} onTrace={setTrace} />
      ) : (
        <SectionCard className={FILL} bodyClassName={BODY} testId="entity-detail">
          <Empty>select an entity</Empty>
        </SectionCard>
      )}
    </div>
  )
}

async function eventsFor(source: string, objectType: string, sourceId: string): Promise<RawEvent[]> {
  const hits: RawEvent[] = []
  for (let offset = 0; ; offset += SCAN) {
    const page = await get<RawResponse>(`/api/raw?${query({ source, object_type: objectType, limit: SCAN, offset })}`)
    hits.push(...page.events.filter((e) => e.source_id === sourceId))
    if (page.events.length === 0 || offset + page.events.length >= page.total) return hits
  }
}

function RecordDetail({ record }: { record: RecordRow }) {
  const key = `${record.source}|${record.object_type}|${record.source_id}`
  const [state, setState] = useState<{ key: string; events: RawEvent[]; error: ApiError | null } | null>(null)
  const [pickedId, setPickedId] = useState<string | null>(null)

  useEffect(() => {
    let live = true
    setPickedId(null)
    eventsFor(record.source, record.object_type, record.source_id)
      .then((events) => live && setState({ key, events, error: null }))
      .catch((e) => live && setState({ key, events: [], error: asApiError(e) }))
    return () => {
      live = false
    }
  }, [key])

  const current = state?.key === key ? state : null
  const events = current?.events ?? []
  const picked = events.find((e) => e.id === pickedId) ?? events[0] ?? null
  const facts = Object.entries(record.facts)

  return (
    <SectionCard title={record.source_id} className={FILL} bodyClassName={BODY} testId="record-detail">
      <ErrorBanner error={current?.error ?? null} className="mb-3" />
      <div className="mt-6 first:mt-0">
        {facts.length === 0 ? (
          <Empty>no facts</Empty>
        ) : (
          <Table data-testid="record-facts">
            <TableHeader>
              <TableRow>
                <TableHead hint="One attribute this tool holds" className="w-[100px] min-w-[100px]">Fact ({num(facts.length)})</TableHead>
                <TableHead hint="The value the tool holds for it">Value</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {facts.map(([k, v]) => (
                <TableRow key={k}>
                  <TableCell className={cn(KEY, 'whitespace-nowrap')}>
                    <Mono>{k}</Mono>
                  </TableCell>
                  <TableCell className={WRAP}>{show(v)}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )}
      </div>
      <div className="mt-6 first:mt-0">
        {!current && <Loading />}
        {current && events.length === 0 && <Empty>no raw events</Empty>}
        {events.length > 0 && (
          <Table className="table-fixed" data-testid="record-events">
            <TableHeader>
              <TableRow>
                <TableHead hint="One payload exactly as the tool sent it">Raw event ({num(events.length)})</TableHead>
                <TableHead hint="When we stored the event" className="w-32">Ingested</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {events.map((e) => (
                <TableRow
                  key={e.id}
                  className={ROW}
                  data-state={picked?.id === e.id ? 'selected' : undefined}
                  aria-selected={picked?.id === e.id}
                  onClick={() => setPickedId(e.id)}
                >
                  <TableCell>
                    <Id id={e.id} full />
                  </TableCell>
                  <TableCell className="whitespace-nowrap" title={e.ingested_at}>
                    {relTime(e.ingested_at)}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )}
      </div>
      {picked && (
        <Section title="Payload">
          <p className="mb-3 text-sm text-dbb-muted">The event exactly as the source delivered it, before any mapping, transform, or merge.</p>
          <pre className={cn(PRE, 'mt-0')} data-testid="record-payload">
            {JSON.stringify(picked.raw_payload, null, 2)}
          </pre>
        </Section>
      )}
    </SectionCard>
  )
}

function RawSide() {
  const [type, setType] = useState('')
  const [source, setSource] = useState('')
  const [sources, setSources] = useState<string[]>([])
  const [picked, setPicked] = useState<RecordRow | null>(null)
  const records = useGet<RecordsResponse>(`/api/records?${query({ entity_type: type, source, limit: SCAN })}`)
  const rows = records.data?.entities ?? []
  const byType = Object.entries(records.data?.by_type ?? {})

  useEffect(() => {
    if (!source && records.data) setSources([...new Set(records.data.entities.map((r) => r.source))].sort())
  }, [source, records.data])

  const isPicked = (r: RecordRow) =>
    picked?.source === r.source && picked?.object_type === r.object_type && picked?.source_id === r.source_id

  return (
    <div className={SPLIT_FILL}>
      <SectionCard
        title="Records"
        testId="records"
        headerRight={
          <div className="flex items-center gap-2">
            <Select value={type || ALL} onValueChange={(v) => setType(v === ALL ? '' : v)}>
              <SelectTrigger className="h-6 w-40" data-testid="records-type-filter">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value={ALL} data-testid="records-type-filter-option" data-value={ALL}>
                  all types
                </SelectItem>
                {byType.map(([t, n]) => (
                  <SelectItem key={t} value={t} data-testid="records-type-filter-option" data-value={t}>
                    {t} ({num(n)})
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            <Select value={source || ALL} onValueChange={(v) => setSource(v === ALL ? '' : v)}>
              <SelectTrigger className="h-6 w-40" data-testid="records-source-filter">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value={ALL} data-testid="records-source-filter-option" data-value={ALL}>
                  all sources
                </SelectItem>
                {sources.map((s) => (
                  <SelectItem key={s} value={s} data-testid="records-source-filter-option" data-value={s}>
                    {s}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
        }
        className={FULL}
        bodyClassName={BODY}
      >
        <ErrorBanner error={records.error} className="mb-3" />
        {records.loading && !records.data ? (
          <Loading />
        ) : rows.length === 0 ? (
          <Empty>no records</Empty>
        ) : (
          <Table className="table-fixed" wrapperClassName="overflow-x-visible" data-testid="records-table">
            <TableHeader className={STICKY_HEAD}>
              <TableRow>
                <TableHead hint="The tool this record came from" className="w-28">Source ({num(records.data?.total ?? rows.length)})</TableHead>
                <TableHead hint="The tool's own id for this record" className="w-36">Source id</TableHead>
                <TableHead hint="Kind of object the tool holds" className="w-28">Source type</TableHead>
                <TableHead hint="What kind of thing this record describes" className="w-24">Entity</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {rows.map((r, i) => (
                <TableRow
                  key={`${r.source}|${r.object_type}|${r.source_id}|${i}`}
                  className={ROW}
                  data-testid="records-row"
                  data-state={isPicked(r) ? 'selected' : undefined}
                  aria-selected={isPicked(r)}
                  onClick={() => setPicked(r)}
                >
                  <TableCell>
                    <Mono>{r.source}</Mono>
                  </TableCell>
                  <TableCell className={KEY}>
                    <Mono>{r.source_id}</Mono>
                  </TableCell>
                  <TableCell>
                    <Mono>{r.object_type}</Mono>
                  </TableCell>
                  <TableCell>
                    <Pill>{r.entity_type}</Pill>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )}
        {records.data && records.data.total > rows.length && (
          <p className="mt-3 text-sm text-dbb-muted">
            showing the first {num(rows.length)} of {num(records.data.total)}
          </p>
        )}
      </SectionCard>
      {picked ? (
        <RecordDetail record={picked} />
      ) : (
        <SectionCard className={FILL} bodyClassName={BODY} testId="record-detail">
          <Empty>select a record</Empty>
        </SectionCard>
      )}
    </div>
  )
}

export function Entities() {
  return (
    <Tabs defaultValue="canonical" className={PAGE_FILL}>
      <TabsList className="shrink-0">
        <TabsTrigger value="canonical" data-testid="tab-canonical">
          Canonical
        </TabsTrigger>
        <TabsTrigger value="raw" data-testid="tab-raw">
          Raw entities
        </TabsTrigger>
        <TabsTrigger value="visualize" data-testid="tab-visualize">
          Visualize
        </TabsTrigger>
      </TabsList>
      <TabsContent value="canonical" className="lg:min-h-0 lg:flex-1" data-testid="tabpanel-canonical">
        <Canonical />
      </TabsContent>
      <TabsContent value="raw" className="lg:min-h-0 lg:flex-1" data-testid="tabpanel-raw">
        <RawSide />
      </TabsContent>
      <TabsContent value="visualize" className="lg:min-h-0 lg:flex-1" data-testid="tabpanel-visualize">
        <VisualizeTab />
      </TabsContent>
    </Tabs>
  )
}
