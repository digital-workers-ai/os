import { useState } from 'react'
import { useQuery, type UseQueryResult } from '@tanstack/react-query'
import { asApiError, getAds, type AdsResponse } from '@/api'
import { Sparkline } from '@/components/competitors/Sparkline'
import { ErrorBanner } from '@/components/ui/banner'
import { Card } from '@/components/ui/card'
import { Empty } from '@/components/ui/empty'
import { Loading } from '@/components/ui/loading'
import { Pill } from '@/components/ui/pill'
import { num, pct, shortDate } from '@/lib/format'

const SELECT = 'h-8 rounded-md border border-line bg-paper px-2 text-xs text-ink'
const LABEL = 'text-xs font-medium uppercase tracking-wide text-muted'

const byCountDesc = (a: [string, number], b: [string, number]) => b[1] - a[1] || a[0].localeCompare(b[0])

const choices = (values: string[], chosen: string) => [...new Set([...values, chosen])].filter((value) => value !== '').sort()

const platformSplit = (platforms: Record<string, number>) => {
  const parts = Object.entries(platforms).sort(byCountDesc)
  return parts.length === 0 ? '—' : parts.map(([platform, count]) => `${platform} ${num(count)}`).join(' · ')
}

const shareOf = (value: number, total: number) => (total > 0 && Math.abs(total - 1) > 0.01 ? value / total : value)

function Figure({ label, value }: { label: string; value: number }) {
  return (
    <span className="flex items-baseline gap-1">
      <span className="text-muted">{label}</span>
      <span className="font-medium tabular-nums text-ink">{num(value)}</span>
    </span>
  )
}

function AdsBody({ query }: { query: UseQueryResult<AdsResponse> }) {
  if (query.error) return <ErrorBanner error={asApiError(query.error)} />
  if (!query.data) return <Loading />
  const data = query.data
  if (data.by_competitor.length === 0) return <Empty>no ads tracked</Empty>
  const rows = [...data.by_competitor].sort((a, b) => b.active - a.active || a.competitor.localeCompare(b.competitor))
  const top = Math.max(0, ...rows.map((row) => row.active))
  const angles = Object.entries(data.angle_mix).sort(byCountDesc)
  const angleTotal = angles.reduce((sum, [, value]) => sum + value, 0)
  const weeks = data.new_per_week
  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-baseline gap-x-4 gap-y-1 text-sm" data-testid="ads-counts">
        <Figure label="active" value={data.active} />
        <Figure label="new 7d" value={data.new_7d} />
        <Figure label="90d+" value={data.long_running} />
      </div>
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
        <ul className="flex flex-col gap-2">
          {rows.map((row) => (
            <li key={row.competitor} data-testid="ads-competitor-row" data-competitor={row.competitor}>
              <div className="flex items-baseline justify-between gap-3 text-sm">
                <span className="min-w-0 truncate text-ink">{row.competitor}</span>
                <span className="shrink-0 tabular-nums text-ink">
                  {num(row.active)} <span className="text-muted">({num(row.long_running)} long-running)</span>
                </span>
              </div>
              <div className="mt-1 h-1.5 rounded-full bg-wash">
                <div className="h-full rounded-full bg-ink" style={{ width: `${top > 0 ? (row.active / top) * 100 : 0}%` }} />
              </div>
              <p className="mt-1 text-xs text-muted">{platformSplit(row.platforms)}</p>
            </li>
          ))}
        </ul>
        <div className="space-y-3">
          <div data-testid="ads-angle-mix">
            <p className={LABEL}>angle mix</p>
            {angles.length === 0 ? (
              <p className="mt-1 text-sm text-muted">—</p>
            ) : (
              <div className="mt-1 flex flex-wrap gap-1.5">
                {angles.map(([angle, value]) => (
                  <Pill key={angle}>
                    {angle} {pct(shareOf(value, angleTotal))}
                  </Pill>
                ))}
              </div>
            )}
          </div>
          <div data-testid="ads-week-spark">
            <p className={LABEL}>new per week</p>
            {weeks.length === 0 ? (
              <p className="mt-1 text-sm text-muted">—</p>
            ) : (
              <div className="mt-1 flex items-center gap-2">
                <span className="whitespace-nowrap text-xs text-muted">{shortDate(weeks[0].week.slice(0, 10))}</span>
                <Sparkline points={weeks.map((week) => week.count)} width={120} />
                <span className="whitespace-nowrap text-xs text-muted">{shortDate(weeks[weeks.length - 1].week.slice(0, 10))}</span>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}

export function AdsPanel() {
  const [competitor, setCompetitor] = useState('')
  const [platform, setPlatform] = useState('')
  const query = useQuery({
    queryKey: ['ads', competitor, platform],
    queryFn: () => getAds(competitor || undefined, platform || undefined),
  })
  const rows = query.data?.by_competitor ?? []
  const competitors = choices(
    rows.map((row) => row.competitor),
    competitor,
  )
  const platforms = choices(
    rows.flatMap((row) => Object.keys(row.platforms)),
    platform,
  )
  return (
    <Card
      className="space-y-3 p-4 sm:p-5"
      data-testid="ads-panel"
      data-state={query.isPending ? 'loading' : query.error ? 'error' : 'ready'}
    >
      <div className="flex flex-wrap items-center justify-between gap-2 border-b border-line pb-2">
        <h2 className={LABEL}>Ads</h2>
        <div className="flex flex-wrap items-center gap-2">
          <select
            aria-label="competitor"
            className={SELECT}
            value={competitor}
            onChange={(event) => setCompetitor(event.target.value)}
            data-testid="ads-filter-competitor"
          >
            <option value="">all competitors</option>
            {competitors.map((name) => (
              <option key={name} value={name}>
                {name}
              </option>
            ))}
          </select>
          <select
            aria-label="platform"
            className={SELECT}
            value={platform}
            onChange={(event) => setPlatform(event.target.value)}
            data-testid="ads-filter-platform"
          >
            <option value="">all platforms</option>
            {platforms.map((name) => (
              <option key={name} value={name}>
                {name}
              </option>
            ))}
          </select>
        </div>
      </div>
      <AdsBody query={query} />
      <p className="border-t border-line/50 pt-2 text-xs text-muted" data-testid="ads-footer">
        counts are plain queries over dated entities
      </p>
    </Card>
  )
}
