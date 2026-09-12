import { useState } from 'react'
import { useQueries } from '@tanstack/react-query'
import { Navigate, useParams } from 'react-router-dom'
import { asApiError, getMetric, type PageSpec } from '@/api'
import { MetricCard } from '@/cards/MetricCard'
import { Definition } from '@/components/Definition'
import { EmptyPage } from '@/components/EmptyPage'
import { ErrorBanner } from '@/components/ui/banner'
import { Loading } from '@/components/ui/loading'
import { bounds, type Range } from '@/lib/range'

export function Page({
  pages,
  first,
  today,
  todayError,
  range,
}: {
  pages: Record<string, PageSpec>
  first: string
  today: string | null
  todayError: unknown
  range: Range
}) {
  const { page = '' } = useParams()
  const spec: PageSpec | undefined = pages[page]
  const [open, setOpen] = useState<string | null>(null)
  const span = spec?.range && today ? bounds(range, today) : null
  const cards = spec?.sections.flatMap((section) => section.cards) ?? []
  const results = useQueries({
    queries: cards.map((card) => ({
      queryKey: ['metric', card.metric, span],
      queryFn: () => getMetric(card.metric, span ? { ...span, compare: 'previous' } : undefined),
      enabled: !spec?.range || !!span,
    })),
  })

  if (!spec) return <Navigate to={`/${first}`} replace />
  if (spec.range && !today) return todayError ? <ErrorBanner error={asApiError(todayError)} /> : <Loading />

  const byMetric = new Map(cards.map((card, i) => [card.metric, results[i]]))
  const allEmpty = results.length > 0 && results.every((r) => r.data?.entities === 0)

  return (
    <>
      {allEmpty && <EmptyPage />}
      {spec.sections.map((section) => (
        <section key={section.label} className="mt-8 first:mt-0" data-testid="section">
          <h2 className="mb-3 border-b border-line pb-2 text-xs font-medium uppercase tracking-wide text-muted">{section.label}</h2>
          <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
            {section.cards.map((card) => (
              <MetricCard key={card.metric} card={card} query={byMetric.get(card.metric)!} onDefinition={() => setOpen(card.metric)} />
            ))}
          </div>
        </section>
      ))}
      <Definition metric={open} last={open ? byMetric.get(open)?.data : undefined} onClose={() => setOpen(null)} />
    </>
  )
}
