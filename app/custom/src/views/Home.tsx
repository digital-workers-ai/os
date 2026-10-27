import { useQuery } from '@tanstack/react-query'
import { Camera, FileText, Mic, Plus, ScanLine, type LucideIcon } from 'lucide-react'
import { Link } from 'react-router-dom'
import { asApiError, getApps, type AppSummary, type Input } from '@/api'
import { ErrorBanner } from '@/components/ui/banner'
import { Empty } from '@/components/ui/empty'
import { Loading } from '@/components/ui/loading'

const ICONS: { [input in Input]: LucideIcon } = { photo: Camera, pdf: FileText, scan: ScanLine, voice: Mic }

function AppCard({ app }: { app: AppSummary }) {
  return (
    <Link
      to={`/apps/${app.name}/new`}
      className="flex flex-col gap-1.5 rounded-xl border bg-card p-4 shadow-sm transition-colors hover:bg-accent"
      data-testid={`app-card-${app.name}`}
    >
      <span className="flex items-center gap-3">
        <span className="font-medium text-ink">{app.title}</span>
        <span className="ml-auto flex items-center gap-1.5 text-muted">
          {app.input.map((input) => {
            const Icon = ICONS[input]
            return <Icon key={input} className="size-4" aria-hidden />
          })}
        </span>
      </span>
      <span className="line-clamp-2 text-sm text-muted">{app.description}</span>
    </Link>
  )
}

export function Home() {
  const apps = useQuery({ queryKey: ['apps'], queryFn: getApps })
  const state = apps.isPending ? 'loading' : apps.error ? 'error' : 'ready'

  return (
    <div className="flex flex-col gap-5" data-testid="home-view" data-state={state}>
      <div className="flex items-center gap-3">
        <h1 className="text-xl text-ink">Apps</h1>
        <Link
          to="/new-app"
          className="ml-auto inline-flex h-9 items-center gap-2 rounded-md border border-input bg-background px-4 text-sm font-medium shadow-sm hover:bg-accent"
        >
          <Plus className="size-4" aria-hidden />
          New app
        </Link>
      </div>
      <ErrorBanner error={apps.error && asApiError(apps.error)} />
      {!apps.data ? (
        !apps.error && <Loading />
      ) : apps.data.length === 0 ? (
        <Empty testId="apps-empty">No apps yet. Describe the one you need with New app.</Empty>
      ) : (
        <div className="grid gap-3 sm:grid-cols-2">
          {apps.data.map((app) => (
            <AppCard key={app.name} app={app} />
          ))}
        </div>
      )}
    </div>
  )
}
