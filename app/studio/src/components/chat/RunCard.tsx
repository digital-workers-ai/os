import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { getAsset, getSkillRun, type SkillRunRow, type ToolCall } from '@/api'
import { KindGlyph, OriginPill, StatusPill } from '@/components/assets/Card'
import { Mono } from '@/components/ui/mono'

export const useSkillRun = (run: SkillRunRow | null) =>
  useQuery({
    queryKey: ['skill-run', run?.seq],
    queryFn: () => getSkillRun(run!.seq),
    enabled: run?.status === 'running',
    refetchInterval: (query) => (query.state.data?.status === 'running' ? 2000 : false),
  })

function ToolTally({ calls }: { calls: ToolCall[] }) {
  const tally = new Map<string, { count: number; failed: boolean }>()
  for (const call of calls) {
    const entry = tally.get(call.tool) ?? { count: 0, failed: false }
    entry.count += 1
    entry.failed ||= !call.ok
    tally.set(call.tool, entry)
  }
  if (tally.size === 0) return null
  return (
    <p className="text-xs text-muted" data-testid="run-tools">
      {[...tally].map(([tool, { count, failed }], i) => (
        <span key={tool} data-testid="run-tool" data-failed={failed || undefined}>
          {i > 0 && ' · '}
          {tool} ×{count}
          {failed && ' ✗'}
        </span>
      ))}
    </p>
  )
}

export function RunProgress({ run, calls }: { run: SkillRunRow; calls: ToolCall[] }) {
  return (
    <div className="flex flex-col gap-1" data-testid="run-progress" data-status={run.status}>
      <div className="flex flex-wrap items-center gap-2 text-xs">
        <Mono>{run.skill}</Mono>
        <StatusPill status={run.status} />
        {run.status === 'running' && run.stage && (
          <span className="text-muted" data-testid="run-stage">
            {run.stage}…
          </span>
        )}
      </div>
      <ToolTally calls={calls} />
      {run.status === 'failed' && run.error && (
        <p className="text-xs text-err" data-testid="run-error">
          {run.error}
        </p>
      )}
    </div>
  )
}

export function RunCard({ run }: { run: SkillRunRow }) {
  const live = useSkillRun(run)
  const current = live.data ?? run
  const done = current.status !== 'running'
  const seq = current.asset_seq
  const asset = useQuery({ queryKey: ['asset', seq], queryFn: () => getAsset(seq!), enabled: done && seq !== null })
  const version = current.version ?? asset.data?.version
  const claims = asset.data?.claims.filter((claim) => claim.version === version) ?? []
  const verified = claims.filter((claim) => claim.verified).length
  const holding = claims.filter((claim) => !claim.verified).map((claim) => claim.text)
  return (
    <div className="mt-2 flex flex-col gap-2 rounded-lg border border-line bg-surface p-3" data-testid="run-card" data-status={current.status}>
      <RunProgress run={current} calls={live.data?.tool_calls ?? []} />
      {current.status === 'held' && (
        <p className="text-xs text-down" data-testid="run-held">
          {holding.length > 0 ? `held by: ${holding.join(' · ')}` : (current.error ?? 'held: something it needed was missing')}
        </p>
      )}
      {asset.data && (
        <Link
          to={`/assets/${asset.data.seq}`}
          className="flex items-center gap-3 rounded-lg border border-line bg-paper p-2 transition-colors hover:border-muted"
          data-testid="run-asset"
        >
          <div className="flex h-14 w-14 shrink-0 items-center justify-center overflow-hidden rounded-md bg-wash">
            {asset.data.preview ? (
              <img src={asset.data.preview} alt={asset.data.name} className="h-full w-full object-cover" />
            ) : (
              <KindGlyph kind={asset.data.kind} size={22} />
            )}
          </div>
          <div className="flex min-w-0 flex-col gap-1">
            <span className="truncate text-sm font-medium text-ink">{asset.data.name}</span>
            <span className="flex flex-wrap items-center gap-1.5 text-xs text-muted">
              {asset.data.kind}
              <OriginPill origin={asset.data.origin} />
              <span data-testid="run-claims">
                {verified}/{claims.length} claims verified
              </span>
            </span>
          </div>
        </Link>
      )}
    </div>
  )
}
