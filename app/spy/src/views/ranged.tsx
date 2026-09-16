import type { ReactNode } from 'react'
import { asApiError } from '@/api'
import { ErrorBanner } from '@/components/ui/banner'
import { Loading } from '@/components/ui/loading'
import { bounds, type Bounds, type Range } from '@/lib/range'

export interface RangedProps {
  today: string | null
  todayError: unknown
  range: Range
}

export const spanOf = ({ today, range }: RangedProps): Bounds | null => (today ? bounds(range, today) : null)

export function Pending({ error }: { error: unknown }) {
  if (error) return <ErrorBanner error={asApiError(error)} />
  return (
    <div data-state="loading">
      <Loading />
    </div>
  )
}

export function PageSection({ page, label, children }: { page: string; label: string; children?: ReactNode }) {
  return (
    <section data-testid={page} data-state="ready">
      <h2 className="mb-3 border-b border-line pb-2 text-xs font-medium uppercase tracking-wide text-muted">{label}</h2>
      {children}
    </section>
  )
}
