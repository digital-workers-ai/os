import { useState } from 'react'
import { useQueries } from '@tanstack/react-query'
import { Navigate, useParams } from 'react-router-dom'
import { asApiError, getMetric, getTop, isTable, type CardSpec, type MetricCardSpec, type PageSpec } from '@/api'
import { MetricCard } from '@/cards/MetricCard'
import { TableCard, tableId } from '@/cards/TableCard'
import { Definition, type Opened } from '@/components/Definition'
import { EmptyPage } from '@/components/EmptyPage'
import { Findings } from '@/components/Findings'
import { Goals } from '@/components/Goals'
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
  const [open, setOpen] = useState<CardSpec | null>(null)
  const span = spec?.range && today ? bounds(range, today) : null
  const filter = spec?.filter ?? {}
  const cards = spec?.sections.flatMap((section) => section.cards) ?? []
  const metrics = cards.filter((card): card is MetricCardSpec => !isTable(card))
  const tables = cards.filter(isTable)
  const enabled = !spec?.range || !!span
  const metricResults = useQueries({
    queries: metrics.map((card) => ({
      queryKey: ['metric', card.metric, span, filter],
      queryFn: () => getMetric(card.metric, { ...(span ? { ...span, compare: 'previous' as const } : {}), filter }),
      enabled,
    })),
  })
  const tableResults = useQueries({
    queries: tables.map((card) => ({
      queryKey: ['top', card, span, filter],
      queryFn: () => getTop(card, { ...(span ?? {}), filter }),
      enabled,
    })),
  })

  if (!spec) return <Navigate to={`/${first}`} replace />
  if (spec.range && !today) {
    if (todayError) return <ErrorBanner error={asApiError(todayError)} />
    return (
      <div data-state="loading">
        <Loading />
      </div>
    )
  }

  const byMetric = new Map(metrics.map((card, i) => [card.metric, metricResults[i]]))
  const byTable = new Map(tables.map((card, i) => [card, tableResults[i]]))
  const allEmpty = metricResults.length > 0 && metricResults.every((r) => r.data?.entities === 0)
  const opened: Opened | null = !open
    ? null
    : isTable(open)
      ? { table: open, last: byTable.get(open)?.data, filter: { ...filter, ...open.filter } }
      : { metric: open, last: byMetric.get(open.metric)?.data }

  return (
    <>
      {allEmpty && <EmptyPage />}
      {spec.goals && <Goals />}
      {spec.findings && <Findings />}
      {spec.sections.map((section) => (
        <section key={section.label} className="mt-8 first:mt-0" data-testid="section">
          <h2 className="mb-3 border-b border-line pb-2 text-xs font-medium uppercase tracking-wide text-muted">{section.label}</h2>
          <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
            {section.cards.map((card) =>
              isTable(card) ? (
                <TableCard key={tableId(card)} card={card} query={byTable.get(card)!} onDefinition={() => setOpen(card)} />
              ) : (
                <MetricCard key={card.metric} card={card} query={byMetric.get(card.metric)!} onDefinition={() => setOpen(card)} />
              ),
            )}
          </div>
        </section>
      ))}
      <Definition open={opened} onClose={() => setOpen(null)} />
    </>
  )
}
