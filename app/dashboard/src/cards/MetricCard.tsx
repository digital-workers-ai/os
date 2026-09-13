import type { ComponentType, ReactNode } from 'react'
import type { UseQueryResult } from '@tanstack/react-query'
import { Info } from 'lucide-react'
import { asApiError, type MetricCardSpec, type MetricResponse, type Shape } from '@/api'
import { Breakdown } from '@/cards/Breakdown'
import { Kpi } from '@/cards/Kpi'
import { Ratio } from '@/cards/Ratio'
import { Series } from '@/cards/Series'
import { Banner, ErrorBanner } from '@/components/ui/banner'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Empty } from '@/components/ui/empty'
import { Loading } from '@/components/ui/loading'
import { cn } from '@/lib/utils'

const BODIES: Record<Shape, ComponentType<{ data: MetricResponse }>> = { kpi: Kpi, ratio: Ratio, breakdown: Breakdown, series: Series }

const WIDE: Shape[] = ['breakdown', 'series']

type QueryState = { isPending: boolean; error: unknown }

const state = (query: QueryState) => (query.isPending ? 'loading' : query.error ? 'error' : 'ready')

export function CardShell({
  id,
  shape,
  label,
  wide,
  query,
  onDefinition,
  children,
}: {
  id: string
  shape: string
  label: string
  wide: boolean
  query: QueryState
  onDefinition: () => void
  children: ReactNode
}) {
  return (
    <Card className={cn('flex flex-col', wide && 'col-span-2')} data-testid={`card-${id}`} data-shape={shape} data-state={state(query)}>
      <CardHeader className="mb-3 items-center">
        <CardTitle className="text-sm font-medium text-muted">{label}</CardTitle>
        <Button
          variant="ghost"
          size="icon"
          className="-mr-2 -mt-1 h-7 w-7 text-muted hover:text-ink"
          aria-label={`definition of ${label}`}
          onClick={onDefinition}
          data-testid={`definition-${id}`}
        >
          <Info size={14} />
        </Button>
      </CardHeader>
      <CardContent className="min-w-0 flex-1">{children}</CardContent>
    </Card>
  )
}

function Body({ shape, query }: { shape: Shape; query: UseQueryResult<MetricResponse> }) {
  if (query.error) return <ErrorBanner error={asApiError(query.error)} />
  if (!query.data) return <Loading />
  const data = query.data
  if (data.error) {
    return (
      <Banner tone="err" testId="card-error">
        {data.error}
      </Banner>
    )
  }
  const Shape = BODIES[shape]
  return (
    <>
      {data.mixed_currencies && (
        <Banner className="mb-3" testId="card-note">
          {data.note ?? data.mixed_currencies.join(', ')}
        </Banner>
      )}
      {data.entities === 0 ? <Empty>no data</Empty> : <Shape data={data} />}
    </>
  )
}

export function MetricCard({ card, query, onDefinition }: { card: MetricCardSpec; query: UseQueryResult<MetricResponse>; onDefinition: () => void }) {
  return (
    <CardShell id={card.metric} shape={card.shape} label={card.label} wide={WIDE.includes(card.shape)} query={query} onDefinition={onDefinition}>
      <Body shape={card.shape} query={query} />
    </CardShell>
  )
}
