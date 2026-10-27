import { useQuery } from '@tanstack/react-query'
import { ExternalLink } from 'lucide-react'
import { Link } from 'react-router-dom'
import { asApiError, getThreads } from '@/api'
import { NewAppLink } from '@/components/NewAppLink'
import { ErrorBanner } from '@/components/ui/banner'
import { Card } from '@/components/ui/card'
import { Empty } from '@/components/ui/empty'
import { Loading } from '@/components/ui/loading'
import { useAppTitles } from '@/lib/apps'
import { shortDate } from '@/lib/format'

export function Threads() {
  const threads = useQuery({ queryKey: ['threads'], queryFn: getThreads })
  const apps = useAppTitles()
  const state = threads.isPending || apps.pending ? 'loading' : threads.error ? 'error' : 'ready'

  return (
    <div className="flex flex-col gap-5" data-testid="threads-view" data-state={state}>
      <div className="flex items-center gap-3">
        <h1 className="text-xl text-ink">Conversations</h1>
        <NewAppLink />
      </div>
      <ErrorBanner error={threads.error && asApiError(threads.error)} />
      {!threads.data ? (
        !threads.error && <Loading />
      ) : threads.data.length === 0 ? (
        <Empty testId="threads-empty">No conversations yet. Start one with New app, or with Change this app on an app's page.</Empty>
      ) : (
        <Card className="p-0 sm:p-0">
          <ul className="flex flex-col divide-y divide-line">
            {threads.data.map((thread) => (
              <li key={thread.id} className="flex items-center gap-4 px-4 py-3" data-testid="thread-row">
                <Link to={`/threads/${thread.id}`} className="flex min-w-0 flex-1 flex-col gap-0.5" data-testid="thread-open">
                  <span className="truncate font-medium text-ink">{thread.title ?? 'No draft yet'}</span>
                  <span className="text-xs text-muted">
                    {thread.app ? `Change ${apps.titleOf(thread.app)}` : 'New app'} · {shortDate(thread.created_at)}
                  </span>
                </Link>
                {thread.issue && (
                  <a
                    href={thread.issue.url}
                    target="_blank"
                    rel="noreferrer"
                    className="inline-flex shrink-0 items-center gap-1.5 text-sm text-ink underline underline-offset-4"
                    data-testid="thread-issue"
                  >
                    Issue #{thread.issue.number}
                    <ExternalLink className="size-4" aria-hidden />
                  </a>
                )}
              </li>
            ))}
          </ul>
        </Card>
      )}
    </div>
  )
}
