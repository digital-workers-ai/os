import { useState } from 'react'
import { useQuery, type UseQueryResult } from '@tanstack/react-query'
import { asApiError, getAssets, type AssetsResponse } from '@/api'
import { AssetCard } from '@/components/assets/AssetCard'
import { Filters, NO_FILTERS, type AssetFilters } from '@/components/assets/Filters'
import { ErrorBanner } from '@/components/ui/banner'
import { Empty } from '@/components/ui/empty'
import { Loading } from '@/components/ui/loading'
import { num } from '@/lib/format'

function Library({ query }: { query: UseQueryResult<AssetsResponse> }) {
  if (query.error) return <ErrorBanner error={asApiError(query.error)} />
  if (!query.data) return <Loading />
  const { assets, total } = query.data
  if (assets.length === 0) return <Empty>no asset matches these filters</Empty>
  return (
    <>
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4 xl:grid-cols-5">
        {assets.map((row) => (
          <AssetCard key={row.seq} row={row} />
        ))}
      </div>
      <p className="mt-4 border-t border-line pt-2 text-xs text-muted" data-testid="assets-footer">
        {num(total)} assets · every one has a skill run; proposals have a slot too
      </p>
    </>
  )
}

export function Assets() {
  const [filters, setFilters] = useState<AssetFilters>(NO_FILTERS)
  const query = useQuery({
    queryKey: ['assets', filters],
    queryFn: () =>
      getAssets(filters.kind || undefined, filters.look || undefined, filters.origin || undefined, filters.q || undefined),
  })

  return (
    <div
      className="space-y-4"
      data-testid="assets-view"
      data-state={query.isPending ? 'loading' : query.error ? 'error' : 'ready'}
    >
      <Filters filters={filters} onChange={setFilters} />
      <Library query={query} />
    </div>
  )
}
