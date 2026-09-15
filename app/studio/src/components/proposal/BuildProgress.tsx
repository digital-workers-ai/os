import type { Proposal, SkillRun } from '@/api'
import { Card } from '@/components/ui/card'
import { Empty } from '@/components/ui/empty'
import { Mono } from '@/components/ui/mono'
import { hhmm, kindGlyph, since } from '@/lib/calendar'
import { fixed } from '@/lib/format'
import { cn } from '@/lib/utils'

type StageState = SkillRun['stages'][number]['state']

const MARKS: Record<StageState, string> = { done: '✓', running: '◔', waiting: '○' }

const TONES: Record<StageState, string> = { done: 'text-ok', running: 'text-ink', waiting: 'text-muted' }

const counted = (run: SkillRun) => {
  const tally = new Map<string, { calls: number; failed: number }>()
  for (const call of run.tool_calls) {
    const seen = tally.get(call.tool) ?? { calls: 0, failed: 0 }
    tally.set(call.tool, { calls: seen.calls + 1, failed: seen.failed + (call.ok ? 0 : 1) })
  }
  return [...tally].map(([tool, seen]) => ({ tool, ...seen }))
}

export function BuildProgress({ proposal, run }: { proposal: Proposal; run: SkillRun }) {
  const tools = counted(run)
  return (
    <Card className="space-y-4" data-testid="build-progress" data-status={run.status} data-run={run.seq}>
      <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1 border-b border-line pb-3">
        <Mono className="text-muted">#{proposal.seq}</Mono>
        <span className="text-muted">
          {kindGlyph(proposal.kind)} {proposal.kind}
        </span>
        <span className="min-w-0 flex-1 truncate font-medium text-ink">{proposal.title}</span>
        <span className="whitespace-nowrap text-sm text-ink">building</span>
        <span className="whitespace-nowrap text-sm text-muted">
          started {hhmm(run.started_at)} · {since(run.started_at)}
        </span>
      </div>

      <p className="flex flex-wrap gap-x-2 text-sm text-muted" data-testid="build-head">
        <span>
          skill <Mono className="text-ink">{run.skill}</Mono>
        </span>
        <span>· mode {run.mode}</span>
        {proposal.look && <span>· look {proposal.look}</span>}
        <span>
          · sha <Mono>{run.skill_sha.slice(0, 7)}</Mono>
        </span>
      </p>

      {run.stages.length === 0 ? (
        <Empty testId="build-stages-empty">no stage reported yet</Empty>
      ) : (
        <ul className="divide-y divide-line/30" data-testid="build-stages">
          {run.stages.map((stage) => (
            <li key={stage.name} className="flex flex-wrap items-baseline gap-x-3 py-1.5 text-sm" data-testid="build-stage" data-stage={stage.name} data-state={stage.state}>
              <span className={cn('w-4 shrink-0', TONES[stage.state])}>{MARKS[stage.state]}</span>
              <span className="w-24 shrink-0 font-medium text-ink">{stage.name}</span>
              <span className="min-w-0 flex-1 text-muted">{stage.detail ?? ''}</span>
            </li>
          ))}
        </ul>
      )}

      <p className="flex flex-wrap items-baseline gap-x-2 text-xs text-muted" data-testid="build-tools">
        <span>tools called:</span>
        {tools.length === 0 ? (
          <span>none yet</span>
        ) : (
          tools.map((entry) => (
            <span key={entry.tool} className={cn(entry.failed > 0 && 'text-down')} data-tool={entry.tool}>
              <Mono>{entry.tool}</Mono>
              {entry.calls > 1 ? ` ×${entry.calls}` : ''}
              {entry.failed > 0 ? ' ✗' : ''}
            </span>
          ))
        )}
      </p>

      <p className="text-xs text-muted" data-testid="build-cost">
        cost so far ${fixed(run.cost_usd)} · every file kept under the media store
      </p>
    </Card>
  )
}
