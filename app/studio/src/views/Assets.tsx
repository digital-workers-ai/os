import { useState } from 'react'
import { keepPreviousData, useQuery } from '@tanstack/react-query'
import { asApiError, getAssets, getLooks, type AssetFilters } from '@/api'
import { AssetCard } from '@/components/assets/Card'
import { Filters } from '@/components/assets/Filters'
import { ErrorBanner } from '@/components/ui/banner'
import { Empty } from '@/components/ui/empty'
import { Loading } from '@/components/ui/loading'
import { num } from '@/lib/format'

export function Assets() {
  const [filters, setFilters] = useState<AssetFilters>({})
  const looks = useQuery({ queryKey: ['looks'], queryFn: getLooks })
  const assets = useQuery({ queryKey: ['assets', filters], queryFn: () => getAssets(filters), placeholderData: keepPreviousData })
  const state = assets.isPending ? 'loading' : assets.error ? 'error' : 'ready'

  return (
    <div className="flex flex-col gap-4" data-testid="assets-view" data-state={state}>
      <Filters value={filters} looks={looks.data?.looks ?? []} onChange={setFilters} />
      {assets.error ? (
        <ErrorBanner error={asApiError(assets.error)} />
      ) : !assets.data ? (
        <Loading />
      ) : assets.data.assets.length === 0 ? (
        <Empty testId="assets-empty">no assets match</Empty>
      ) : (
        <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5" data-testid="assets-grid">
          {assets.data.assets.map((asset) => (
            <AssetCard key={asset.seq} asset={asset} />
          ))}
        </div>
      )}
      {assets.data && (
        <p className="text-xs text-muted" data-testid="assets-total">
          {num(assets.data.total)} assets
        </p>
      )}
    </div>
  )
}
