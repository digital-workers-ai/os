import { Outlet, useMatch } from 'react-router-dom'
import type { PageSpec } from '@/api'
import { RangePicker } from '@/components/RangePicker'
import { TopNav } from '@/components/TopNav'
import type { Range } from '@/lib/range'

export function Layout({
  pages,
  today,
  range,
  onRange,
}: {
  pages: Record<string, PageSpec>
  today: string | null
  range: Range
  onRange: (range: Range) => void
}) {
  const page = useMatch('/:page')?.params.page
  const ranged = !!page && !!pages[page]?.range && !!today
  return (
    <div className="min-h-screen bg-surface">
      <TopNav pages={pages} right={ranged ? <RangePicker range={range} today={today} onChange={onRange} /> : null} />
      <main className="max-w-7xl mx-auto px-4 md:px-6 py-5 md:py-8" data-testid="page-main">
        <Outlet />
      </main>
    </div>
  )
}
