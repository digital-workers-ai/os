import { useQuery } from '@tanstack/react-query'
import { Plus } from 'lucide-react'
import { Link, useParams } from 'react-router-dom'
import { asApiError, getApp, getRecords } from '@/api'
import { ErrorBanner } from '@/components/ui/banner'
import { Empty } from '@/components/ui/empty'
import { Loading } from '@/components/ui/loading'
import { day } from '@/lib/format'
import { summary } from '@/lib/values'

export function Records() {
  const { app: name = '' } = useParams()
  const app = useQuery({ queryKey: ['app', name], queryFn: () => getApp(name) })
  const records = useQuery({ queryKey: ['records', name], queryFn: () => getRecords(name), staleTime: 0 })
  const pending = app.isPending || records.isPending
  const failed = app.error ?? records.error
  const state = pending && !failed ? 'loading' : failed ? 'error' : 'ready'

  return (
    <div className="flex flex-col gap-5" data-testid="records-view" data-state={state}>
      <ErrorBanner error={failed && asApiError(failed)} />
      {!app.data || !records.data ? (
        !failed && <Loading />
      ) : (
        <>
          <div className="flex items-center gap-3">
            <h1 className="text-xl text-ink">{app.data.title}</h1>
            <Link
              to={`/apps/${name}/new`}
              className="ml-auto inline-flex h-9 items-center gap-2 rounded-md border border-input bg-background px-4 text-sm font-medium shadow-sm hover:bg-accent"
            >
              <Plus className="size-4" aria-hidden />
              New record
            </Link>
          </div>
          {records.data.length === 0 ? (
            <Empty testId="records-empty">No saved records yet.</Empty>
          ) : (
            <div className="flex flex-col divide-y divide-line overflow-hidden rounded-xl border bg-card shadow-sm">
              {records.data.map((record) => (
                <Link
                  key={record.id}
                  to={`/records/${record.id}`}
                  className="flex items-baseline gap-3 px-4 py-3 text-sm hover:bg-accent"
                  data-testid="record-row"
                >
                  <span className="min-w-0 flex-1 text-ink">{summary(app.data, record.fields).join(' · ')}</span>
                  {record.saved_at && <span className="shrink-0 tabular-nums text-xs text-muted">{day(record.saved_at)}</span>}
                </Link>
              ))}
            </div>
          )}
        </>
      )}
    </div>
  )
}
