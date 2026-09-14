import type { ReactNode } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { ExternalLink } from 'lucide-react'
import { asApiError, getToday, type ProposalRow, type SkillRunRow, type Slot, type TodayResponse } from '@/api'
import { ErrorBanner } from '@/components/ui/banner'
import { buttonVariants } from '@/components/ui/button'
import { Card } from '@/components/ui/card'
import { Empty } from '@/components/ui/empty'
import { Loading } from '@/components/ui/loading'
import { Mono } from '@/components/ui/mono'
import { dayMonth, hhmm, kindGlyph, since, stateMark, stateTone, weekday } from '@/lib/calendar'
import { cn } from '@/lib/utils'

const ROW = 'flex flex-wrap items-baseline gap-x-2 gap-y-0.5 py-1.5 text-sm'

function Panel({ title, count, testId, children }: { title: string; count?: number; testId: string; children: ReactNode }) {
  return (
    <Card className="flex flex-col p-4 sm:p-5" data-testid={testId}>
      <h2 className="mb-1 border-b border-line pb-1.5 text-xs font-medium uppercase tracking-wide text-muted">
        {title}
        {count === undefined ? null : <span className="ml-1 tabular-nums">({count})</span>}
      </h2>
      <div className="divide-y divide-line/30">{children}</div>
    </Card>
  )
}

function OpenProposal({ row }: { row: ProposalRow }) {
  return (
    <Link to={`/proposals/${row.seq}`} className={cn(ROW, 'group hover:bg-wash')} data-testid="today-proposal" data-seq={row.seq}>
      <span className={stateTone('proposed')}>◔</span>
      <Mono className="text-muted">#{row.seq}</Mono>
      <span className="text-muted">{row.kind}</span>
      <span className="min-w-0 flex-1 truncate font-medium text-ink group-hover:underline">{row.title}</span>
    </Link>
  )
}

function WeekSlot({ slot }: { slot: Slot }) {
  const body = (
    <>
      <span className="w-8 shrink-0 text-muted">{weekday(slot.date)}</span>
      <span className="w-5 shrink-0 text-center text-muted">{kindGlyph(slot.kind)}</span>
      <span className="min-w-0 flex-1 truncate text-ink">{slot.name}</span>
      {slot.reactive && <span className="text-down">!</span>}
      <span className={stateTone(slot.state)}>{stateMark(slot.state)}</span>
      <span className="text-muted">{slot.proposal_seq === null ? slot.state : `#${slot.proposal_seq}`}</span>
    </>
  )
  if (slot.proposal_seq === null)
    return (
      <div className={ROW} data-testid="today-slot" data-state={slot.state}>
        {body}
      </div>
    )
  return (
    <Link
      to={`/proposals/${slot.proposal_seq}`}
      className={cn(ROW, 'hover:bg-wash')}
      data-testid="today-slot"
      data-state={slot.state}
    >
      {body}
    </Link>
  )
}

function Building({ run }: { run: SkillRunRow }) {
  return (
    <Link
      to={run.proposal_seq === null ? '/activity' : `/proposals/${run.proposal_seq}`}
      className={cn(ROW, 'hover:bg-wash')}
      data-testid="today-run"
      data-seq={run.seq}
    >
      <span className="text-ink">◔</span>
      <Mono className="text-muted">{run.skill}</Mono>
      <span className="min-w-0 flex-1 truncate text-ink">{run.stage ?? run.status}</span>
      <span className="text-muted">{since(run.started_at)}</span>
    </Link>
  )
}

function Nothing({ today }: { today: string }) {
  return (
    <Card data-testid="today-empty">
      <p className="text-sm text-ink">Nothing proposed yet. The marketer runs at 06:00 and drafts every empty slot.</p>
      <p className="mt-2 text-sm text-muted">
        It reads the brand files, the calendar and the swipe file — {dayMonth(today)} has none of them to work from yet.
      </p>
      <div className="mt-4 flex flex-wrap gap-2">
        <Link to="/context/brand" className={buttonVariants({ variant: 'outline', size: 'sm' })} data-testid="today-brand-link">
          Brand files
        </Link>
        <Link to="/calendar" className={buttonVariants({ variant: 'outline', size: 'sm' })} data-testid="today-calendar-link">
          Calendar
        </Link>
        <Link to="/competitors/swipe" className={buttonVariants({ variant: 'outline', size: 'sm' })} data-testid="today-competitors-link">
          Competitors
        </Link>
      </div>
    </Card>
  )
}

const quiet = (data: TodayResponse) =>
  data.open.length === 0 &&
  data.week.length === 0 &&
  data.noticed.length === 0 &&
  data.building.length === 0 &&
  data.built_today.length === 0 &&
  data.skill_proposals.length === 0

export function Today() {
  const query = useQuery({ queryKey: ['today'], queryFn: getToday })
  const data = query.data

  return (
    <div className="space-y-4" data-testid="today-view" data-state={query.isPending ? 'loading' : query.error ? 'error' : 'ready'}>
      {query.error && <ErrorBanner error={asApiError(query.error)} testId="today-error" />}
      {!data && !query.error && <Loading />}
      {data && (
        <>
          <p className="flex flex-wrap items-baseline gap-x-2 text-sm text-muted" data-testid="today-line">
            <span className="font-medium text-ink">{dayMonth(data.today)}</span>
            {data.last_run ? (
              <>
                <span>·</span>
                <span>
                  {data.last_run.agent} ran {hhmm(data.last_run.created_at)}
                </span>
                <span>·</span>
                <span className="min-w-0">read {data.last_run.read_detail}</span>
              </>
            ) : (
              <>
                <span>·</span>
                <span>no agent run yet</span>
              </>
            )}
          </p>
          {quiet(data) ? (
            <Nothing today={data.today} />
          ) : (
            <div className="grid gap-4 lg:grid-cols-2">
              <Panel title="Needs you" count={data.open.length} testId="today-needs-you">
                {data.open.length === 0 ? (
                  <Empty testId="today-needs-you-empty">nothing open</Empty>
                ) : (
                  data.open.map((row) => <OpenProposal key={row.seq} row={row} />)
                )}
                <div className="pt-2">
                  <Link to="/proposals" className={buttonVariants({ variant: 'outline', size: 'sm' })} data-testid="today-open-queue">
                    Open queue
                  </Link>
                </div>
              </Panel>

              <Panel title="This week" testId="today-this-week">
                {data.week.length === 0 ? (
                  <Empty testId="today-week-empty">no slots this week</Empty>
                ) : (
                  data.week.map((slot) => <WeekSlot key={`${slot.date}|${slot.name}`} slot={slot} />)
                )}
              </Panel>

              <Panel title="Noticed" count={data.noticed.length} testId="today-noticed">
                {data.noticed.length === 0 ? (
                  <Empty testId="today-noticed-empty">nothing noticed</Empty>
                ) : (
                  data.noticed.map((item) => (
                    <p key={item.text} className={ROW} data-testid="today-noticed-item">
                      <span className="text-muted">●</span>
                      <span className="min-w-0 flex-1 text-ink">{item.text}</span>
                      {item.proposal_seq === null ? (
                        <span className="text-muted">no action</span>
                      ) : (
                        <Link to={`/proposals/${item.proposal_seq}`} className="text-ink underline" data-testid="today-noticed-link">
                          → #{item.proposal_seq}
                        </Link>
                      )}
                    </p>
                  ))
                )}
              </Panel>

              <Panel title="Building" count={data.building.length} testId="today-building">
                {data.building.length === 0 ? (
                  <Empty testId="today-building-empty">nothing building</Empty>
                ) : (
                  data.building.map((run) => <Building key={run.seq} run={run} />)
                )}
              </Panel>

              <Panel title="Built today" count={data.built_today.length} testId="today-built">
                {data.built_today.length === 0 ? (
                  <Empty testId="today-built-empty">nothing built today</Empty>
                ) : (
                  data.built_today.map((asset) => (
                    <Link
                      key={asset.seq}
                      to={`/assets/${asset.seq}`}
                      className={cn(ROW, 'hover:bg-wash')}
                      data-testid="today-built-item"
                      data-seq={asset.seq}
                    >
                      <span className="w-5 shrink-0 text-center text-muted">{kindGlyph(asset.kind)}</span>
                      <span className="min-w-0 flex-1 truncate text-ink">{asset.name}</span>
                      <span className="text-muted">{asset.kind}</span>
                    </Link>
                  ))
                )}
              </Panel>

              <Panel title="Skill proposals" count={data.skill_proposals.length} testId="today-skill-proposals">
                {data.skill_proposals.length === 0 ? (
                  <Empty testId="today-skill-proposals-empty">the taste agent proposed nothing</Empty>
                ) : (
                  data.skill_proposals.map((lesson) => (
                    <div key={`${lesson.skill}|${lesson.line}`} className={ROW} data-testid="today-skill-proposal">
                      <span className="text-muted">✎</span>
                      <Mono className="text-muted">{lesson.skill}</Mono>
                      <span className="min-w-0 flex-1 text-ink">“{lesson.line}”</span>
                      <span className="text-muted">{lesson.proposal_refs.map((ref) => `#${ref}`).join(' ')}</span>
                      <a
                        href={lesson.url}
                        target="_blank"
                        rel="noreferrer"
                        className={buttonVariants({ variant: 'ghost', size: 'sm', className: 'h-7 px-2 text-muted' })}
                        data-testid="today-skill-diff"
                      >
                        Review diff <ExternalLink size={12} />
                      </a>
                    </div>
                  ))
                )}
              </Panel>
            </div>
          )}
        </>
      )}
    </div>
  )
}
