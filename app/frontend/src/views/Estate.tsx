import { useEffect, useState, type ReactNode } from 'react'
import {
  api,
  asApiError,
  type ApiError,
  type EngineReport,
  type RebuildResponse,
  type ReportResponse,
  type SourcesResponse,
  type SyncResponse,
} from '@/api'
import { SectionCard } from '@/components/SectionCard'
import { Section } from '@/components/SectionHeading'
import { Banner, ErrorBanner } from '@/components/ui/banner'
import { Button } from '@/components/ui/button'
import { Empty } from '@/components/ui/empty'
import { Mono } from '@/components/ui/mono'
import { PAGE, Pager } from '@/components/ui/pager'
import { Pill, type Tone } from '@/components/ui/pill'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { num, relTime } from '@/lib/format'
import { cn } from '@/lib/utils'
import { Activity, KEY, LINK, MONO, NUM, PRE } from './estate/Activity'

const validationTone = (v: string): Tone =>
  v === 'provider-validated' ? 'ok' : v === 'mock-validated' ? 'warn' : 'neutral'

function Group({ title, count, children }: { title: string; count: number; children: ReactNode }) {
  return (
    <Section
      title={
        <>
          {title} · {num(count)}
        </>
      }
    >
      {count === 0 ? <p className="text-sm text-dbb-muted">none</p> : children}
    </Section>
  )
}

function Counts({ title, rows }: { title: string; rows: Record<string, number> }) {
  const entries = Object.entries(rows || {})
  return (
    <Group title={title} count={entries.length}>
      <div className="columns-2 gap-6 text-sm xl:columns-3">
        {entries.map(([k, v]) => (
          <div key={k} className="flex justify-between gap-3 border-b border-dbb-warm/30 py-1 break-inside-avoid">
            <span className={cn(KEY, MONO, 'break-all')}>{k}</span>
            <span className="tabular-nums text-dbb-muted">{num(v)}</span>
          </div>
        ))}
      </div>
    </Group>
  )
}

const SECTIONED: (keyof EngineReport)[] = [
  'totals',
  'skips',
  'records_skipped',
  'identity_less',
  'dangling_refs',
  'quarantines',
  'oversized',
  'clears',
  'dead_paths',
  'disagreements',
  'match_rates',
  'counts',
]

function Report({ report }: { report: EngineReport }) {
  const other = Object.entries(report).filter(([k]) => !SECTIONED.includes(k as keyof EngineReport))
  return (
    <>
      <Counts title="totals" rows={report.totals} />
      <Counts title="counts" rows={report.counts} />
      <Counts title="skips" rows={report.skips} />
      <Counts title="records_skipped" rows={report.records_skipped} />
      <Counts title="identity_less" rows={report.identity_less} />
      <Counts title="dangling_refs" rows={report.dangling_refs} />
      <Counts title="clears" rows={report.clears} />
      <Counts title="disagreements" rows={report.disagreements} />
      <Group title="quarantines" count={report.quarantines.length}>
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Relationship</TableHead>
              <TableHead>Record</TableHead>
              <TableHead>Detail</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {report.quarantines.map((q, i) => (
              <TableRow key={i}>
                <TableCell className={KEY}>{q.rel}</TableCell>
                <TableCell className={MONO}>{q.record}</TableCell>
                <TableCell>{q.detail}</TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </Group>
      <Group title="oversized" count={report.oversized.length}>
        <Table>
          <TableBody>
            {report.oversized.map((o, i) => (
              <TableRow key={i}>
                <TableCell className="w-px whitespace-nowrap">
                  <Pill tone="warn">{o.kind}</Pill>
                </TableCell>
                <TableCell>
                  <Mono>{JSON.stringify(o)}</Mono>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </Group>
      <Group title="dead_paths" count={report.dead_paths.length}>
        <div className="columns-2 gap-6 xl:columns-3">
          {report.dead_paths.map((p) => (
            <div key={p} className={cn(MONO, 'border-b border-dbb-warm/30 py-1 break-inside-avoid')}>
              {p}
            </div>
          ))}
        </div>
      </Group>
      <Group title="match_rates" count={Object.keys(report.match_rates).length}>
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Relationship</TableHead>
              <TableHead className={NUM}>Candidates</TableHead>
              <TableHead className={NUM}>Matched</TableHead>
              <TableHead className={NUM}>Edges</TableHead>
              <TableHead className={NUM}>Rate</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {Object.entries(report.match_rates).map(([rel, r]) => (
              <TableRow key={rel}>
                <TableCell className={KEY}>{rel}</TableCell>
                <TableCell className={NUM}>{num(r.candidates)}</TableCell>
                <TableCell className={NUM}>{num(r.matched)}</TableCell>
                <TableCell className={NUM}>{num(r.edges)}</TableCell>
                <TableCell className={NUM}>{r.match_rate === null ? '—' : r.match_rate}</TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </Group>
      {other.length > 0 && (
        <Section title="Other keys">
          <pre className={PRE}>{JSON.stringify(Object.fromEntries(other), null, 2)}</pre>
        </Section>
      )}
      <Section title="Raw report">
        <pre className={PRE}>{JSON.stringify(report, null, 2)}</pre>
      </Section>
    </>
  )
}

export function Estate() {
  const [tab, setTab] = useState('sources')
  const [sources, setSources] = useState<SourcesResponse | null>(null)
  const [sourcesError, setSourcesError] = useState<ApiError | null>(null)
  const [syncing, setSyncing] = useState<string | null>(null)
  const [sync, setSync] = useState<SyncResponse | null>(null)
  const [syncError, setSyncError] = useState<ApiError | null>(null)
  const [synced, setSynced] = useState(0)
  const [activitySource, setActivitySource] = useState('')
  const [rebuilding, setRebuilding] = useState(false)
  const [rebuild, setRebuild] = useState<RebuildResponse | null>(null)
  const [rebuildError, setRebuildError] = useState<ApiError | null>(null)
  const [report, setReport] = useState<ReportResponse | null>(null)
  const [reportError, setReportError] = useState<ApiError | null>(null)
  const [offset, setOffset] = useState(0)

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

  useEffect(() => setOffset(0), [sources])

  const runSync = async (only?: string[]) => {
    setSyncing(only ? only.join(',') : 'all')
    setSyncError(null)
    try {
      setSync(await api.sync(only))
    } catch (e) {
      setSyncError(asApiError(e))
    } finally {
      setSyncing(null)
      setSynced((n) => n + 1)
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

  const showActivity = (source: string) => {
    setActivitySource(source)
    setTab('activity')
  }

  const rows = sources?.sources ?? []
  const page = rows.slice(offset, offset + PAGE)

  return (
    <Tabs value={tab} onValueChange={setTab}>
      <TabsList>
        <TabsTrigger value="sources">Sources</TabsTrigger>
        <TabsTrigger value="activity">Activity</TabsTrigger>
        <TabsTrigger value="report">Report</TabsTrigger>
      </TabsList>

      <TabsContent value="sources">
        <SectionCard
          title={`Sources${sources ? ` (${rows.length})` : ''}`}
          description={sources?.validation_coverage.detail}
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
        >
          <ErrorBanner error={sourcesError} className="mb-3" />
          {!sources && !sourcesError ? (
            <Empty>loading…</Empty>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Source</TableHead>
                  <TableHead>Validation</TableHead>
                  <TableHead>Entities</TableHead>
                  <TableHead>Last sync</TableHead>
                  <TableHead className={NUM}>Attempts</TableHead>
                  <TableHead>Rows</TableHead>
                  <TableHead>Enabled</TableHead>
                  <TableHead>Detail</TableHead>
                  <TableHead />
                </TableRow>
              </TableHeader>
              <TableBody>
                {page.map((r) => {
                  const last = sync?.results.find((s) => s.source === r.source)
                  const lastOk = r.last_success === r.last_attempt
                  return (
                    <TableRow key={r.source}>
                      <TableCell className="whitespace-nowrap">
                        <button type="button" className={cn(KEY, LINK)} title="show activity" onClick={() => showActivity(r.source)}>
                          {r.label}
                        </button>{' '}
                        <Mono>{r.source}</Mono>
                      </TableCell>
                      <TableCell>
                        <Pill tone={validationTone(r.validation)}>{r.validation}</Pill>
                      </TableCell>
                      <TableCell>{r.entities.join(', ') || '—'}</TableCell>
                      <TableCell className="whitespace-nowrap">
                        {r.last_attempt === null ? (
                          'never'
                        ) : (
                          <>
                            <Pill tone={lastOk ? 'ok' : 'err'}>{lastOk ? 'ok' : 'failed'}</Pill> {relTime(r.last_attempt)}
                          </>
                        )}
                      </TableCell>
                      <TableCell className={NUM}>{num(r.attempts)}</TableCell>
                      <TableCell className="whitespace-nowrap">
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
                      <TableCell>{r.enabled_by_default ? 'on' : 'off'}</TableCell>
                      <TableCell>{r.detail || ''}</TableCell>
                      <TableCell className="pr-0 text-right">
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
          {rows.length > 0 && <Pager offset={offset} count={page.length} total={rows.length} onPage={setOffset} />}

          {(sync || syncError) && (
            <Section title="Last sync">
              <ErrorBanner error={syncError} className="mb-3" />
              {sync && (
                <>
                  <p className="mb-3 text-sm text-dbb-muted">
                    {sync.ok} ok, {sync.failed} failed, {num(sync.rows_written)} rows written.
                  </p>
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead>Source</TableHead>
                        <TableHead>Ok</TableHead>
                        <TableHead className={NUM}>Fetched</TableHead>
                        <TableHead className={NUM}>Written</TableHead>
                        <TableHead className={NUM}>Refused</TableHead>
                        <TableHead className={NUM}>Colliding</TableHead>
                        <TableHead className={NUM}>Pages</TableHead>
                        <TableHead>Truncated</TableHead>
                        <TableHead>Detail</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {sync.results.map((r) => (
                        <TableRow key={r.source}>
                          <TableCell className={cn(KEY, MONO)}>{r.source}</TableCell>
                          <TableCell>
                            <Pill tone={r.ok ? 'ok' : 'err'}>{r.ok ? 'ok' : 'failed'}</Pill>
                          </TableCell>
                          <TableCell className={NUM}>{num(r.rows_fetched)}</TableCell>
                          <TableCell className={NUM}>{num(r.rows_written)}</TableCell>
                          <TableCell className={NUM}>{num(r.rows_refused)}</TableCell>
                          <TableCell className={NUM}>{num(r.rows_colliding)}</TableCell>
                          <TableCell className={NUM}>{num(r.pages_read)}</TableCell>
                          <TableCell>{r.truncated ? 'yes' : 'no'}</TableCell>
                          <TableCell>{r.detail || ''}</TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                </>
              )}
            </Section>
          )}

          {(rebuild || rebuildError) && (
            <Section title="Rebuild">
              {rebuildError?.status === 409 ? (
                <Banner>
                  <Mono>409</Mono> rebuild in progress — {rebuildError.detail}
                </Banner>
              ) : (
                <ErrorBanner error={rebuildError} />
              )}
              {rebuild && (
                <p className="text-sm text-dbb-muted">
                  <Pill tone={rebuild.ok ? 'ok' : 'err'}>{rebuild.ok ? 'ok' : 'failed'}</Pill> · {num(rebuild.entities)} entities ·{' '}
                  {num(rebuild.canonical)} canonical · {num(rebuild.links)} links · {num(rebuild.facts)} facts ·{' '}
                  {num(rebuild.raw_events_read)} raw events read · {num(rebuild.duration_ms)} ms
                </p>
              )}
            </Section>
          )}
        </SectionCard>
      </TabsContent>

      <TabsContent value="activity">
        <Activity sources={rows} source={activitySource} onSource={setActivitySource} tick={synced} />
      </TabsContent>

      <TabsContent value="report">
        <SectionCard
          title="Report"
          description={
            report?.ran && (
              <>
                <Pill tone={report.ok ? 'ok' : 'err'}>{report.ok ? 'ok' : 'failed'}</Pill> · ran {relTime(report.created_at)} ·{' '}
                {num(report.duration_ms)} ms · {num(report.raw_events_read)} raw events read · {num(report.entities)} entities ·{' '}
                {num(report.facts)} facts
              </>
            )
          }
          headerRight={
            <Button size="sm" variant="outline" onClick={loadReport}>
              Refresh
            </Button>
          }
        >
          <ErrorBanner error={reportError} className="mb-3" />
          {!report && !reportError && <Empty>loading…</Empty>}
          {report && !report.ran && <Empty>{report.detail}</Empty>}
          {report?.ran && <Report report={report.report} />}
        </SectionCard>
      </TabsContent>
    </Tabs>
  )
}
