import { useState } from 'react'
import { useQuery, type UseQueryResult } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { asApiError, getAgentRuns, getSkillRuns, type AgentRunRow, type Mode, type SkillRunRow } from '@/api'
import { ErrorBanner } from '@/components/ui/banner'
import { Card } from '@/components/ui/card'
import { Empty } from '@/components/ui/empty'
import { Loading } from '@/components/ui/loading'
import { Mono } from '@/components/ui/mono'
import { Pill } from '@/components/ui/pill'
import { fixed, num, shortDate } from '@/lib/format'
import { cn } from '@/lib/utils'

const TABS: [string, string][] = [
  ['agents', 'Agents'],
  ['skill-runs', 'Skill runs'],
]
const MODES: Mode[] = ['draft', 'build', 'chat']
const LIMIT = 50
const LABEL = 'text-xs font-medium uppercase tracking-wide text-muted'
const SELECT = 'h-8 rounded-md border border-line bg-paper px-2 text-xs text-ink'
const HEAD = 'whitespace-nowrap pb-2 pr-4 text-left font-medium text-muted last:pr-0'
const CELL = 'py-2 pr-4 align-middle last:pr-0'

const pad = (n: number) => String(n).padStart(2, '0')

const duration = (ms: number) => {
  const seconds = Math.max(0, Math.round(ms / 1000))
  return seconds < 60 ? `${seconds}s` : `${Math.floor(seconds / 60)}m ${pad(seconds % 60)}s`
}

const stamp = (at: string) => {
  const [day, time] = at.split(/[T ]/)
  return time ? `${shortDate(day)} ${time.slice(0, 5)}` : shortDate(day)
}

const detailLink = (run: SkillRunRow) => {
  if (run.proposal_seq !== null) return `/proposals/${run.proposal_seq}`
  if (run.asset_seq !== null) return `/assets/${run.asset_seq}`
  return null
}

const choices = (values: string[], chosen: string) => [...new Set([...values, chosen])].filter((value) => value !== '').sort()

function AgentRunsBody({ query }: { query: UseQueryResult<{ runs: AgentRunRow[] }> }) {
  if (query.error) return <ErrorBanner error={asApiError(query.error)} />
  if (!query.data) return <Loading />
  const runs = query.data.runs
  if (runs.length === 0) return <Empty>no agent runs yet</Empty>
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead className="text-left text-muted">
          <tr className="border-b border-line">
            <th className={HEAD}>Time</th>
            <th className={HEAD}>Agent</th>
            <th className={HEAD}>Trigger</th>
            <th className={HEAD}>Read</th>
            <th className={HEAD}>Did</th>
            <th className={HEAD}>Took</th>
            <th className={cn(HEAD, 'text-right')}>Cost</th>
          </tr>
        </thead>
        <tbody>
          {runs.map((run) => (
            <tr key={run.seq} className="border-b border-line/30 last:border-0" data-testid="agent-run-row" data-seq={run.seq}>
              <td className={cn(CELL, 'whitespace-nowrap text-muted')}>{stamp(run.created_at)}</td>
              <td className={cn(CELL, 'whitespace-nowrap')}>
                <Pill>{run.agent}</Pill>
              </td>
              <td className={cn(CELL, 'whitespace-nowrap text-muted')}>{run.trigger}</td>
              <td className={cn(CELL, 'text-muted')}>{run.read_detail}</td>
              <td className={CELL}>
                <span className="block text-ink">proposed {num(run.proposed)}</span>
                {!run.ok && run.error !== null && <span className="block text-err">{run.error}</span>}
              </td>
              <td className={cn(CELL, 'whitespace-nowrap tabular-nums text-muted')}>{duration(run.duration_ms)}</td>
              <td className={cn(CELL, 'whitespace-nowrap text-right tabular-nums text-ink')}>${fixed(run.cost_usd)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

function SkillRunsBody({ query }: { query: UseQueryResult<{ runs: SkillRunRow[] }> }) {
  if (query.error) return <ErrorBanner error={asApiError(query.error)} />
  if (!query.data) return <Loading />
  const runs = query.data.runs
  if (runs.length === 0) return <Empty>no skill runs yet</Empty>
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead className="text-left text-muted">
          <tr className="border-b border-line">
            <th className={HEAD}>Time</th>
            <th className={HEAD}>Run</th>
            <th className={HEAD}>Skill</th>
            <th className={HEAD}>Mode</th>
            <th className={HEAD}>Caller</th>
            <th className={HEAD}>Progress</th>
            <th className={cn(HEAD, 'text-right')}>Cost</th>
          </tr>
        </thead>
        <tbody>
          {runs.map((run) => {
            const to = detailLink(run)
            return (
              <tr key={run.seq} className="border-b border-line/30 last:border-0" data-testid="skill-run-row" data-seq={run.seq}>
                <td className={cn(CELL, 'whitespace-nowrap text-muted')}>{stamp(run.started_at)}</td>
                <td className={cn(CELL, 'whitespace-nowrap')}>
                  {to === null ? (
                    <Mono className="text-muted">#{run.seq}</Mono>
                  ) : (
                    <Link to={to} className="hover:underline">
                      <Mono className="text-ink">#{run.seq}</Mono>
                    </Link>
                  )}
                </td>
                <td className={cn(CELL, 'whitespace-nowrap')}>
                  <Mono className="text-ink">{run.skill}</Mono>
                </td>
                <td className={cn(CELL, 'whitespace-nowrap')}>
                  <Pill>{run.mode}</Pill>
                </td>
                <td className={cn(CELL, 'whitespace-nowrap text-muted')}>{run.caller}</td>
                <td className={CELL}>
                  {run.status === 'running' ? (
                    <Pill tone="unknown">◔ {run.stage ?? 'running'}</Pill>
                  ) : (
                    <>
                      <Pill tone={run.status === 'ok' ? 'ok' : 'down'}>{run.status}</Pill>
                      {run.status === 'failed' && run.error !== null && <span className="mt-0.5 block text-err">{run.error}</span>}
                    </>
                  )}
                </td>
                <td className={cn(CELL, 'whitespace-nowrap text-right tabular-nums text-ink')}>${fixed(run.cost_usd)}</td>
              </tr>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}

function AgentRuns() {
  const query = useQuery({ queryKey: ['agent-runs', LIMIT], queryFn: () => getAgentRuns(LIMIT) })
  return (
    <div className="space-y-3" data-state={query.isPending ? 'loading' : query.error ? 'error' : 'ready'}>
      <div className="border-b border-line pb-2">
        <h2 className={LABEL}>Agents</h2>
      </div>
      <AgentRunsBody query={query} />
    </div>
  )
}

function SkillRuns() {
  const [skill, setSkill] = useState('')
  const [mode, setMode] = useState('')
  const query = useQuery({
    queryKey: ['skill-runs', LIMIT, skill, mode],
    queryFn: () => getSkillRuns(LIMIT, skill || undefined, mode || undefined),
  })
  const skills = choices(
    (query.data?.runs ?? []).map((run) => run.skill),
    skill,
  )
  return (
    <div className="space-y-3" data-state={query.isPending ? 'loading' : query.error ? 'error' : 'ready'}>
      <div className="flex flex-wrap items-center justify-between gap-2 border-b border-line pb-2">
        <h2 className={LABEL}>Skill runs</h2>
        <div className="flex flex-wrap items-center gap-2">
          <select
            aria-label="skill"
            className={SELECT}
            value={skill}
            onChange={(event) => setSkill(event.target.value)}
            data-testid="runs-filter-skill"
          >
            <option value="">all skills</option>
            {skills.map((name) => (
              <option key={name} value={name}>
                {name}
              </option>
            ))}
          </select>
          <select
            aria-label="mode"
            className={SELECT}
            value={mode}
            onChange={(event) => setMode(event.target.value)}
            data-testid="runs-filter-mode"
          >
            <option value="">all modes</option>
            {MODES.map((name) => (
              <option key={name} value={name}>
                {name}
              </option>
            ))}
          </select>
        </div>
      </div>
      <SkillRunsBody query={query} />
    </div>
  )
}

export function Activity() {
  const [tab, setTab] = useState('agents')
  return (
    <div className="space-y-4" data-testid="activity-view" data-tab={tab}>
      <div className="flex flex-wrap items-center gap-1 border-b border-line pb-2">
        {TABS.map(([slug, label]) => (
          <button
            key={slug}
            type="button"
            aria-pressed={tab === slug}
            onClick={() => setTab(slug)}
            className={cn(
              'rounded-md px-2.5 py-1 text-xs transition-colors',
              tab === slug ? 'bg-wash font-medium text-ink' : 'text-muted hover:text-ink',
            )}
            data-testid={`activity-tab-${slug}`}
          >
            {label}
          </button>
        ))}
      </div>
      <Card className="space-y-3 p-4 sm:p-5">
        {tab === 'agents' ? <AgentRuns /> : <SkillRuns />}
        <p className="border-t border-line/50 pt-2 text-xs text-muted" data-testid="activity-footer">
          agents: marketer (06:00) · taste (02:00) · runner: sandboxed, fixed toolbelt
        </p>
      </Card>
    </div>
  )
}
