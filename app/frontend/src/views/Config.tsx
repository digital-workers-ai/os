import { useEffect, useState, type ReactNode } from 'react'
import {
  api,
  asApiError,
  type ApiError,
  type RebuildResponse,
  type ReportResponse,
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
import { Pill } from '@/components/ui/pill'
import { STICKY_HEAD, Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { num, plural, relTime } from '@/lib/format'
import { cn } from '@/lib/utils'

type Ran = Extract<ReportResponse, { ran: true }>

const MONO = 'font-mono text-xs'
const NUM = 'text-right tabular-nums'
const KEY = 'font-medium text-dbb-charcoal'
const TOP = 'align-top'
const PAGE_FILL = 'lg:flex lg:flex-col lg:h-[calc(100vh-11.25rem-1px)]'
const TAB_FILL = 'lg:min-h-0 lg:flex-1 lg:overflow-y-auto'
const FULL = 'min-w-0 lg:flex lg:flex-col lg:h-full'
const BODY = 'lg:min-h-0 lg:overflow-y-auto lg:-mx-6 lg:px-6 lg:-mb-6 lg:pb-6 lg:rounded-b-xl'
const NOTICES = 'mt-2 -mb-1 flex flex-col gap-3 [&>*]:mb-0'

const enabledKey = (r: SourceRow) => (r.enabled_by_default ? 'enabled' : 'disabled')

const enabledOptions = (rows: SourceRow[]): [string, number][] => {
  const on = rows.filter((r) => r.enabled_by_default).length
  return [
    ['enabled', on],
    ['disabled', rows.length - on],
  ]
}

function SyncBanner({ sync }: { sync: SyncResponse }) {
  const total = (k: 'rows_fetched' | 'rows_written' | 'rows_refused' | 'rows_colliding') =>
    num(sync.results.reduce((n, r) => n + r[k], 0))
  return (
    <Banner tone={sync.failed > 0 ? 'err' : 'warn'}>
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

function CountTable({ label, rows }: { label: string; rows: Record<string, number> }) {
  const entries = Object.entries(rows)
  if (entries.length === 0) return null
  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead>
            {label} ({num(entries.length)})
          </TableHead>
          <TableHead className={NUM}>Count</TableHead>
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

function Report({ report, error, refresh }: { report: Ran; error: ApiError | null; refresh: ReactNode }) {
  const r = report.report
  const rates = Object.entries(r.match_rates)
  return (
    <div className="space-y-6">
      <ErrorBanner error={error} />
      <SectionCard
        title={
          <>
            <Pill tone={report.ok ? 'ok' : 'err'}>{report.ok ? 'ok' : 'failed'}</Pill> · ran {relTime(report.created_at)} ·{' '}
            {num(report.duration_ms)} ms · {num(report.raw_events_read)} raw events read · {num(report.entities)} entities ·{' '}
            {num(report.facts)} facts
          </>
        }
        headerRight={refresh}
      >
        <CountTable label="Total" rows={r.totals} />
      </SectionCard>
      {r.quarantines.length > 0 && (
        <SectionCard>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Quarantine ({num(r.quarantines.length)})</TableHead>
                <TableHead>Record</TableHead>
                <TableHead>Detail</TableHead>
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
        <SectionCard>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Oversized ({num(r.oversized.length)})</TableHead>
                <TableHead>Detail</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {r.oversized.map((o, i) => (
                <TableRow key={i}>
                  <TableCell className={cn('w-px whitespace-nowrap', TOP)}>
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
        <SectionCard>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Dead path ({num(r.dead_paths.length)})</TableHead>
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
        <SectionCard>
          <CountTable label="Disagreement" rows={r.disagreements} />
        </SectionCard>
      )}
      {rates.length > 0 && (
        <SectionCard>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Relationship ({num(rates.length)})</TableHead>
                <TableHead className={NUM}>Candidates</TableHead>
                <TableHead className={NUM}>Matched</TableHead>
                <TableHead className={NUM}>Edges</TableHead>
                <TableHead className={NUM}>Rate</TableHead>
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
      <SectionCard title="Receipts">
        <p className="mb-3 text-sm text-dbb-muted">The full report of the last rebuild, exactly as the engine produced it.</p>
        <pre className="overflow-auto rounded-lg bg-dbb-surface p-3 font-mono text-xs">{JSON.stringify(r, null, 2)}</pre>
      </SectionCard>
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
  const [rebuilding, setRebuilding] = useState(false)
  const [rebuild, setRebuild] = useState<RebuildResponse | null>(null)
  const [rebuildError, setRebuildError] = useState<ApiError | null>(null)
  const [report, setReport] = useState<ReportResponse | null>(null)
  const [reportError, setReportError] = useState<ApiError | null>(null)

  const loadSources = () =>
    api
      .sources()
      .then((r) => {
        setSources(r)
        setSourcesError(null)
      })
      .catch((e) => setSourcesError(asApiError(e)))

  const loadReport = () =>
    api
      .report()
      .then((r) => {
        setReport(r)
        setReportError(null)
      })
      .catch((e) => setReportError(asApiError(e)))

  useEffect(() => {
    loadSources()
    loadReport()
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

  const runRebuild = async () => {
    setRebuilding(true)
    setRebuildError(null)
    try {
      setRebuild(await api.rebuild())
    } catch (e) {
      setRebuildError(asApiError(e))
    } finally {
      setRebuilding(false)
      loadReport()
    }
  }

  const all = sources?.sources ?? []
  const rows = all.filter((r) => !enabled || enabledKey(r) === enabled)
  const refresh = (
    <Button size="sm" variant="outline" onClick={loadReport}>
      Refresh
    </Button>
  )

  return (
    <Tabs defaultValue="sources" className={PAGE_FILL}>
      <TabsList className="shrink-0">
        <TabsTrigger value="sources">Sources</TabsTrigger>
        <TabsTrigger value="rebuild">Rebuild</TabsTrigger>
      </TabsList>

      <TabsContent value="sources" className="lg:min-h-0 lg:flex-1">
        <SectionCard
          title={
            <div className="flex items-center gap-2">
              <Filter value={enabled} onChange={setEnabled} all={`all sources (${num(all.length)})`} options={enabledOptions(all)} />
            </div>
          }
          description={
            sync || syncError || rebuild || rebuildError ? (
              <div className={NOTICES}>
                <ErrorBanner error={syncError} />
                {sync && <SyncBanner sync={sync} />}
                {rebuildError?.status === 409 ? (
                  <Banner>
                    <Mono>409</Mono> rebuild in progress — {rebuildError.detail}
                  </Banner>
                ) : (
                  <ErrorBanner error={rebuildError} />
                )}
                {rebuild && (
                  <Banner tone={rebuild.ok ? 'warn' : 'err'}>
                    {rebuild.ok ? 'rebuilt' : 'rebuild failed'} · {num(rebuild.duration_ms)} ms · {num(rebuild.raw_events_read)} raw events ·{' '}
                    {num(rebuild.entities)} entities · {num(rebuild.facts)} facts
                  </Banner>
                )}
              </div>
            ) : null
          }
          headerRight={
            <div className="flex gap-2">
              <Button size="sm" disabled={syncing !== null || !sources} onClick={() => runSync()}>
                {syncing === 'all' ? 'syncing…' : 'Sync all'}
              </Button>
              <Button size="sm" variant="outline" disabled={rebuilding} onClick={runRebuild}>
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
            <Table className="table-fixed" wrapperClassName="overflow-x-visible">
              <TableHeader className={STICKY_HEAD}>
                <TableRow>
                  <TableHead className="w-56">Source ({num(rows.length)})</TableHead>
                  <TableHead className="w-56">Entities</TableHead>
                  <TableHead className="w-40">Last sync</TableHead>
                  <TableHead className="w-40">Rows</TableHead>
                  <TableHead className="w-24">Enabled</TableHead>
                  <TableHead className="w-24" />
                </TableRow>
              </TableHeader>
              <TableBody>
                {rows.map((r) => {
                  const last = sync?.results.find((s) => s.source === r.source)
                  const lastOk = r.last_success === r.last_attempt
                  return (
                    <TableRow key={r.source}>
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
                      <TableCell className={TOP}>{r.enabled_by_default ? <Pill tone="ok">on</Pill> : <Pill>off</Pill>}</TableCell>
                      <TableCell className={cn('pr-0 text-right', TOP)}>
                        <Button size="sm" variant="outline" disabled={syncing !== null} onClick={() => runSync([r.source])}>
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

      <TabsContent value="rebuild" className={TAB_FILL}>
        {report?.ran ? (
          <Report report={report} error={reportError} refresh={refresh} />
        ) : (
          <SectionCard headerRight={refresh}>
            <ErrorBanner error={reportError} />
            {!report && !reportError && <Loading />}
            {report && !report.ran && <Empty>{report.detail}</Empty>}
          </SectionCard>
        )}
      </TabsContent>
    </Tabs>
  )
}
