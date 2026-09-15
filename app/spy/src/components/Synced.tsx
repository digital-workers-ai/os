import type { UseQueryResult } from '@tanstack/react-query'
import type { ReactNode } from 'react'
import { asApiError, type Source } from '@/api'
import { ErrorBanner } from '@/components/ui/banner'
import { Empty } from '@/components/ui/empty'
import { Loading } from '@/components/ui/loading'

export function Synced<T extends { source: Source }>({
  slug,
  query,
  count,
  empty,
  children,
}: {
  slug: string
  query: UseQueryResult<T>
  count: (data: T) => string
  empty: (data: T) => boolean
  children: (data: T) => ReactNode
}) {
  const { data, error } = query
  return (
    <section data-testid={`view-${slug}`}>
      {error ? (
        <ErrorBanner error={asApiError(error)} />
      ) : !data ? (
        <div data-state="loading">
          <Loading />
        </div>
      ) : (
        <>
          <header className="mb-3 flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1 border-b border-line pb-2 text-sm">
            <p className="font-medium text-ink" data-testid="source-line">
              {data.source.source}
            </p>
            <p className="tabular-nums text-muted" data-testid="count-line">
              {count(data)}
            </p>
          </header>
          {empty(data) ? <Empty>nothing synced yet</Empty> : children(data)}
        </>
      )}
    </section>
  )
}
