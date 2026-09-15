import { useQuery, type UseQueryResult } from '@tanstack/react-query'
import { asApiError, getStudioSources, type StudioSourcesResponse } from '@/api'
import { ErrorBanner } from '@/components/ui/banner'
import { Card } from '@/components/ui/card'
import { Empty } from '@/components/ui/empty'
import { Loading } from '@/components/ui/loading'
import { Mono } from '@/components/ui/mono'
import { Pill } from '@/components/ui/pill'
import { stamp } from '@/components/context/stamp'
import { num } from '@/lib/format'
import { cn } from '@/lib/utils'

const HEADING = 'text-xs font-medium uppercase tracking-wide text-muted'
const HEAD = 'whitespace-nowrap pb-2 pr-4 text-left font-medium text-muted last:pr-0'
const CELL = 'py-2 pr-4 align-middle last:pr-0'

function SourcesBody({ query }: { query: UseQueryResult<StudioSourcesResponse> }) {
  if (query.error) return <ErrorBanner error={asApiError(query.error)} />
  if (!query.data) return <Loading />
  const rows = query.data.competitor_sources
  if (rows.length === 0) return <Empty>no connectors configured</Empty>
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead className="text-left text-muted">
          <tr className="border-b border-line">
            <th className={HEAD}>Source</th>
            <th className={HEAD}>Status</th>
            <th className={HEAD}>Last sync</th>
            <th className={cn(HEAD, 'text-right')}>Rows</th>
            <th className={HEAD}>Detail</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={row.source} className="border-b border-line/30 last:border-0" data-testid="source-row" data-source={row.source}>
              <td className={CELL}>
                <Mono className="block text-ink">{row.source}</Mono>
                <span className="block text-xs text-muted">{row.label}</span>
              </td>
              <td className={cn(CELL, 'whitespace-nowrap')}>
                <Pill tone={row.ok ? 'ok' : 'down'}>{row.ok ? '✓' : '✗'}</Pill>
              </td>
              <td className={cn(CELL, 'whitespace-nowrap text-muted')}>
                {row.last_sync === null ? '—' : stamp(row.last_sync)}
              </td>
              <td className={cn(CELL, 'whitespace-nowrap text-right tabular-nums text-ink')}>{num(row.rows)}</td>
              <td className={CELL}>
                <span className="block text-muted">{row.detail}</span>
                {row.error !== null && <span className="block text-err">{row.error}</span>}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

export function SourcesPanel() {
  const query = useQuery({ queryKey: ['studio-sources'], queryFn: getStudioSources })
  const data = query.data
  return (
    <Card
      className="space-y-3 p-4 sm:p-5"
      data-testid="sources-panel"
      data-state={query.isPending ? 'loading' : query.error ? 'error' : 'ready'}
    >
      <div className="flex flex-wrap items-baseline justify-between gap-2 border-b border-line pb-2">
        <h2 className={HEADING}>Sources (competitor)</h2>
        <span className="text-xs text-muted">
          {data ? `${num(data.competitor_sources.length)} connectors · ` : ''}stand-ins in this repo
        </span>
      </div>
      <SourcesBody query={query} />
      <p className="border-t border-line/50 pt-2 text-xs text-muted" data-testid="sources-console-note">
        estate sources: {data ? num(data.estate_sources) : '—'} → Console
      </p>
    </Card>
  )
}
