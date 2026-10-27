import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useNavigate, useParams } from 'react-router-dom'
import { asApiError, createThread, getApp, getYaml } from '@/api'
import { Facts, Fields, TemplateParts } from '@/components/Definition'
import { ErrorBanner } from '@/components/ui/banner'
import { Button } from '@/components/ui/button'
import { Card, CardHeader, CardTitle } from '@/components/ui/card'
import { Loading } from '@/components/ui/loading'
import { Mono } from '@/components/ui/mono'
import { openThread } from '@/lib/threads'

export function AppPage() {
  const { app: name = '' } = useParams()
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const app = useQuery({ queryKey: ['app', name], queryFn: () => getApp(name) })
  const yaml = useQuery({ queryKey: ['yaml', name], queryFn: () => getYaml(name) })
  const change = useMutation({
    mutationFn: () => createThread(name),
    onSuccess: (thread) => openThread(queryClient, navigate, thread),
  })
  const state = app.isPending || yaml.isPending ? 'loading' : app.error || yaml.error ? 'error' : 'ready'
  const error = app.error ?? yaml.error ?? change.error

  return (
    <div className="flex flex-col gap-5" data-testid="app-view" data-state={state}>
      <ErrorBanner error={error && asApiError(error)} />
      {app.data && yaml.data ? (
        <>
          <div className="flex items-start gap-3">
            <div className="flex min-w-0 flex-col gap-1">
              <h1 className="text-xl text-ink">{app.data.title}</h1>
              <Mono className="text-muted">{app.data.name}</Mono>
              <p className="text-sm text-muted">{app.data.description}</p>
            </div>
            <Button variant="solid" className="ml-auto shrink-0" disabled={change.isPending} onClick={() => change.mutate()}>
              Change this app
            </Button>
          </div>
          <div className="grid grid-cols-1 items-start gap-4 lg:grid-cols-2">
            <Card className="flex flex-col gap-5">
              <Facts app={app.data} />
              <div className="flex flex-col gap-2">
                <CardTitle>Fields</CardTitle>
                <Fields fields={app.data.fields} />
              </div>
              {app.data.template && (
                <div className="flex flex-col gap-2">
                  <CardTitle>Template: {app.data.template.kind}</CardTitle>
                  <TemplateParts template={app.data.template} />
                </div>
              )}
            </Card>
            <Card>
              <CardHeader>
                <CardTitle>
                  <Mono className="text-sm">app.yaml</Mono>
                </CardTitle>
              </CardHeader>
              <pre className="code" data-testid="app-yaml">
                {yaml.data.yaml}
              </pre>
            </Card>
          </div>
        </>
      ) : (
        !error && <Loading />
      )}
    </div>
  )
}
