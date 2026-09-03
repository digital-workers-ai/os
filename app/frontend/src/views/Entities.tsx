import { useEffect, useState, type MouseEvent } from 'react'
import { asApiError, get, type ApiError } from '../api'
import { Json } from '../components/Json'
import { Empty, Panel, num, relTime } from '../components/Panel'
import { Status } from '../components/Status'
import './Entities.css'

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

const query = (params: Record<string, string | number | undefined>) =>
  Object.entries(params)
    .filter(([, v]) => v !== undefined && v !== '')
    .map(([k, v]) => `${k}=${encodeURIComponent(String(v))}`)
    .join('&')

const short = (id: string) => id.slice(0, 8) + '…'

const show = (v: unknown) =>
  v === null || v === undefined ? '—' : typeof v === 'object' ? JSON.stringify(v) : String(v)

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
    <code className="id" title={`${id} — click to copy`} onClick={copy}>
      {full ? id : short(id)}
      {copied && <span className="pill ok">copied</span>}
    </code>
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
    <div className="pager">
      <button className="btn" disabled={offset === 0} onClick={() => onPage(Math.max(0, offset - PAGE))}>
        ‹ prev
      </button>
      <span className="dim">
        {total === 0 ? '0' : `${num(offset + 1)}–${num(offset + count)}`} of {num(total)}
      </span>
      <button className="btn" disabled={offset + count >= total} onClick={() => onPage(offset + PAGE)}>
        next ›
      </button>
    </div>
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
      <table>
        <thead>
          <tr>
            <th>Id</th>
            <th className="num">Seq</th>
            <th>Source</th>
            <th>Object type</th>
            <th>Source id</th>
            <th>Ingested</th>
          </tr>
        </thead>
        <tbody>
          <tr>
            <td>
              <Id id={event.id} full />
            </td>
            <td className="num">{num(event.seq)}</td>
            <td>
              <code>{event.source}</code>
            </td>
            <td>
              <code>{event.object_type}</code>
            </td>
            <td>
              <code>{event.source_id}</code>
            </td>
            <td title={event.ingested_at}>{relTime(event.ingested_at)}</td>
          </tr>
        </tbody>
      </table>
      <div className="panel-body">
        <Json value={event.raw_payload} label="raw_payload" open />
      </div>
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
    <Panel title="Raw event">
      <div className="panel-body">
        <p>
          <code>{trace.id}</code> looked up by scanning <code>/api/raw?{filter}</code>
        </p>
        <Status error={done?.error ?? null} />
        {!done && <Empty>scanning…</Empty>}
        {done && !done.error && !done.event && <Empty>no raw event with that id under this filter</Empty>}
      </div>
      {done?.event && <RawEventView event={done.event} />}
    </Panel>
  )
}

function Detail({ id, onOpen, onTrace }: { id: string; onOpen: (id: string) => void; onTrace: (t: Trace) => void }) {
  const detail = useGet<EntityResponse>(`/api/entities/${id}`)
  const [anchors, setAnchors] = useState<Record<string, string>>({})
  const d = detail.data && !('retired' in detail.data) ? detail.data : null

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
    <Panel title={d ? `${d.entity_type} · ${d.anchor}` : 'Entity'}>
      <div className="panel-body">
        <Status error={detail.error} />
        {detail.loading && <Empty>loading…</Empty>}
        {detail.data && 'retired' in detail.data && (
          <p>
            <span className="pill warn">retired</span> {detail.data.detail}
          </p>
        )}
        {d && (
          <>
            <p>
              <Id id={d.canonical_id} full />
              {d.resolved_from_alias && (
                <>
                  {' '}
                  <span className="pill warn">alias</span> resolved from <code>{d.resolved_from_alias}</code>
                </>
              )}
            </p>
            {d.aliases.length > 0 && (
              <p className="dim">
                aliases: {d.aliases.map((a) => <code key={a}>{a} </code>)}
              </p>
            )}
            <h3>
              Members <span className="dim">({d.members.length})</span>
            </h3>
          </>
        )}
      </div>
      {d && (
        <>
          <table>
            <thead>
              <tr>
                <th>Source</th>
                <th>Source id</th>
                <th>Object type</th>
                <th>Evidence</th>
              </tr>
            </thead>
            <tbody>
              {d.members.map((m) => (
                <tr key={`${m.source}|${m.object_type}|${m.source_id}`}>
                  <td>
                    <code>{m.source}</code>
                  </td>
                  <td>
                    <code>{m.source_id}</code>
                  </td>
                  <td>
                    <code>{m.object_type}</code>
                  </td>
                  <td className="dim">{m.evidence}</td>
                </tr>
              ))}
            </tbody>
          </table>
          <div className="panel-body">
            <h3>
              Facts <span className="dim">({d.facts.length})</span>
            </h3>
          </div>
          {d.facts.length === 0 ? (
            <Empty>no facts</Empty>
          ) : (
            <table>
              <thead>
                <tr>
                  <th>Attr</th>
                  <th>Value</th>
                  <th>Winning source</th>
                  <th>Observed</th>
                  <th className="num">Disagreements</th>
                  <th>Raw event</th>
                </tr>
              </thead>
              <tbody>
                {d.facts.map((f) => {
                  const { raw_event_id: rid, source } = f
                  return (
                    <tr key={f.attr}>
                      <td>
                        <code>{f.attr}</code>
                      </td>
                      <td className="wrap">{show(f.value)}</td>
                      <td>{source ? <code>{source}</code> : <span className="dim">—</span>}</td>
                      <td title={f.observed_at}>{relTime(f.observed_at)}</td>
                      <td className="num">
                        {f.disagreements > 0 ? <span className="pill warn">{num(f.disagreements)}</span> : '0'}
                      </td>
                      <td>
                        {rid && source ? (
                          <button
                            className="link-btn mono"
                            title={`${rid} — open raw event`}
                            onClick={() => onTrace({ id: rid, source, objectType: objectTypeFor(source) })}
                          >
                            {short(rid)}
                          </button>
                        ) : (
                          <span className="dim">—</span>
                        )}
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          )}
          <div className="panel-body">
            <h3>
              Links <span className="dim">({links.length})</span>
            </h3>
          </div>
          {links.length === 0 ? (
            <Empty>no links</Empty>
          ) : (
            <table>
              <thead>
                <tr>
                  <th>Direction</th>
                  <th>Relationship</th>
                  <th>Target</th>
                  <th>Grounding</th>
                </tr>
              </thead>
              <tbody>
                {links.map((l) => (
                  <tr key={`${l.dir}|${l.rel}|${l.other}`}>
                    <td>
                      <span className="pill">{l.dir}</span>
                    </td>
                    <td>
                      <code>{l.rel}</code>
                    </td>
                    <td>
                      <button className="link-btn" title={l.other} onClick={() => onOpen(l.other)}>
                        {anchors[l.other] || short(l.other)}
                      </button>
                    </td>
                    <td>
                      <Grounding value={l.grounding} />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </>
      )}
    </Panel>
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
    <div className="split">
      <Panel title={`Canonical entities${list.data ? ` (${num(list.data.total)})` : ''}`}>
        <div className="panel-body">
          <Status error={list.error} />
          <div className="chips">
            <button className="chip" aria-pressed={type === ''} onClick={() => pick('')}>
              all <strong>{num(all)}</strong>
            </button>
            {byType.map(([t, n]) => (
              <button key={t} className="chip" aria-pressed={type === t} onClick={() => pick(t)}>
                {t} <strong>{num(n)}</strong>
              </button>
            ))}
          </div>
        </div>
        {list.loading ? (
          <Empty>loading…</Empty>
        ) : rows.length === 0 ? (
          <Empty>no entities</Empty>
        ) : (
          <table>
            <thead>
              <tr>
                <th>Type</th>
                <th>Anchor</th>
                <th className="num">Members</th>
                <th>Canonical id</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((r) => (
                <tr
                  key={r.canonical_id}
                  className="row-click"
                  aria-selected={r.canonical_id === selected}
                  onClick={() => open(r.canonical_id)}
                >
                  <td>
                    <span className="pill">{r.entity_type}</span>
                  </td>
                  <td className="wrap">
                    {show(r.facts.name ?? r.facts.subject ?? r.facts.event_name ?? r.anchor)}
                    {r.facts.name || r.facts.subject || r.facts.event_name ? (
                      <>
                        {' '}
                        <code className="dim">{r.anchor}</code>
                      </>
                    ) : null}
                  </td>
                  <td className="num">{num(r.members)}</td>
                  <td>
                    <Id id={r.canonical_id} />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
        {list.data && <Pager offset={offset} count={rows.length} total={list.data.total} onPage={setOffset} />}
      </Panel>
      <div className="stack">
        {selected ? (
          <Detail id={selected} onOpen={open} onTrace={setTrace} />
        ) : (
          <Panel title="Entity">
            <Empty>select an entity</Empty>
          </Panel>
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
    <div className="split">
      <Panel title={`Records${records.data ? ` (${num(records.data.total)})` : ''}`}>
        <div className="panel-body">
          <Status error={records.error} />
          <div className="filters">
            <select
              value={type}
              onChange={(e) => {
                setType(e.target.value)
                setOffset(0)
              }}
            >
              <option value="">all types</option>
              {types.map((t) => (
                <option key={t} value={t}>
                  {t} ({num(records.data?.by_type[t] ?? 0)})
                </option>
              ))}
            </select>
            <input
              placeholder="source"
              value={source}
              onChange={(e) => {
                setSource(e.target.value)
                setOffset(0)
              }}
            />
            <span className="dim">click a record to peek at its raw events</span>
          </div>
        </div>
        {records.loading ? (
          <Empty>loading…</Empty>
        ) : rows.length === 0 ? (
          <Empty>no records</Empty>
        ) : (
          <table>
            <thead>
              <tr>
                <th>Source</th>
                <th>Type</th>
                <th>Source id</th>
                <th>Object type</th>
                <th>Facts</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((r) => (
                <tr
                  key={`${r.source}|${r.object_type}|${r.source_id}`}
                  className="row-click"
                  aria-selected={picked?.source === r.source && picked?.source_id === r.source_id}
                  onClick={() => peek(r)}
                >
                  <td>
                    <code>{r.source}</code>
                  </td>
                  <td>
                    <span className="pill">{r.entity_type}</span>
                  </td>
                  <td>
                    <code>{r.source_id}</code>
                  </td>
                  <td>
                    <code>{r.object_type}</code>
                  </td>
                  <td className="dim wrap">
                    {Object.entries(r.facts)
                      .map(([k, v]) => `${k}=${show(v)}`)
                      .join(' · ')}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
        {records.data && <Pager offset={offset} count={rows.length} total={records.data.total} onPage={setOffset} />}
      </Panel>
      <div className="stack">
        <Panel title={`Raw events${raw.data ? ` (${num(raw.data.total)})` : ''}`}>
          <div className="panel-body">
            <Status error={raw.error} />
            <div className="filters">
              <input
                placeholder="source"
                value={rawSource}
                onChange={(e) => {
                  setRawSource(e.target.value)
                  setRawOffset(0)
                }}
              />
              <input
                placeholder="object_type"
                value={rawType}
                onChange={(e) => {
                  setRawType(e.target.value)
                  setRawOffset(0)
                }}
              />
            </div>
          </div>
          {raw.loading ? (
            <Empty>loading…</Empty>
          ) : events.length === 0 ? (
            <Empty>no raw events</Empty>
          ) : (
            <table>
              <thead>
                <tr>
                  <th className="num">Seq</th>
                  <th>Source</th>
                  <th>Object type</th>
                  <th>Source id</th>
                  <th>Ingested</th>
                  <th>Id</th>
                </tr>
              </thead>
              <tbody>
                {events.map((e) => (
                  <tr key={e.id} className="row-click" aria-selected={picked?.id === e.id} onClick={() => setPicked(e)}>
                    <td className="num">{num(e.seq)}</td>
                    <td>
                      <code>{e.source}</code>
                    </td>
                    <td>
                      <code>{e.object_type}</code>
                    </td>
                    <td>
                      <code>{e.source_id}</code>
                    </td>
                    <td title={e.ingested_at}>{relTime(e.ingested_at)}</td>
                    <td>
                      <Id id={e.id} />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
          {raw.data && <Pager offset={rawOffset} count={events.length} total={raw.data.total} onPage={setRawOffset} />}
        </Panel>
        <Panel title="Raw payload">
          {picked ? <RawEventView event={picked} /> : <Empty>select a raw event</Empty>}
        </Panel>
      </div>
    </div>
  )
}

export function Entities() {
  const [tab, setTab] = useState<'canonical' | 'raw'>('canonical')
  return (
    <>
      <nav className="tabs">
        <button className="tab" aria-current={tab === 'canonical' ? 'page' : undefined} onClick={() => setTab('canonical')}>
          Canonical
        </button>
        <button className="tab" aria-current={tab === 'raw' ? 'page' : undefined} onClick={() => setTab('raw')}>
          Raw side
        </button>
      </nav>
      {tab === 'canonical' ? <Canonical /> : <RawSide />}
    </>
  )
}
