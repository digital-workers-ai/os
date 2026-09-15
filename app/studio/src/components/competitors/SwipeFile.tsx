import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { asApiError, getSwipe, type SwipeResponse } from '@/api'
import { SwipeCard } from '@/components/competitors/SwipeCard'
import { ErrorBanner } from '@/components/ui/banner'
import { Empty } from '@/components/ui/empty'
import { Loading } from '@/components/ui/loading'
import { Mono } from '@/components/ui/mono'
import { num } from '@/lib/format'

const FACETS = ['competitor', 'platform', 'angle', 'hook', 'format']

const SORTS: [string, string][] = [
  ['days_running', 'days running'],
  ['first_seen', 'newest'],
]

const SELECT = 'h-8 rounded-md border border-line bg-paper px-2 text-xs text-ink'

function Results({ error, data }: { error: unknown; data?: SwipeResponse }) {
  if (error) return <ErrorBanner error={asApiError(error)} testId="swipe-error" />
  if (!data) return <Loading />
  return (
    <>
      {data.items.length === 0 ? (
        <Empty testId="swipe-empty">nothing matches these filters</Empty>
      ) : (
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-5">
          {data.items.map((item) => (
            <SwipeCard key={item.id} item={item} />
          ))}
        </div>
      )}
      <p className="text-xs text-muted" data-testid="swipe-footer">
        {num(data.total)} items · labels from the <Mono>competitor_creative</Mono> reading in <Mono>enrichment.yaml</Mono>
      </p>
    </>
  )
}

export function SwipeFile() {
  const [filters, setFilters] = useState<Record<string, string>>({})
  const [sort, setSort] = useState('days_running')
  const query = useQuery({
    queryKey: ['swipe', filters, sort],
    queryFn: () => getSwipe({ ...filters, sort }),
  })
  const facets = query.data?.facets ?? {}

  return (
    <section className="space-y-3" data-testid="swipe-file">
      <div className="flex flex-wrap items-center gap-2">
        {FACETS.map((facet) => (
          <select
            key={facet}
            aria-label={facet}
            className={SELECT}
            value={filters[facet] ?? ''}
            onChange={(event) => setFilters({ ...filters, [facet]: event.target.value })}
            data-testid={`swipe-filter-${facet}`}
          >
            <option value="">{facet}</option>
            {(facets[facet] ?? []).map((value) => (
              <option key={value} value={value}>
                {value}
              </option>
            ))}
          </select>
        ))}
        <span className="text-xs text-muted">sort:</span>
        <select
          aria-label="sort"
          className={SELECT}
          value={sort}
          onChange={(event) => setSort(event.target.value)}
          data-testid="swipe-sort"
        >
          {SORTS.map(([value, label]) => (
            <option key={value} value={value}>
              {label}
            </option>
          ))}
        </select>
      </div>
      <Results error={query.error} data={query.data} />
    </section>
  )
}
