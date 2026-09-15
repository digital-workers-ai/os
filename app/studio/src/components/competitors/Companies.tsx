import { useQuery, type UseQueryResult } from '@tanstack/react-query'
import { asApiError, getCompetitors, type CompetitorRow, type CompetitorsResponse } from '@/api'
import { ErrorBanner } from '@/components/ui/banner'
import { Card } from '@/components/ui/card'
import { Empty } from '@/components/ui/empty'
import { Loading } from '@/components/ui/loading'
import { Mono } from '@/components/ui/mono'
import { Pill, type Tone } from '@/components/ui/pill'
import { num, shortDate } from '@/lib/format'

const LABEL = 'text-xs font-medium uppercase tracking-wide text-muted'
const ROW = 'flex flex-wrap items-baseline gap-x-3 gap-y-1 py-2 text-sm'

type Source = CompetitorRow['sources'][number]

const mark = (source: Source): { glyph: string; tone: Tone } => {
  if (source.last_sync === null) return { glyph: '—', tone: 'unknown' }
  return source.ok ? { glyph: '✓', tone: 'ok' } : { glyph: '✗', tone: 'down' }
}

const lastSync = (sources: Source[]) =>
  sources
    .map((source) => source.last_sync)
    .filter((stamp): stamp is string => stamp !== null)
    .sort()
    .at(-1) ?? null

const clock = (stamp: string) => stamp.slice(11, 16)

const synced = (stamp: string | null) => {
  if (stamp === null) return 'never synced'
  const day = shortDate(stamp.slice(0, 10))
  return stamp.includes('T') ? `synced ${day} ${clock(stamp)}` : `synced ${day}`
}

function CompaniesBody({ query }: { query: UseQueryResult<CompetitorsResponse> }) {
  if (query.error) return <ErrorBanner error={asApiError(query.error)} />
  if (!query.data) return <Loading />
  const data = query.data
  if (data.competitors.length === 0) return <Empty>no competitors tracked</Empty>
  return (
    <ul className="divide-y divide-line/30">
      {data.competitors.map((competitor) => (
        <li key={competitor.slug} className={ROW} data-testid="company-row" data-slug={competitor.slug}>
          <span className="font-medium text-ink">{competitor.name}</span>
          <Mono className="text-muted">{competitor.domain}</Mono>
          <span className="flex min-w-0 flex-wrap gap-1">
            {competitor.sources.map((source) => {
              const state = mark(source)
              return (
                <Pill key={source.source} tone={state.tone} title={`${num(source.rows)} rows`} data-testid="company-source">
                  {source.source} {state.glyph}
                </Pill>
              )
            })}
          </span>
          <span className="ml-auto whitespace-nowrap text-muted">{synced(lastSync(competitor.sources))}</span>
        </li>
      ))}
      <li className={ROW} data-testid="us-row">
        <Pill>us</Pill>
        <span className="font-medium text-ink">{data.us.name}</span>
        <Mono className="text-muted">{data.us.domain}</Mono>
        <span className="ml-auto whitespace-nowrap text-muted">ours</span>
      </li>
    </ul>
  )
}

export function CompaniesPanel() {
  const query = useQuery({ queryKey: ['competitors'], queryFn: getCompetitors })
  const data = query.data
  return (
    <Card
      className="space-y-3 p-4 sm:p-5"
      data-testid="companies-panel"
      data-state={query.isPending ? 'loading' : query.error ? 'error' : 'ready'}
    >
      <div className="flex flex-wrap items-baseline gap-2 border-b border-line pb-2">
        <h2 className={LABEL}>Companies</h2>
        {data && (
          <span className="text-xs text-muted">
            {num(data.competitors.length)} tracked · definitions/competitors.yaml
          </span>
        )}
      </div>
      <CompaniesBody query={query} />
      <p className="border-t border-line/50 pt-2 text-xs text-muted" data-testid="companies-footer">
        sync status comes from the competitor connectors · add a domain in definitions/competitors.yaml
      </p>
    </Card>
  )
}
