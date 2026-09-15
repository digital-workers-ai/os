import { useState } from 'react'
import { useQuery, type UseQueryResult } from '@tanstack/react-query'
import { asApiError, getRankings, type RankingsResponse } from '@/api'
import { Sparkline } from '@/components/competitors/Sparkline'
import { ErrorBanner } from '@/components/ui/banner'
import { Card } from '@/components/ui/card'
import { Empty } from '@/components/ui/empty'
import { Input } from '@/components/ui/input'
import { Loading } from '@/components/ui/loading'
import { num } from '@/lib/format'
import { cn } from '@/lib/utils'

const HEAD = 'whitespace-nowrap pb-2 pr-4 text-left font-medium text-muted last:pr-0'
const CELL = 'py-2 pr-4 align-middle last:pr-0'
const LABEL = 'text-xs font-medium uppercase tracking-wide text-muted'

const best = (positions: Record<string, number | null>) => {
  const ranked = Object.values(positions).filter((position): position is number => position !== null)
  return ranked.length === 0 ? null : Math.min(...ranked)
}

function SearchBody({ query }: { query: UseQueryResult<RankingsResponse> }) {
  if (query.error) return <ErrorBanner error={asApiError(query.error)} />
  if (!query.data) return <Loading />
  const data = query.data
  if (data.keywords.length === 0) return <Empty>no keywords tracked</Empty>
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm" data-testid="search-table">
        <thead className="text-left text-muted">
          <tr className="border-b border-line">
            <th className={HEAD}>keyword</th>
            {data.domains.map((domain) => (
              <th key={domain} className={cn(HEAD, 'text-right')} data-domain={domain}>
                {domain}
              </th>
            ))}
            <th className={cn(HEAD, 'text-right')}>12w</th>
          </tr>
        </thead>
        <tbody>
          {data.keywords.map((row) => {
            const leader = best(row.positions)
            return (
              <tr key={row.keyword} className="border-b border-line/30 last:border-0" data-testid="search-row">
                <td className={cn(CELL, 'font-medium text-ink')}>{row.keyword}</td>
                {data.domains.map((domain) => {
                  const position = row.positions[domain] ?? null
                  return (
                    <td
                      key={domain}
                      className={cn(
                        CELL,
                        'whitespace-nowrap text-right tabular-nums',
                        position !== null && position === leader ? 'font-medium text-ink' : 'text-muted',
                      )}
                      data-domain={domain}
                    >
                      {position === null ? '—' : `#${num(position)}`}
                    </td>
                  )
                })}
                <td className={cn(CELL, 'text-right')}>
                  <Sparkline points={row.history.map((entry) => entry.position)} invert testId="search-spark" />
                </td>
              </tr>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}

export function SearchPanel() {
  const [keyword, setKeyword] = useState('')
  const query = useQuery({
    queryKey: ['rankings', keyword],
    queryFn: () => getRankings(keyword || undefined),
  })
  const data = query.data
  return (
    <Card
      className="space-y-3 p-4 sm:p-5"
      data-testid="search-panel"
      data-state={query.isPending ? 'loading' : query.error ? 'error' : 'ready'}
    >
      <div className="flex flex-wrap items-center justify-between gap-2 border-b border-line pb-2">
        <div className="flex flex-wrap items-baseline gap-2">
          <h2 className={LABEL}>Search</h2>
          {data && (
            <span className="text-xs text-muted">
              {num(data.keywords.length)} keywords · {data.location} · {data.engine}
            </span>
          )}
        </div>
        <Input
          aria-label="keyword"
          placeholder="keyword…"
          className="h-8 w-full text-xs sm:w-56"
          value={keyword}
          onChange={(event) => setKeyword(event.target.value)}
          data-testid="search-filter-keyword"
        />
      </div>
      <SearchBody query={query} />
      <p className="border-t border-line/50 pt-2 text-xs text-muted" data-testid="search-footer">
        positions are plain queries over dated entities · keywords live in definitions/competitors.yaml
      </p>
    </Card>
  )
}
