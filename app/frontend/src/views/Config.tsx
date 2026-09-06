import { useEffect, useState } from 'react'
import {
  api,
  asApiError,
  get,
  put,
  type ApiError,
  type McpIndex,
  type RebuildResponse,
  type ReportResponse,
  type RunsResponse,
  type SourceRow,
  type SourcesResponse,
  type SyncResponse,
} from '@/api'
import { Filter } from '@/components/Filter'
import { SectionCard } from '@/components/SectionCard'
import { Banner, ErrorBanner } from '@/components/ui/banner'
import { Button } from '@/components/ui/button'
import { Empty } from '@/components/ui/empty'
import { Loading } from '@/components/ui/loading'
import { Mono } from '@/components/ui/mono'
import { Chip, FilterChip, Pill } from '@/components/ui/pill'
import { STICKY_HEAD, Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { num, plural, relTime } from '@/lib/format'
import { useGet } from '@/lib/useGet'
import { cn } from '@/lib/utils'
import { BODY, FULL, PAGE_FILL, useLoad } from './inference/shared'

type Ran = Extract<ReportResponse, { ran: true }>

const MONO = 'font-mono text-xs'
const NUM = 'text-right tabular-nums'
const KEY = 'font-medium text-dbb-charcoal'
const TOP = 'align-top'
const TAB = 'lg:min-h-0 lg:flex-1'
const TAB_SCROLL = 'lg:min-h-0 lg:flex-1 lg:overflow-y-auto'
const NARROW = 'w-px whitespace-nowrap'
const PRE = 'overflow-auto rounded-lg bg-dbb-surface p-3 font-mono text-xs'
const SPLIT = 'grid items-start gap-6 lg:h-full lg:grid-cols-[0.45fr_0.55fr] lg:grid-rows-[minmax(0,1fr)]'
const NOTICES = 'mt-2 -mb-1 flex flex-col gap-3 [&>*]:mb-0'

const enabledKey = (r: SourceRow) => (r.enabled ? 'enabled' : 'disabled')

const enabledOptions = (rows: SourceRow[]): [string, number][] => {
  const on = rows.filter((r) => r.enabled).length
  return [
    ['enabled', on],
    ['disabled', rows.length - on],
  ]
}

const shortDate = (iso: string) => new Date(iso).toLocaleDateString('en-US', { month: 'short', day: 'numeric' })

function SyncBanner({ sync }: { sync: SyncResponse }) {
  const total = (k: 'rows_fetched' | 'rows_written' | 'rows_refused' | 'rows_colliding') =>
    num(sync.results.reduce((n, r) => n + r[k], 0))
  return (
    <Banner tone={sync.failed > 0 ? 'err' : 'warn'} testId="sync-banner">
      synced {plural(sync.results.length, 'source')} · {total('rows_fetched')} fetched · {total('rows_written')} written ·{' '}
      {total('rows_refused')} refused · {total('rows_colliding')} colliding
      {sync.results
        .filter((r) => !r.ok || r.detail)
        .map((r) => (
          <span key={r.source} className="block">
            {r.source}: {r.detail || 'failed'}
          </span>
        ))}
    </Banner>
  )
}

function CountTable({ label, hint, rows }: { label: string; hint: string; rows: Record<string, number> }) {
  const entries = Object.entries(rows)
  if (entries.length === 0) return null
  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead hint={hint}>
            {label} ({num(entries.length)})
          </TableHead>
          <TableHead className={NUM} hint="How many times it happened">
            Count
          </TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {entries.map(([k, v]) => (
          <TableRow key={k}>
            <TableCell className={cn(KEY, MONO, TOP)}>{k}</TableCell>
            <TableCell className={cn(NUM, TOP)}>{num(v)}</TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  )
}

function Report({ report }: { report: Ran }) {
  const r = report.report
  const rates = Object.entries(r.match_rates)
  return (
    <>
      <SectionCard
        testId="rebuild-totals"
        title={
          <div className="flex flex-wrap items-center gap-1.5 font-normal" data-testid="rebuild-status">
            <Pill tone={report.ok ? 'ok' : 'err'}>{report.ok ? 'ok' : 'failed'}</Pill>
            <Chip title={report.created_at}>
              ran <strong>{relTime(report.created_at)}</strong>
            </Chip>
            <Chip>
              duration <strong>{num(report.duration_ms)} ms</strong>
            </Chip>
            <Chip>
              raw events <strong>{num(report.raw_events_read)}</strong>
            </Chip>
            <Chip>
              entities <strong>{num(report.entities)}</strong>
            </Chip>
            <Chip>
              facts <strong>{num(report.facts)}</strong>
            </Chip>
          </div>
        }
      >
        <CountTable label="Total" hint="The kind of problem the rebuild counted" rows={r.totals} />
      </SectionCard>
      {r.quarantines.length > 0 && (
        <SectionCard testId="rebuild-quarantines">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead hint="Which link type was held back as suspicious">Quarantine ({num(r.quarantines.length)})</TableHead>
                <TableHead hint="The record whose link was held back">Record</TableHead>
                <TableHead hint="Why the link looked suspicious">Detail</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {r.quarantines.map((q, i) => (
                <TableRow key={i}>
                  <TableCell className={cn(KEY, TOP)}>{q.rel}</TableCell>
                  <TableCell className={cn(MONO, TOP)}>{q.record}</TableCell>
                  <TableCell className={TOP}>{q.detail}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </SectionCard>
      )}
      {r.oversized.length > 0 && (
        <SectionCard testId="rebuild-oversized">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead hint="What kind of record was too big to process">Oversized ({num(r.oversized.length)})</TableHead>
                <TableHead hint="Everything known about the oversized record">Detail</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {r.oversized.map((o, i) => (
                <TableRow key={i}>
                  <TableCell className={cn(NARROW, TOP)}>
                    <Pill tone="warn">{o.kind}</Pill>
                  </TableCell>
                  <TableCell className={TOP}>
                    <Mono>{JSON.stringify(o)}</Mono>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </SectionCard>
      )}
      {r.dead_paths.length > 0 && (
        <SectionCard testId="rebuild-dead-paths">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead hint="A mapping path that matched nothing in the data">Dead path ({num(r.dead_paths.length)})</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {r.dead_paths.map((p) => (
                <TableRow key={p}>
                  <TableCell className={cn(MONO, TOP)}>{p}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </SectionCard>
      )}
      {Object.keys(r.disagreements).length > 0 && (
        <SectionCard testId="rebuild-disagreements">
          <CountTable label="Disagreement" hint="The field sources gave different values for" rows={r.disagreements} />
        </SectionCard>
      )}
      {rates.length > 0 && (
        <SectionCard testId="rebuild-match-rates">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead hint="The kind of link between two things">Relationship ({num(rates.length)})</TableHead>
                <TableHead className={NUM} hint="How many links were attempted">
                  Candidates
                </TableHead>
                <TableHead className={NUM} hint="How many links found their target">
                  Matched
                </TableHead>
                <TableHead className={NUM} hint="How many links were written">
                  Edges
                </TableHead>
                <TableHead className={NUM} hint="Matched divided by candidates">
                  Rate
                </TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {rates.map(([rel, m]) => (
                <TableRow key={rel}>
                  <TableCell className={cn(KEY, TOP)}>{rel}</TableCell>
                  <TableCell className={cn(NUM, TOP)}>{num(m.candidates)}</TableCell>
                  <TableCell className={cn(NUM, TOP)}>{num(m.matched)}</TableCell>
                  <TableCell className={cn(NUM, TOP)}>{num(m.edges)}</TableCell>
                  <TableCell className={cn(NUM, TOP)}>{m.match_rate === null ? '—' : m.match_rate}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </SectionCard>
      )}
      <SectionCard title="Receipts" testId="rebuild-receipts">
        <p className="mb-3 text-sm text-dbb-muted">The full report of this rebuild, exactly as the engine produced it.</p>
        <pre className={PRE}>{JSON.stringify(r, null, 2)}</pre>
      </SectionCard>
    </>
  )
}

function Rebuilds({ rebuilds }: { rebuilds: number }) {
  const [seq, setSeq] = useState<number | null>(null)
  const runs = useLoad(() => get<RunsResponse>('/api/report/runs'), [rebuilds])
  const list = runs.data?.runs ?? []
  const newest = runs.data?.runs[0]?.seq
  useEffect(() => {
    if (seq === null && newest !== undefined) setSeq(newest)
  }, [seq, newest])
  const report = useGet<ReportResponse>(seq === null ? null : `/api/report/runs/${seq}`)

  return (
    <div className={SPLIT}>
      <SectionCard className={FULL} bodyClassName={BODY} testId="rebuild-runs">
        <ErrorBanner error={runs.error} className="mb-3" />
        {runs.loading && <Loading />}
        {runs.data && list.length === 0 && <Empty>no rebuild has run yet</Empty>}
        {list.length > 0 && (
          <Table className="table-fixed" wrapperClassName="overflow-x-visible" data-testid="rebuild-runs-table">
            <TableHeader className={STICKY_HEAD}>
              <TableRow>
                <TableHead className="w-32" hint="When this rebuild ran">Rebuild ({num(list.length)})</TableHead>
                <TableHead className="w-20" hint="Whether the rebuild succeeded or failed">Status</TableHead>
                <TableHead className={cn('w-24', NUM)} hint="How long the rebuild took">
                  Duration
                </TableHead>
                <TableHead hint="Totals that were not zero">Issues</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {list.map((run) => {
                const issues = Object.entries(run.totals).filter(([, v]) => v !== 0)
                return (
                  <TableRow
                    key={run.seq}
                    className="cursor-pointer"
                    data-testid="rebuild-run"
                    data-seq={run.seq}
                    data-state={run.seq === seq ? 'selected' : undefined}
                    aria-selected={run.seq === seq}
                    onClick={() => setSeq(run.seq)}
                  >
                    <TableCell className={TOP}>
                      <span className={cn(KEY, 'block')} title={run.created_at}>
                        {relTime(run.created_at)}
                      </span>
                      {shortDate(run.created_at)}
                    </TableCell>
                    <TableCell className={TOP}>
                      <Pill tone={run.ok ? 'ok' : 'err'}>{run.ok ? 'ok' : 'failed'}</Pill>
                    </TableCell>
                    <TableCell className={cn(NUM, TOP)}>{num(run.duration_ms)} ms</TableCell>
                    <TableCell className={TOP}>
                      {!run.ok ? (
                        <span className="text-xs text-dbb-clay">{run.error}</span>
                      ) : issues.length === 0 ? (
                        '—'
                      ) : (
                        <span className="inline-flex flex-wrap gap-1">
                          {issues.map(([k, v]) => (
                            <Chip key={k}>
                              {k}=<strong>{num(v)}</strong>
                            </Chip>
                          ))}
                        </span>
                      )}
                    </TableCell>
                  </TableRow>
                )
              })}
            </TableBody>
          </Table>
        )}
      </SectionCard>
      <div className="min-w-0 space-y-6 lg:min-h-0 lg:max-h-full lg:overflow-y-auto" data-testid="rebuild-receipt">
        <ErrorBanner error={report.error} />
        {report.loading && !report.data && <Loading />}
        {report.data?.ran && <Report report={report.data} />}
      </div>
    </div>
  )
}

function Mcp() {
  const index = useLoad(() => get<McpIndex>('/api/mcp'), [])
  const [copied, setCopied] = useState(false)
  const data = index.data
  const endpoint = `${window.location.origin}${data?.path ?? ''}`
  const copy = () => {
    if (!navigator.clipboard) return
    navigator.clipboard
      .writeText(endpoint)
      .then(() => {
        setCopied(true)
        setTimeout(() => setCopied(false), 1500)
      })
      .catch(() => {})
  }
  return (
    <div className="space-y-6">
      <SectionCard
        testId="mcp"
        title={data && <Mono>{endpoint}</Mono>}
        headerRight={
          data && (
            <Button size="sm" variant="outline" onClick={copy} data-testid="mcp-copy">
              {copied ? 'Copied' : 'Copy'}
            </Button>
          )
        }
      >
        <ErrorBanner error={index.error} />
        {index.loading && <Loading />}
        {data && data.tools.length === 0 && <Empty>no tools</Empty>}
        {data && data.tools.length > 0 && (
          <Table data-testid="mcp-tools">
            <TableHeader>
              <TableRow>
                <TableHead hint="What an agent can call here">Tool ({num(data.tools.length)})</TableHead>
                <TableHead hint="What the tool does">Description</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {data.tools.map((t) => (
                <TableRow key={t.name}>
                  <TableCell className={cn(NARROW, TOP)}>
                    <Mono>{t.name}</Mono>
                  </TableCell>
                  <TableCell className={TOP}>{t.description}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )}
      </SectionCard>
      {data && (
        <>
          <SectionCard testId="mcp-resources">
            {data.resources.length === 0 && <Empty>no resources</Empty>}
            {data.resources.length > 0 && (
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead hint="A file an agent can read">Resource ({num(data.resources.length)})</TableHead>
                    <TableHead hint="The address an agent uses to read it">URI</TableHead>
                    <TableHead hint="What the resource holds">Description</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {data.resources.map((r) => (
                    <TableRow key={r.uri}>
                      <TableCell className={cn(KEY, NARROW, TOP)}>{r.name}</TableCell>
                      <TableCell className={cn(NARROW, TOP)}>
                        <Mono>{r.uri}</Mono>
                      </TableCell>
                      <TableCell className={TOP}>{r.description}</TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            )}
          </SectionCard>
          <SectionCard testId="mcp-prompts">
            {data.prompts.length === 0 && <Empty>no prompts</Empty>}
            {data.prompts.length > 0 && (
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead hint="A ready-made instruction an agent can request">Prompt ({num(data.prompts.length)})</TableHead>
                    <TableHead hint="What the prompt asks for">Description</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {data.prompts.map((p) => (
                    <TableRow key={p.name}>
                      <TableCell className={cn(NARROW, TOP)}>
                        <Mono>{p.name}</Mono>
                      </TableCell>
                      <TableCell className={TOP}>{p.description}</TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            )}
          </SectionCard>
          <SectionCard title="Client config" testId="mcp-client">
            <p className="mb-3 text-sm text-dbb-muted">One line for Claude Code, or the JSON for Claude Desktop and Cursor.</p>
            <div className="space-y-3">
              <pre className={PRE}>{`claude mcp add --transport http os ${endpoint}`}</pre>
              <pre className={PRE}>{JSON.stringify({ mcpServers: { os: { type: 'http', url: endpoint } } }, null, 2)}</pre>
            </div>
          </SectionCard>
        </>
      )}
    </div>
  )
}

export function Config() {
  const [sources, setSources] = useState<SourcesResponse | null>(null)
  const [sourcesError, setSourcesError] = useState<ApiError | null>(null)
  const [enabled, setEnabled] = useState('')
  const [syncing, setSyncing] = useState<string | null>(null)
  const [sync, setSync] = useState<SyncResponse | null>(null)
  const [syncError, setSyncError] = useState<ApiError | null>(null)
  const [pending, setPending] = useState(() => new Set<string>())
  const [rebuilding, setRebuilding] = useState(false)
  const [rebuild, setRebuild] = useState<RebuildResponse | null>(null)
  const [rebuildError, setRebuildError] = useState<ApiError | null>(null)
  const [rebuilds, setRebuilds] = useState(0)

  const loadSources = () =>
    api
      .sources()
      .then((r) => {
        setSources(r)
        setSourcesError(null)
      })
      .catch((e) => setSourcesError(asApiError(e)))

  useEffect(() => {
    loadSources()
  }, [])

  const runSync = async (only?: string[]) => {
    setSyncing(only ? only.join(',') : 'all')
    setSyncError(null)
    try {
      setSync(await api.sync(only))
    } catch (e) {
      setSyncError(asApiError(e))
    } finally {
      setSyncing(null)
      loadSources()
    }
  }

  const toggleEnabled = async (r: SourceRow) => {
    setPending((p) => new Set(p).add(r.source))
    setSyncError(null)
    try {
      await put(`/api/sources/${encodeURIComponent(r.source)}/enabled`, { enabled: !r.enabled })
    } catch (e) {
      setSyncError(asApiError(e))
    } finally {
      setPending((p) => {
        const next = new Set(p)
        next.delete(r.source)
        return next
      })
      loadSources()
    }
  }

  const runRebuild = async () => {
    setRebuilding(true)
    setRebuildError(null)
    try {
      setRebuild(await api.rebuild())
      setRebuilds((n) => n + 1)
    } catch (e) {
      setRebuildError(asApiError(e))
    } finally {
      setRebuilding(false)
    }
  }

  const all = sources?.sources ?? []
  const rows = all.filter((r) => !enabled || enabledKey(r) === enabled)

  return (
    <Tabs defaultValue="sources" className={PAGE_FILL}>
      <TabsList className="shrink-0">
        <TabsTrigger value="sources" data-testid="tab-sources">
          Sources
        </TabsTrigger>
        <TabsTrigger value="rebuild" data-testid="tab-rebuild">
          Rebuild
        </TabsTrigger>
        <TabsTrigger value="mcp" data-testid="tab-mcp">
          MCP
        </TabsTrigger>
      </TabsList>

      <TabsContent value="sources" className={TAB} data-testid="tabpanel-sources">
        <SectionCard
          testId="sources"
          title={
            <div className="flex items-center gap-2">
              <Filter
                value={enabled}
                onChange={setEnabled}
                all={`all sources (${num(all.length)})`}
                options={enabledOptions(all)}
                testId="sources-enabled-filter"
              />
            </div>
          }
          description={
            sync || syncError || rebuild || rebuildError ? (
              <div className={NOTICES}>
                <ErrorBanner error={syncError} testId="sync-error" />
                {sync && <SyncBanner sync={sync} />}
                {rebuildError?.status === 409 ? (
                  <Banner testId="rebuild-error">
                    <Mono>409</Mono> rebuild in progress — {rebuildError.detail}
                  </Banner>
                ) : (
                  <ErrorBanner error={rebuildError} testId="rebuild-error" />
                )}
                {rebuild && (
                  <Banner tone={rebuild.ok ? 'warn' : 'err'} testId="rebuild-banner">
                    {rebuild.ok ? 'rebuilt' : 'rebuild failed'} · {num(rebuild.duration_ms)} ms · {num(rebuild.raw_events_read)} raw events ·{' '}
                    {num(rebuild.entities)} entities · {num(rebuild.facts)} facts
                  </Banner>
                )}
              </div>
            ) : null
          }
          headerRight={
            <div className="flex gap-2">
              <Button size="sm" disabled={syncing !== null || !sources} onClick={() => runSync()} data-testid="sync-all">
                {syncing === 'all' ? 'syncing…' : 'Sync all'}
              </Button>
              <Button size="sm" variant="outline" disabled={rebuilding} onClick={runRebuild} data-testid="rebuild">
                {rebuilding ? 'rebuilding…' : 'Rebuild'}
              </Button>
            </div>
          }
          className={FULL}
          bodyClassName={BODY}
        >
          <ErrorBanner error={sourcesError} className="mb-3" />
          {!sources && !sourcesError && <Loading />}
          {sources && rows.length === 0 && <Empty>no sources</Empty>}
          {rows.length > 0 && (
            <Table className="table-fixed" wrapperClassName="overflow-x-visible" data-testid="sources-table">
              <TableHeader className={STICKY_HEAD}>
                <TableRow>
                  <TableHead className="w-56" hint="The external tool data comes from">Source ({num(rows.length)})</TableHead>
                  <TableHead className="w-56" hint="What kinds of things this source provides">Entities</TableHead>
                  <TableHead className="w-40" hint="When the last sync ran and whether it worked">Last sync</TableHead>
                  <TableHead className="w-40" hint="When this source last brought new data">Rows</TableHead>
                  <TableHead className="w-24" hint="Whether this source is allowed to sync">Enabled</TableHead>
                  <TableHead className="w-24" />
                </TableRow>
              </TableHeader>
              <TableBody>
                {rows.map((r) => {
                  const last = sync?.results.find((s) => s.source === r.source)
                  const lastOk = r.last_success === r.last_attempt
                  return (
                    <TableRow key={r.source} data-testid="sources-row" data-source={r.source}>
                      <TableCell className={TOP}>
                        <span className={cn(KEY, 'block')}>{r.label}</span>
                        <Mono>{r.source}</Mono>
                      </TableCell>
                      <TableCell className={TOP}>
                        {r.entities.length === 0 ? (
                          '—'
                        ) : (
                          <span className="inline-flex flex-wrap gap-1">
                            {r.entities.map((e) => (
                              <Pill key={e}>{e}</Pill>
                            ))}
                          </span>
                        )}
                      </TableCell>
                      <TableCell className={TOP}>
                        {r.last_attempt === null ? (
                          'never'
                        ) : (
                          <span className="whitespace-nowrap">
                            <Pill tone={lastOk ? 'ok' : 'err'}>{lastOk ? 'ok' : 'failed'}</Pill> {relTime(r.last_attempt)}
                          </span>
                        )}
                        {r.detail && <span className="block text-xs text-dbb-clay">{r.detail}</span>}
                      </TableCell>
                      <TableCell className={TOP}>
                        {last ? (
                          <>
                            {num(last.rows_written)} written / {num(last.rows_fetched)} fetched
                            {last.rows_refused ? (
                              <>
                                {' '}
                                <Pill tone="err">{num(last.rows_refused)} refused</Pill>
                              </>
                            ) : null}
                            {last.rows_colliding ? (
                              <>
                                {' '}
                                <Pill tone="warn">{num(last.rows_colliding)} colliding</Pill>
                              </>
                            ) : null}
                          </>
                        ) : (
                          `new data ${relTime(r.last_new_data)}`
                        )}
                      </TableCell>
                      <TableCell className={TOP}>
                        <span className={cn(pending.has(r.source) && 'pointer-events-none opacity-50')}>
                          <FilterChip
                            on={r.enabled}
                            onClick={() => (pending.has(r.source) ? undefined : toggleEnabled(r))}
                            data-testid={`source-enabled-${r.source}`}
                          >
                            {r.enabled ? 'on' : 'off'}
                          </FilterChip>
                        </span>
                      </TableCell>
                      <TableCell className={cn('pr-0 text-right', TOP)}>
                        <Button
                          size="sm"
                          variant="outline"
                          disabled={syncing !== null || !r.enabled}
                          onClick={() => runSync([r.source])}
                          data-testid={`source-sync-${r.source}`}
                        >
                          {syncing === r.source ? 'syncing…' : 'Sync'}
                        </Button>
                      </TableCell>
                    </TableRow>
                  )
                })}
              </TableBody>
            </Table>
          )}
        </SectionCard>
      </TabsContent>

      <TabsContent value="rebuild" className={TAB} data-testid="tabpanel-rebuild">
        <Rebuilds rebuilds={rebuilds} />
      </TabsContent>

      <TabsContent value="mcp" className={TAB_SCROLL} data-testid="tabpanel-mcp">
        <Mcp />
      </TabsContent>
    </Tabs>
  )
}
