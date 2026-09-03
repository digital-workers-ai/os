import { useEffect, useState, type MouseEvent } from 'react'
import { createPortal } from 'react-dom'
import { asApiError, get, type ApiError } from '@/api'
import { HEADING_RIGHT_ID } from '@/components/Layout'
import { SectionCard } from '@/components/SectionCard'
import { Section } from '@/components/SectionHeading'
import { ErrorBanner } from '@/components/ui/banner'
import { Empty } from '@/components/ui/empty'
import { Loading } from '@/components/ui/loading'
import { Input } from '@/components/ui/input'
import { Mono } from '@/components/ui/mono'
import { PAGE, Pager } from '@/components/ui/pager'
import { FilterChip, Pill } from '@/components/ui/pill'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { num, relTime, short } from '@/lib/format'
import { cn } from '@/lib/utils'

interface EntityRow {
  canonical_id: string
  entity_type: string
  anchor: string
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
const SPLIT = 'grid gap-6 lg:grid-cols-[1fr_1.2fr]'
const PAGE_FILL = 'lg:flex lg:flex-col lg:h-[calc(100vh-11.25rem-1px)]'
const SPLIT_FILL = 'grid items-start gap-6 lg:grid-cols-[1.2fr_1fr] lg:grid-rows-[minmax(0,1fr)] lg:flex-1 lg:min-h-0'
const FILL = 'min-w-0 lg:flex lg:flex-col lg:max-h-full'
const BODY = 'lg:min-h-0 lg:overflow-y-auto lg:-mx-6 lg:px-6 lg:-mb-6 lg:pb-6 lg:rounded-b-xl'
const STICKY_HEAD = '[&_th]:sticky [&_th]:top-0 [&_th]:z-10 [&_th]:bg-card [&_th]:shadow-[inset_0_-1px_0_theme(colors.dbb.warm)]'
const TOGGLE = 'h-6 rounded-md px-2.5 py-0 text-xs after:hidden data-[state=active]:bg-white data-[state=active]:shadow-sm'

function Count({ n }: { n: number }) {
  return <span className="ml-1.5 tabular-nums opacity-60">{num(n)}</span>
}

const counted = (label: string, n: number) => `${label} · ${num(n)}`

function useGet<T>(path: string | null) {
  const [got, setGot] = useState<{ path: string; data: T | null; error: ApiError | null } | null>(null)
  useEffect(() => {
    if (!path) return
    let live = true
    get<T>(path)
      .then((data) => live && setGot({ path, data, error: null }))
      .catch((e) => live && setGot({ path, data: null, error: asApiError(e) }))
    return () => {
      live = false
    }
  }, [path])
  const fresh = path && got?.path === path ? got : null
  return { data: path ? (fresh?.data ?? got?.data ?? null) : null, error: fresh?.error ?? null, loading: !!path && !fresh }
}

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
            <TableHead>Id</TableHead>
            <TableHead className={NUM}>Seq</TableHead>
            <TableHead>Source</TableHead>
            <TableHead>Object type</TableHead>
            <TableHead>Source id</TableHead>
            <TableHead>Ingested</TableHead>
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
          .then((r) => [i, 'retired' in r ? 'retired' : r.anchor] as const)
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
    <SectionCard title={d ? `${d.entity_type} · ${d.anchor}` : 'Entity'} className={FILL} bodyClassName={BODY}>
      <ErrorBanner error={detail.error} className="mb-3" />
      {detail.loading && !detail.data && <Loading />}
      {retired && (
        <p className="text-sm text-dbb-muted">
          <Pill tone="warn">retired</Pill> {retired.detail}
        </p>
      )}
      {d && (
        <>
          <div className="space-y-1 text-sm text-dbb-muted">
            <p>
              <Id id={d.canonical_id} full />
            </p>
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
          <Section title={counted('Members', d.members.length)}>
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Source</TableHead>
                  <TableHead>Source id</TableHead>
                  <TableHead>Object type</TableHead>
                  <TableHead>Evidence</TableHead>
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
                    <TableCell>{m.evidence}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </Section>
          <Section title={counted('Facts', d.facts.length)}>
            {d.facts.length === 0 ? (
              <Empty>no facts</Empty>
            ) : (
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Attr</TableHead>
                    <TableHead>Value</TableHead>
                    <TableHead>Winning source</TableHead>
                    <TableHead>Observed</TableHead>
                    <TableHead className={NUM}>Disagreements</TableHead>
                    <TableHead>Raw event</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {d.facts.map((f) => {
                    const { raw_event_id: rid, source } = f
                    return (
                      <TableRow key={f.attr}>
                        <TableCell className={KEY}>
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
          </Section>
          <Section title={counted('Links', links.length)}>
            {links.length === 0 ? (
              <Empty>no links</Empty>
            ) : (
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Direction</TableHead>
                    <TableHead>Relationship</TableHead>
                    <TableHead>Target</TableHead>
                    <TableHead>Grounding</TableHead>
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
          </Section>
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
    <div className="flex flex-col gap-6 lg:h-full">
      <SectionCard title="Canonical entities" description="click an entity to open it" className="shrink-0">
        <ErrorBanner error={list.error} className="mb-3" />
        <div className="flex flex-wrap gap-2">
          <FilterChip on={type === ''} onClick={() => pick('')}>
            all
            <Count n={all} />
          </FilterChip>
          {byType.map(([t, n]) => (
            <FilterChip key={t} on={type === t} onClick={() => pick(t)}>
              {t}
              <Count n={n} />
            </FilterChip>
          ))}
        </div>
      </SectionCard>
      <div className={SPLIT_FILL}>
        <SectionCard className={FILL} bodyClassName={BODY}>
          {list.loading && !list.data ? (
            <Loading />
          ) : rows.length === 0 ? (
            <Empty>no entities</Empty>
          ) : (
            <Table className="table-fixed" wrapperClassName="overflow-x-visible">
              <TableHeader className={STICKY_HEAD}>
                <TableRow>
                  <TableHead className="w-28">Type</TableHead>
                  <TableHead className="w-64">Anchor</TableHead>
                  <TableHead className={cn(NUM, 'w-24')}>Members</TableHead>
                  <TableHead className="w-32">Id</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {rows.map((r) => {
                  const name = r.facts.name ?? r.facts.subject ?? r.facts.event_name
                  return (
                    <TableRow
                      key={r.canonical_id}
                      className={ROW}
                      data-state={r.canonical_id === selected ? 'selected' : undefined}
                      aria-selected={r.canonical_id === selected}
                      onClick={() => open(r.canonical_id)}
                    >
                      <TableCell>
                        <Pill>{r.entity_type}</Pill>
                      </TableCell>
                      <TableCell className={KEY}>
                        {show(name ?? r.anchor)}
                        {name ? <span className={cn(MONO, 'block font-normal text-dbb-muted')}>{r.anchor}</span> : null}
                      </TableCell>
                      <TableCell className={NUM}>{num(r.members)}</TableCell>
                      <TableCell>
                        <Id id={r.canonical_id} />
                      </TableCell>
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
          <SectionCard className={FILL} bodyClassName={BODY}>
            <Empty>select an entity</Empty>
          </SectionCard>
        )}
      </div>
    </div>
  )
}

function RawSide() {
  const [type, setType] = useState('')
  const [source, setSource] = useState('')
  const [offset, setOffset] = useState(0)
  const [size, setSize] = useState(PAGE)
  const records = useGet<RecordsResponse>(`/api/records?${query({ entity_type: type, source, limit: size, offset })}`)
  const changeSize = (n: number) => {
    setSize(n)
    setOffset(0)
  }

  const [rawSource, setRawSource] = useState('')
  const [rawType, setRawType] = useState('')
  const [rawOffset, setRawOffset] = useState(0)
  const [rawSize, setRawSize] = useState(PAGE)
  const [want, setWant] = useState<string | null>(null)
  const [picked, setPicked] = useState<RawEvent | null>(null)
  const raw = useGet<RawResponse>(
    `/api/raw?${query({ source: rawSource, object_type: rawType, limit: rawSize, offset: rawOffset })}`,
  )
  const changeRawSize = (n: number) => {
    setRawSize(n)
    setRawOffset(0)
  }

  useEffect(() => {
    if (!want || !raw.data) return
    setPicked(raw.data.events.find((e) => e.source_id === want) ?? null)
    setWant(null)
  }, [want, raw.data])

  const peek = (r: RecordRow) => {
    setRawSource(r.source)
    setRawType(r.object_type)
    setRawOffset(0)
    setPicked(null)
    setWant(r.source_id)
  }

  const types = Object.keys(records.data?.by_type ?? {})
  const rows = records.data?.entities ?? []
  const events = raw.data?.events ?? []

  return (
    <div className={SPLIT}>
      <SectionCard title={`Records${records.data ? ` (${num(records.data.total)})` : ''}`} description="click a record to peek at its raw events">
        <ErrorBanner error={records.error} className="mb-3" />
        <div className="mb-4 flex flex-wrap items-center gap-2">
          <Select
            value={type || ALL}
            onValueChange={(v) => {
              setType(v === ALL ? '' : v)
              setOffset(0)
            }}
          >
            <SelectTrigger className="h-8 w-44">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value={ALL}>all types</SelectItem>
              {types.map((t) => (
                <SelectItem key={t} value={t}>
                  {t} ({num(records.data?.by_type[t] ?? 0)})
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
          <Input
            className="h-8 w-40"
            placeholder="source"
            value={source}
            onChange={(e) => {
              setSource(e.target.value)
              setOffset(0)
            }}
          />
        </div>
        {records.loading && !records.data ? (
          <Loading />
        ) : rows.length === 0 ? (
          <Empty>no records</Empty>
        ) : (
          <Table className="table-fixed">
            <TableHeader>
              <TableRow>
                <TableHead className="w-28">Source</TableHead>
                <TableHead className="w-28">Type</TableHead>
                <TableHead className="w-40">Source id</TableHead>
                <TableHead className="w-32">Object type</TableHead>
                <TableHead className="w-80">Facts</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {rows.map((r, i) => (
                <TableRow
                  key={`${r.source}|${r.object_type}|${r.source_id}|${i}`}
                  className={ROW}
                  data-state={picked?.source === r.source && picked?.source_id === r.source_id ? 'selected' : undefined}
                  aria-selected={picked?.source === r.source && picked?.source_id === r.source_id}
                  onClick={() => peek(r)}
                >
                  <TableCell>
                    <Mono>{r.source}</Mono>
                  </TableCell>
                  <TableCell>
                    <Pill>{r.entity_type}</Pill>
                  </TableCell>
                  <TableCell className={KEY}>
                    <Mono>{r.source_id}</Mono>
                  </TableCell>
                  <TableCell>
                    <Mono>{r.object_type}</Mono>
                  </TableCell>
                  <TableCell className={WRAP}>
                    {Object.entries(r.facts)
                      .map(([k, v]) => `${k}=${show(v)}`)
                      .join(' · ')}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )}
        {records.data && (
          <Pager
            offset={offset}
            count={rows.length}
            total={records.data.total}
            onPage={setOffset}
            size={size}
            allSize={Math.min(records.data.total, 500)}
            onSize={changeSize}
          />
        )}
      </SectionCard>
      <SectionCard title={`Raw events${raw.data ? ` (${num(raw.data.total)})` : ''}`} className="min-w-0">
        <ErrorBanner error={raw.error} className="mb-3" />
        <div className="mb-4 flex flex-wrap items-center gap-2">
          <Input
            className="h-8 w-40"
            placeholder="source"
            value={rawSource}
            onChange={(e) => {
              setRawSource(e.target.value)
              setRawOffset(0)
            }}
          />
          <Input
            className="h-8 w-40"
            placeholder="object_type"
            value={rawType}
            onChange={(e) => {
              setRawType(e.target.value)
              setRawOffset(0)
            }}
          />
        </div>
        {raw.loading && !raw.data ? (
          <Loading />
        ) : events.length === 0 ? (
          <Empty>no raw events</Empty>
        ) : (
          <Table className="table-fixed">
            <TableHeader>
              <TableRow>
                <TableHead className={cn(NUM, 'w-20')}>Seq</TableHead>
                <TableHead className="w-28">Source</TableHead>
                <TableHead className="w-32">Object type</TableHead>
                <TableHead className="w-40">Source id</TableHead>
                <TableHead className="w-32">Ingested</TableHead>
                <TableHead className="w-28">Id</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {events.map((e) => (
                <TableRow
                  key={e.id}
                  className={ROW}
                  data-state={picked?.id === e.id ? 'selected' : undefined}
                  aria-selected={picked?.id === e.id}
                  onClick={() => setPicked(e)}
                >
                  <TableCell className={NUM}>{num(e.seq)}</TableCell>
                  <TableCell>
                    <Mono>{e.source}</Mono>
                  </TableCell>
                  <TableCell>
                    <Mono>{e.object_type}</Mono>
                  </TableCell>
                  <TableCell className={KEY}>
                    <Mono>{e.source_id}</Mono>
                  </TableCell>
                  <TableCell className="whitespace-nowrap" title={e.ingested_at}>
                    {relTime(e.ingested_at)}
                  </TableCell>
                  <TableCell>
                    <Id id={e.id} />
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )}
        {raw.data && (
          <Pager
            offset={rawOffset}
            count={events.length}
            total={raw.data.total}
            onPage={setRawOffset}
            size={rawSize}
            allSize={Math.min(raw.data.total, 500)}
            onSize={changeRawSize}
          />
        )}
        <Section title="Payload">{picked ? <RawEventView event={picked} /> : <Empty>select a raw event</Empty>}</Section>
      </SectionCard>
    </div>
  )
}

export function Entities() {
  const [slot, setSlot] = useState<HTMLElement | null>(null)
  useEffect(() => {
    setSlot(document.getElementById(HEADING_RIGHT_ID))
  }, [])
  return (
    <Tabs defaultValue="canonical" className={PAGE_FILL}>
      {slot &&
        createPortal(
          <TabsList className="gap-0.5 rounded-lg border-0 bg-dbb-sand p-0.5">
            <TabsTrigger value="canonical" className={TOGGLE}>
              Canonical
            </TabsTrigger>
            <TabsTrigger value="raw" className={TOGGLE}>
              Raw side
            </TabsTrigger>
          </TabsList>,
          slot,
        )}
      <TabsContent value="canonical" className="mt-0 lg:min-h-0 lg:flex-1">
        <Canonical />
      </TabsContent>
      <TabsContent value="raw" className="mt-0">
        <RawSide />
      </TabsContent>
    </Tabs>
  )
}
