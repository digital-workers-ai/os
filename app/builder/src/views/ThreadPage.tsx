import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { ExternalLink } from 'lucide-react'
import { Link, useParams } from 'react-router-dom'
import { asApiError, getThread, sendTurn, submitThread } from '@/api'
import { Composer } from '@/components/Composer'
import { DraftCard, TryCard } from '@/components/Draft'
import { Turns } from '@/components/Turns'
import { ErrorBanner } from '@/components/ui/banner'
import { Button } from '@/components/ui/button'
import { Card, CardTitle } from '@/components/ui/card'
import { Loading } from '@/components/ui/loading'
import { useAppTitles } from '@/lib/apps'

const HEIGHT = 'lg:h-[calc(100vh-7.5rem-1px)]'

const emptyText = (named: string | null) =>
  named
    ? `Say what should change in ${named}. The builder redrafts its app.yaml, and you can try the draft on a sample before you send it for review.`
    : 'Describe what your team needs to record. The builder asks what it needs to know, drafts the app, and lets you try it on a sample before you send it for review.'

export function ThreadPage() {
  const { id = '' } = useParams()
  const queryClient = useQueryClient()
  const thread = useQuery({ queryKey: ['thread', id], queryFn: () => getThread(id) })
  const apps = useAppTitles()
  const refresh = () =>
    Promise.all([queryClient.invalidateQueries({ queryKey: ['thread', id] }), queryClient.invalidateQueries({ queryKey: ['threads'] })])
  const send = useMutation({ mutationFn: (text: string) => sendTurn(id, text), onSuccess: refresh })
  const submit = useMutation({ mutationFn: () => submitThread(id), onSuccess: refresh })
  const state = thread.isPending || apps.pending ? 'loading' : thread.error ? 'error' : 'ready'
  const error = thread.error ?? send.error

  if (!thread.data)
    return (
      <div data-testid="thread-view" data-state={state}>
        {thread.error ? <ErrorBanner error={asApiError(thread.error)} /> : <Loading />}
      </div>
    )

  const { app, title, issue, turns } = thread.data
  const named = app && apps.titleOf(app)
  const latest = [...turns].reverse().find((turn) => turn.draft !== null)

  return (
    <div className="grid items-start gap-4 lg:grid-cols-[minmax(0,1fr)_420px]" data-testid="thread-view" data-state={state}>
      <Card className={`flex min-h-[28rem] flex-col gap-3 ${HEIGHT}`} data-testid="thread">
        <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
          <h1 className="truncate text-base font-semibold text-ink">{title ?? (named ? `Change ${named}` : 'New app')}</h1>
          {app ? (
            <Link to={`/apps/${app}`} className="text-xs text-muted underline underline-offset-4" data-testid="thread-app">
              Changing {named}
            </Link>
          ) : (
            <span className="text-xs text-muted">New app</span>
          )}
        </div>
        <ErrorBanner error={error && asApiError(error)} />
        <div className="min-h-0 flex-1 overflow-y-auto">
          <Turns turns={turns} open={!issue} pending={send.isPending} empty={emptyText(named)} onSend={(text) => send.mutate(text)} />
        </div>
        {issue ? (
          <p className="border-t border-line pt-3 text-sm text-muted">Sent for review as issue #{issue.number}. This conversation is closed.</p>
        ) : (
          <Composer
            onSend={(text) => send.mutateAsync(text)}
            pending={send.isPending}
            placeholder={app ? 'What should change?' : 'For example: we pour concrete and want every pour logged with a photo of the slump test.'}
          />
        )}
      </Card>
      <aside className={`flex flex-col gap-4 lg:overflow-y-auto ${HEIGHT}`}>
        {latest?.draft ? (
          <>
            <DraftCard turn={latest} />
            <TryCard thread={id} draft={latest.draft} />
            <Card className="flex flex-col gap-3">
              <CardTitle>Review</CardTitle>
              {issue ? (
                <a
                  href={issue.url}
                  target="_blank"
                  rel="noreferrer"
                  className="inline-flex items-center gap-2 self-start text-sm text-ink underline underline-offset-4"
                  data-testid="builder-issue-link"
                >
                  Filed as issue #{issue.number}
                  <ExternalLink className="size-4" aria-hidden />
                </a>
              ) : (
                <>
                  <p className="text-sm text-muted">Files the conversation and the draft as a GitHub issue. Nothing is built until a person approves it.</p>
                  <Button
                    variant="solid"
                    className="self-start"
                    disabled={latest.problems.length > 0 || submit.isPending}
                    onClick={() => submit.mutate()}
                    data-testid="builder-submit"
                  >
                    {submit.isPending ? 'Sending…' : 'Send for review'}
                  </Button>
                </>
              )}
              <ErrorBanner error={submit.error && asApiError(submit.error)} />
            </Card>
          </>
        ) : (
          <Card>
            <p className="text-sm text-muted">The draft shows here once the builder writes one.</p>
          </Card>
        )}
      </aside>
    </div>
  )
}
