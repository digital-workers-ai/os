import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom'
import { asApiError, getDashboards, getMetric, isTable, type MetricCardSpec } from '@/api'
import { Layout } from '@/components/Layout'
import { ErrorBanner } from '@/components/ui/banner'
import { Empty } from '@/components/ui/empty'
import { Loading } from '@/components/ui/loading'
import { DEFAULT_RANGE, type Range } from '@/lib/range'
import { Page } from '@/views/Page'

export default function App() {
  const dashboards = useQuery({ queryKey: ['dashboards'], queryFn: getDashboards })
  const pages = dashboards.data?.dashboards ?? {}
  const first = Object.keys(pages)[0]
  const firstMetric = Object.values(pages)
    .flatMap((page) => page.sections.flatMap((section) => section.cards))
    .find((card): card is MetricCardSpec => !isTable(card))?.metric
  const today = useQuery({
    queryKey: ['metric', firstMetric, null],
    queryFn: () => getMetric(firstMetric!),
    enabled: !!firstMetric,
    select: (r) => r.as_of.slice(0, 10),
    staleTime: Infinity,
  })
  const [range, setRange] = useState<Range>(DEFAULT_RANGE)

  if (dashboards.error) {
    return (
      <main className="p-6">
        <ErrorBanner error={asApiError(dashboards.error)} />
      </main>
    )
  }
  if (!dashboards.data) return <Loading />
  if (!first) return <Empty>no dashboards declared</Empty>

  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<Layout pages={pages} today={today.data ?? null} range={range} onRange={setRange} />}>
          <Route index element={<Navigate to={`/${first}`} replace />} />
          <Route
            path=":page"
            element={<Page pages={pages} first={first} today={today.data ?? null} todayError={today.error} range={range} />}
          />
          <Route path="*" element={<Navigate to={`/${first}`} replace />} />
        </Route>
      </Routes>
    </BrowserRouter>
  )
}
