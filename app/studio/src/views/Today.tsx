import type { ReactNode } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { asApiError, getToday } from '@/api'
import { ErrorBanner } from '@/components/ui/banner'
import { Card, CardHeader, CardTitle } from '@/components/ui/card'
import { Empty } from '@/components/ui/empty'
import { Loading } from '@/components/ui/loading'
import { Mono } from '@/components/ui/mono'
import { Pill } from '@/components/ui/pill'
import { hhmm, kindGlyph, since, stateMark, weekday } from '@/lib/calendar'

const link = 'text-xs text-ink underline underline-offset-2'

function Section({ title, testId, count, empty, children }: { title: string; testId: string; count: number; empty: string; children: ReactNode }) {
  return (
    <Card data-testid={testId}>
      <CardHeader>
        <CardTitle>{title}</CardTitle>
        <span className="text-xs tabular-nums text-muted">{count}</span>
      </CardHeader>
      {count === 0 ? <Empty testId={`${testId}-empty`}>{empty}</Empty> : <ul className="flex flex-col gap-2">{children}</ul>}
    </Card>
  )
}

export function Today() {
  const query = useQuery({ queryKey: ['today'], queryFn: getToday })
  if (query.isPending)
    return (
      <div data-testid="today-view" data-state="loading">
        <Loading />
      </div>
    )
  if (query.isError)
    return (
      <div data-testid="today-view" data-state="error">
        <ErrorBanner error={asApiError(query.error)} />
      </div>
    )
  const { today, last_run, week, building, built_today } = query.data
  const idle = week.length === 0 && building.length === 0 && built_today.length === 0
  return (
    <div className="flex flex-col gap-4" data-testid="today-view" data-state="ready">
      <p className="text-sm text-muted" data-testid="today-header">
        {last_run ? `${today} · ${last_run.agent} ran ${hhmm(last_run.created_at)} · read ${last_run.read_detail}` : `${today} · no agent run yet`}
      </p>
      {idle ? (
        <Card data-testid="today-empty">
          <p className="text-sm text-muted">
            Nothing planned, building or built today.{' '}
            <Link to="/create" className="text-ink underline underline-offset-2" data-testid="today-empty-create">
              Make something
            </Link>{' '}
            or{' '}
            <Link to="/calendar" className="text-ink underline underline-offset-2" data-testid="today-empty-calendar">
              fill the calendar
            </Link>
            .
          </p>
        </Card>
      ) : (
        <div className="grid gap-4 md:grid-cols-3">
          <Section title="This week" testId="today-week" count={week.length} empty="nothing planned this week">
            {week.map((slot) => (
              <li key={`${slot.date}/${slot.name}`} className="flex items-center gap-2 text-sm" data-testid="today-slot" data-state={slot.state}>
                <span className="w-8 shrink-0 text-muted">{weekday(slot.date)}</span>
                <span className="shrink-0 text-muted" title={slot.kind}>
                  {kindGlyph(slot.kind)}
                </span>
                <span className="min-w-0 flex-1 truncate text-ink">{slot.name}</span>
                <span className="shrink-0" title={slot.state}>
                  {stateMark(slot.state)}
                </span>
                {slot.state === 'built' && slot.asset_seq !== null && (
                  <Link to={`/assets/${slot.asset_seq}`} className={link} data-testid="today-slot-link">
                    open
                  </Link>
                )}
              </li>
            ))}
          </Section>
          <Section title="Building" testId="today-building" count={building.length} empty="nothing building">
            {building.map((run) => (
              <li key={run.seq} className="flex items-center gap-2 text-sm" data-testid="today-run" data-status={run.status}>
                <Mono className="min-w-0 flex-1 truncate">{run.skill}</Mono>
                <Pill tone={run.status === 'failed' || run.status === 'held' ? 'down' : 'unknown'}>{run.stage ?? run.status}</Pill>
                <span className="shrink-0 text-xs text-muted">{since(run.started_at)}</span>
                {run.asset_seq !== null && (
                  <Link to={`/assets/${run.asset_seq}`} className={link} data-testid="today-run-link">
                    open
                  </Link>
                )}
              </li>
            ))}
          </Section>
          <Section title="Built today" testId="today-built" count={built_today.length} empty="nothing built yet">
            {built_today.map((asset) => (
              <li key={asset.seq} className="flex items-center gap-2 text-sm" data-testid="today-asset" data-seq={asset.seq}>
                <Link to={`/assets/${asset.seq}`} className="min-w-0 flex-1 truncate text-ink underline-offset-2 hover:underline" data-testid="today-asset-link">
                  {asset.name}
                </Link>
                <Pill title={asset.kind}>
                  {kindGlyph(asset.kind)} {asset.kind}
                </Pill>
              </li>
            ))}
          </Section>
        </div>
      )}
    </div>
  )
}
