import { useEffect, useState, type MouseEvent, type ReactNode } from 'react'
import { asApiError, get, type ApiError } from '@/api'
import { SectionCard } from '@/components/SectionCard'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
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

const PAGE = 50
const SCAN = 500
const ALL = '*'

const num = (n: number) => n.toLocaleString()

function relTime(iso: string | null): string {
  if (!iso) return 'never'
  const then = new Date(iso).getTime()
  if (Number.isNaN(then)) return 'never'
  const secs = Math.max(0, Math.round((Date.now() - then) / 1000))
  if (secs < 60) return `${secs}s ago`
  if (secs < 3600) return `${Math.round(secs / 60)}m ago`
  if (secs < 86400) return `${Math.round(secs / 3600)}h ago`
  return `${Math.round(secs / 86400)}d ago`
}

const query = (params: Record<string, string | number | undefined>) =>
  Object.entries(params)
    .filter(([, v]) => v !== undefined && v !== '')
    .map(([k, v]) => `${k}=${encodeURIComponent(String(v))}`)
    .join('&')

const short = (id: string) => id.slice(0, 8) + '…'

const show = (v: unknown) =>
  v === null || v === undefined ? '—' : typeof v === 'object' ? JSON.stringify(v) : String(v)

const MONO = 'font-mono text-xs'
const NUM = 'text-right tabular-nums'
const KEY = 'font-medium text-dbb-charcoal'
const LINK = 'text-dbb-charcoal underline decoration-dotted decoration-dbb-muted underline-offset-2 hover:decoration-solid'
const ROW = 'cursor-pointer hover:bg-dbb-sand/50'
const PRE = 'mt-4 max-h-[480px] overflow-auto rounded-lg bg-dbb-surface p-3 font-mono text-xs'
const WRAP = 'break-words'
const SPLIT = 'flex flex-col gap-6 lg:grid lg:grid-cols-[1fr_1.2fr]'

const TONES = {
  ok: 'bg-dbb-up/10 text-dbb-up',
  warn: 'bg-amber-50 text-amber-800',
  neutral: 'bg-dbb-sand text-dbb-charcoal',
}

function Pill({ tone = 'neutral', className, children }: { tone?: keyof typeof TONES; className?: string; children: ReactNode }) {
  return (
    <span className={cn('inline-flex items-center whitespace-nowrap rounded-full px-2 py-0.5 text-[11px] font-medium', TONES[tone], className)}>
      {children}
    </span>
  )
}

function Mono({ children }: { children: ReactNode }) {
  return <span className={MONO}>{children}</span>
}

function Count({ n }: { n: number }) {
  return <span className="ml-1.5 tabular-nums opacity-60">{num(n)}</span>
}

function Empty({ children }: { children: ReactNode }) {
  return <p className="py-8 text-center text-sm text-dbb-muted">{children}</p>
}

function ErrorBanner({ error }: { error: ApiError | null }) {
  if (!error) return null
  return (
    <div role="alert" className="mb-3 rounded-lg border border-dbb-clay/30 bg-dbb-clay/5 px-3 py-2 text-sm text-dbb-clay">
      <span className={MONO}>{error.status || 'network'}</span> {error.detail}
    </div>
  )
}

function Chip({ on, onClick, children }: { on: boolean; onClick: () => void; children: ReactNode }) {
  return (
    <button
      type="button"
      aria-pressed={on}
      onClick={onClick}
      className={cn(
        'rounded-full border px-2.5 py-1 text-xs font-medium transition-colors',
        on ? 'border-dbb-warm bg-dbb-sand text-dbb-charcoal' : 'border-dbb-warm/50 text-dbb-muted hover:border-dbb-warm',
      )}
    >
      {children}
    </button>
  )
}

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
  return { data: fresh?.data ?? null, error: fresh?.error ?? null, loading: !!path && !fresh }
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

function Pager({
  offset,
  count,
  total,
  onPage,
}: {
  offset: number
  count: number
  total: number
  onPage: (offset: number) => void
}) {
  return (
    <div className="mt-3 flex items-center gap-1 border-t border-dbb-warm/50 pt-2 text-sm text-dbb-muted">
      <Button variant="ghost" size="sm" className="h-7 px-2" disabled={offset === 0} onClick={() => onPage(Math.max(0, offset - PAGE))}>
        ← Prev
      </Button>
      <span className="px-1 tabular-nums">
        {total === 0 ? '0' : `${num(offset + 1)}–${num(offset + count)}`} / {num(total)}
      </span>
      <Button variant="ghost" size="sm" className="h-7 px-2" disabled={offset + count >= total} onClick={() => onPage(offset + PAGE)}>
        Next →
      </Button>
    </div>
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
    <SectionCard title="Raw event">
      <p className={cn('mb-3 text-sm text-dbb-muted', WRAP)}>
        <Mono>{trace.id}</Mono> looked up by scanning <Mono>/api/raw?{filter}</Mono>
      </p>
      <ErrorBanner error={done?.error ?? null} />
      {!done && <Empty>scanning…</Empty>}
      {done && !done.error && !done.event && <Empty>no raw event with that id under this filter</Empty>}
      {done?.event && <RawEventView event={done.event} />}
    </SectionCard>
  )
}

function Detail({ id, onOpen, onTrace }: { id: string; onOpen: (id: string) => void; onTrace: (t: Trace) => void }) {
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
    <SectionCard title={d ? `${d.entity_type} · ${d.anchor}` : 'Entity'}>
      <ErrorBanner error={detail.error} />
      {detail.loading && <Empty>loading…</Empty>}
      {retired && (
        <p className="text-sm text-dbb-muted">
          <Pill tone="warn">retired</Pill> {retired.detail}
        </p>
      )}
      {d && (
        <>
          <div className="mb-4 space-y-1 text-sm text-dbb-muted">
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
          <Tabs defaultValue="members">
            <TabsList>
              <TabsTrigger value="members">
                Members
                <Count n={d.members.length} />
              </TabsTrigger>
              <TabsTrigger value="facts">
                Facts
                <Count n={d.facts.length} />
              </TabsTrigger>
              <TabsTrigger value="links">
                Links
                <Count n={links.length} />
              </TabsTrigger>
            </TabsList>
            <TabsContent value="members" className="mt-4">
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
            </TabsContent>
            <TabsContent value="facts" className="mt-4">
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
            </TabsContent>
            <TabsContent value="links" className="mt-4">
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
            </TabsContent>
          </Tabs>
        </>
      )}
    </SectionCard>
  )
}

function Canonical() {
  const [type, setType] = useState('')
  const [offset, setOffset] = useState(0)
  const [selected, setSelected] = useState<string | null>(null)
  const [trace, setTrace] = useState<Trace | null>(null)
  const list = useGet<EntitiesResponse>(`/api/entities?${query({ entity_type: type, limit: PAGE, offset })}`)

  const pick = (t: string) => {
    setType(t)
    setOffset(0)
  }
  const open = (id: string) => {
    setSelected(id)
    setTrace(null)
  }

  const byType = Object.entries(list.data?.by_type ?? {})
  const all = byType.reduce((n, [, c]) => n + c, 0)
  const rows = list.data?.entities ?? []

  return (
    <div className={SPLIT}>
      <SectionCard title={`Canonical entities${list.data ? ` (${num(list.data.total)})` : ''}`}>
        <ErrorBanner error={list.error} />
        <div className="mb-4 flex flex-wrap gap-2">
          <Chip on={type === ''} onClick={() => pick('')}>
            all
            <Count n={all} />
          </Chip>
          {byType.map(([t, n]) => (
            <Chip key={t} on={type === t} onClick={() => pick(t)}>
              {t}
              <Count n={n} />
            </Chip>
          ))}
        </div>
        {list.loading ? (
          <Empty>loading…</Empty>
        ) : rows.length === 0 ? (
          <Empty>no entities</Empty>
        ) : (
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Type</TableHead>
                <TableHead>Anchor</TableHead>
                <TableHead className={NUM}>Members</TableHead>
                <TableHead>Id</TableHead>
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
        {list.data && <Pager offset={offset} count={rows.length} total={list.data.total} onPage={setOffset} />}
      </SectionCard>
      <div className="flex min-w-0 flex-col gap-6">
        {selected ? (
          <Detail id={selected} onOpen={open} onTrace={setTrace} />
        ) : (
          <SectionCard title="Entity">
            <Empty>select an entity</Empty>
          </SectionCard>
        )}
        {trace && <RawTrace trace={trace} />}
      </div>
    </div>
  )
}

function RawSide() {
  const [type, setType] = useState('')
  const [source, setSource] = useState('')
  const [offset, setOffset] = useState(0)
  const records = useGet<RecordsResponse>(`/api/records?${query({ entity_type: type, source, limit: PAGE, offset })}`)

  const [rawSource, setRawSource] = useState('')
  const [rawType, setRawType] = useState('')
  const [rawOffset, setRawOffset] = useState(0)
  const [want, setWant] = useState<string | null>(null)
  const [picked, setPicked] = useState<RawEvent | null>(null)
  const raw = useGet<RawResponse>(
    `/api/raw?${query({ source: rawSource, object_type: rawType, limit: PAGE, offset: rawOffset })}`,
  )

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
      <SectionCard title={`Records${records.data ? ` (${num(records.data.total)})` : ''}`}>
        <ErrorBanner error={records.error} />
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
          <span className="text-sm text-dbb-muted">click a record to peek at its raw events</span>
        </div>
        {records.loading ? (
          <Empty>loading…</Empty>
        ) : rows.length === 0 ? (
          <Empty>no records</Empty>
        ) : (
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Source</TableHead>
                <TableHead>Type</TableHead>
                <TableHead>Source id</TableHead>
                <TableHead>Object type</TableHead>
                <TableHead>Facts</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {rows.map((r) => (
                <TableRow
                  key={`${r.source}|${r.object_type}|${r.source_id}`}
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
        {records.data && <Pager offset={offset} count={rows.length} total={records.data.total} onPage={setOffset} />}
      </SectionCard>
      <div className="flex min-w-0 flex-col gap-6">
        <SectionCard title={`Raw events${raw.data ? ` (${num(raw.data.total)})` : ''}`}>
          <ErrorBanner error={raw.error} />
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
          {raw.loading ? (
            <Empty>loading…</Empty>
          ) : events.length === 0 ? (
            <Empty>no raw events</Empty>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead className={NUM}>Seq</TableHead>
                  <TableHead>Source</TableHead>
                  <TableHead>Object type</TableHead>
                  <TableHead>Source id</TableHead>
                  <TableHead>Ingested</TableHead>
                  <TableHead>Id</TableHead>
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
          {raw.data && <Pager offset={rawOffset} count={events.length} total={raw.data.total} onPage={setRawOffset} />}
        </SectionCard>
        <SectionCard title="Payload">{picked ? <RawEventView event={picked} /> : <Empty>select a raw event</Empty>}</SectionCard>
      </div>
    </div>
  )
}

export function Entities() {
  return (
    <Tabs defaultValue="canonical">
      <TabsList>
        <TabsTrigger value="canonical">Canonical</TabsTrigger>
        <TabsTrigger value="raw">Raw side</TabsTrigger>
      </TabsList>
      <TabsContent value="canonical">
        <Canonical />
      </TabsContent>
      <TabsContent value="raw">
        <RawSide />
      </TabsContent>
    </Tabs>
  )
}
