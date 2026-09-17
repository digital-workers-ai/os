import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useNavigate, useParams } from 'react-router-dom'
import { asApiError, createThread, getThread, getThreads, sendTurn } from '@/api'
import { Composer } from '@/components/chat/Composer'
import { Threads } from '@/components/chat/Threads'
import { Turns } from '@/components/chat/Turns'
import { ErrorBanner } from '@/components/ui/banner'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Loading } from '@/components/ui/loading'

export function Create() {
  const { seq } = useParams()
  const current = seq ? Number(seq) : null
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const threads = useQuery({ queryKey: ['threads'], queryFn: getThreads })
  const thread = useQuery({ queryKey: ['thread', current], queryFn: () => getThread(current!), enabled: current !== null })
  const create = useMutation({
    mutationFn: createThread,
    onSuccess: ({ thread }) => {
      queryClient.invalidateQueries({ queryKey: ['threads'] })
      navigate(`/create/${thread.seq}`)
    },
  })
  const send = useMutation({
    mutationFn: (text: string) => sendTurn(current!, text),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['thread', current] })
      queryClient.invalidateQueries({ queryKey: ['threads'] })
    },
  })
  const loading = threads.isPending || (current !== null && thread.isPending)
  const state = loading ? 'loading' : threads.error || thread.error ? 'error' : 'ready'
  const error = threads.error ?? thread.error ?? create.error ?? send.error

  return (
    <div className="grid gap-4 md:grid-cols-[220px_minmax(0,1fr)]" data-testid="create-view" data-state={state}>
      <Threads threads={threads.data?.threads ?? []} current={current} onNew={() => create.mutate()} creating={create.isPending} />
      <div className="flex min-w-0 flex-col gap-3">
        {error && <ErrorBanner error={asApiError(error)} />}
        {current === null ? (
          <Card data-testid="create-intro">
            <CardHeader>
              <CardTitle>Create</CardTitle>
            </CardHeader>
            <CardContent className="flex flex-col gap-2 text-sm text-muted">
              <p>
                Ask for a post, a newsletter, a blog, an image or a carousel. Studio picks the skill, reads the brand and the proof, and builds
                the finished asset right here in the thread.
              </p>
              <p>Every asset lands in Assets and on the Canvas. Start a thread with "+ new".</p>
            </CardContent>
          </Card>
        ) : thread.data ? (
          <Card className="flex flex-col gap-3" data-testid="thread">
            <CardHeader className="mb-0">
              <CardTitle className="truncate">{thread.data.title || 'untitled'}</CardTitle>
            </CardHeader>
            <div className="max-h-[60vh] min-h-[40vh] overflow-y-auto">
              <Turns turns={thread.data.turns} />
            </div>
            <Composer onSend={(text) => send.mutateAsync(text)} pending={send.isPending} />
          </Card>
        ) : thread.error ? null : (
          <Loading />
        )}
      </div>
    </div>
  )
}
