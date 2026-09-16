import { useState } from 'react'
import { keepPreviousData, useQuery } from '@tanstack/react-query'
import { asApiError, getPosts } from '@/api'
import { CompanySummary } from '@/cards/CompanySummary'
import { PostRow } from '@/cards/PostRow'
import { EmptyPage } from '@/components/EmptyPage'
import { ErrorBanner } from '@/components/ui/banner'
import { Card } from '@/components/ui/card'
import { Empty } from '@/components/ui/empty'
import { Loading } from '@/components/ui/loading'
import { Pager } from '@/components/ui/pager'
import type { Bounds } from '@/lib/range'
import { cn } from '@/lib/utils'
import { Pending, spanOf, type RangedProps } from '@/views/ranged'

const SIZE = 20
const MAX = 200

function Option({ company, on, onClick }: { company: string; on: boolean; onClick: () => void }) {
  return (
    <button
      type="button"
      aria-pressed={on}
      onClick={onClick}
      className={cn(
        'whitespace-nowrap rounded-md px-2.5 py-1 text-xs font-medium transition-colors',
        on ? 'bg-paper text-ink shadow-[0_1px_3px_rgba(0,0,0,0.06)]' : 'text-muted hover:text-ink',
      )}
      data-testid="posts-filter-option"
      data-company={company}
    >
      {company}
    </button>
  )
}

function Paged({ span }: { span: Bounds }) {
  const [filter, setFilter] = useState<string | null>(null)
  const [offset, setOffset] = useState(0)
  const [size, setSize] = useState(SIZE)
  const query = useQuery({
    queryKey: ['posts', filter, size, offset, span],
    queryFn: () => getPosts({ company: filter ?? undefined, limit: size, offset }, span),
    placeholderData: keepPreviousData,
  })
  const data = query.data
  const pick = (company: string) => {
    setFilter(company === 'all' || company === filter ? null : company)
    setOffset(0)
  }
  const changeSize = (n: number) => {
    setSize(n)
    setOffset(0)
  }
  return (
    <section data-testid="posts" data-state={query.error ? 'error' : data && !query.isPlaceholderData ? 'ready' : 'loading'}>
      {query.error && <ErrorBanner error={asApiError(query.error)} />}
      {!data && !query.error && <Loading />}
      {data && data.total === 0 && !filter && <EmptyPage />}
      {data && (data.total > 0 || filter) && (
        <>
          <div className="grid grid-cols-2 gap-4 md:grid-cols-3 lg:grid-cols-4">
            {data.companies.map((company) => (
              <CompanySummary key={company.name} company={company} />
            ))}
          </div>
          <div className="mb-3 mt-8 flex flex-wrap items-center justify-between gap-2 border-b border-line pb-2">
            <h2 className="text-xs font-medium uppercase tracking-wide text-muted">Posts</h2>
            <div className="flex flex-wrap items-center gap-0.5 rounded-lg bg-wash p-0.5" role="group" aria-label="company" data-testid="posts-filter">
              <Option company="all" on={filter === null} onClick={() => pick('all')} />
              {data.companies.map((company) => (
                <Option key={company.name} company={company.name} on={filter === company.name} onClick={() => pick(company.name)} />
              ))}
            </div>
          </div>
          <Card>
            {data.posts.length === 0 ? (
              <Empty>no posts for {filter}</Empty>
            ) : (
              <ul data-testid="posts-list">
                {data.posts.map((post) => (
                  <PostRow key={post.canonical_id} post={post} />
                ))}
              </ul>
            )}
            <Pager
              offset={offset}
              count={data.posts.length}
              total={data.total}
              onPage={setOffset}
              size={size}
              allSize={Math.min(data.total, MAX)}
              onSize={changeSize}
              pageSize={SIZE}
            />
          </Card>
        </>
      )}
    </section>
  )
}

export function Posts(props: RangedProps) {
  const span = spanOf(props)
  if (!span) return <Pending error={props.todayError} />
  return <Paged key={`${span.from}|${span.to}`} span={span} />
}
