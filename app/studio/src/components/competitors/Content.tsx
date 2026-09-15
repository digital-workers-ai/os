import { useQuery, type UseQueryResult } from '@tanstack/react-query'
import { asApiError, getContent, type ContentResponse } from '@/api'
import { ErrorBanner } from '@/components/ui/banner'
import { Card } from '@/components/ui/card'
import { Empty } from '@/components/ui/empty'
import { Loading } from '@/components/ui/loading'
import { Mono } from '@/components/ui/mono'
import { num, shortDate } from '@/lib/format'

const LABEL = 'text-xs font-medium uppercase tracking-wide text-muted'
const ROW = 'flex flex-wrap items-baseline gap-x-2 gap-y-0.5 py-1.5 text-sm'
const LIMIT = 44

const clip = (text: string) => (text.length > LIMIT ? `${text.slice(0, LIMIT)}…` : text)

const pathOf = (url: string) => url.replace(/^https?:\/\/[^/]+/, '') || '/'

function ContentBody({ query }: { query: UseQueryResult<ContentResponse> }) {
  if (query.error) return <ErrorBanner error={asApiError(query.error)} />
  if (!query.data) return <Loading />
  const data = query.data
  if (data.changes.length === 0 && data.recent_posts.length === 0) return <Empty>nothing tracked yet</Empty>
  return (
    <div className="space-y-3">
      {data.changes.length > 0 && (
        <div>
          <p className={LABEL}>page changes</p>
          <ul className="divide-y divide-line/30">
            {data.changes.map((change) => (
              <li key={`${change.competitor}|${change.url}|${change.on}`} className={ROW} data-testid="content-change" data-competitor={change.competitor}>
                <span className="text-ink">●</span>
                <span className="font-medium text-ink">{change.competitor}</span>
                <Mono className="text-muted" title={change.url}>
                  {pathOf(change.url)}
                </Mono>
                <span className="text-muted">changed {shortDate(change.on.slice(0, 10))}</span>
                <span className="flex flex-wrap items-baseline gap-1">
                  <span className="text-down line-through" title={change.before}>
                    {clip(change.before)}
                  </span>
                  <span className="text-muted">→</span>
                  <span className="text-ok" title={change.after}>
                    {clip(change.after)}
                  </span>
                </span>
              </li>
            ))}
          </ul>
        </div>
      )}
      {data.recent_posts.length > 0 && (
        <div>
          <p className={LABEL}>posts</p>
          <ul className="divide-y divide-line/30">
            {data.recent_posts.map((post) => (
              <li key={post.url} className={ROW} data-testid="content-post" data-competitor={post.competitor}>
                <span className="text-ink">●</span>
                <span className="font-medium text-ink">{post.competitor}</span>
                <span className="min-w-0 text-ink" title={post.text}>
                  “{clip(post.text)}”
                </span>
                <span className="text-muted">{shortDate(post.posted_at.slice(0, 10))}</span>
                <span className="whitespace-nowrap tabular-nums text-muted">{num(post.likes)} ♡</span>
                <a href={post.url} target="_blank" rel="noreferrer" className="text-muted hover:text-ink" title={post.url}>
                  ↗
                </a>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  )
}

export function ContentPanel() {
  const query = useQuery({ queryKey: ['content'], queryFn: getContent })
  const data = query.data
  return (
    <Card
      className="space-y-3 p-4 sm:p-5"
      data-testid="content-panel"
      data-state={query.isPending ? 'loading' : query.error ? 'error' : 'ready'}
    >
      <div className="flex flex-wrap items-baseline gap-2 border-b border-line pb-2">
        <h2 className={LABEL}>Content</h2>
        {data && (
          <span className="text-xs text-muted">
            {num(data.pages)} pages · {num(data.posts)} posts · {num(data.changes.length)} changes
          </span>
        )}
      </div>
      <ContentBody query={query} />
      <p className="border-t border-line/50 pt-2 text-xs text-muted" data-testid="content-footer">
        page changes and posts are plain queries over dated entities
      </p>
    </Card>
  )
}
