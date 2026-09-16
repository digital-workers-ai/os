import type { ReactNode } from 'react'
import { asApiError } from '@/api'
import { ErrorBanner } from '@/components/ui/banner'
import { Loading } from '@/components/ui/loading'

export interface Queried {
  isPending: boolean
  error: unknown
}

export const stateOf = (queries: Queried[]) =>
  queries.some((query) => query.error) ? 'error' : queries.some((query) => query.isPending) ? 'loading' : 'ready'

export function StateSection({
  id,
  label,
  queries,
  className,
  children,
}: {
  id: string
  label: string
  queries: Queried[]
  className?: string
  children?: ReactNode
}) {
  const state = stateOf(queries)
  const failed = queries.find((query) => query.error)
  return (
    <section className={className} data-testid={id} data-state={state}>
      <h2 className="mb-3 border-b border-line pb-2 text-xs font-medium uppercase tracking-wide text-muted">{label}</h2>
      {state === 'error' ? <ErrorBanner error={asApiError(failed?.error)} /> : state === 'loading' ? <Loading /> : children}
    </section>
  )
}
