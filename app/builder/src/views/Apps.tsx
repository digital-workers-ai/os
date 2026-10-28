import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { asApiError, getApps, type AppSummary } from '@/api'
import { NewAppLink } from '@/components/NewAppLink'
import { ErrorBanner } from '@/components/ui/banner'
import { Card } from '@/components/ui/card'
import { Empty } from '@/components/ui/empty'
import { Loading } from '@/components/ui/loading'
import { Mono } from '@/components/ui/mono'
import { Pill, Pills } from '@/components/ui/pill'
import { extraCode } from '@/lib/apps'

const CELL = 'px-4 py-3 align-top'

function AppRow({ app }: { app: AppSummary }) {
  const code = extraCode(app)
  return (
    <tr className="border-t border-line" data-testid="app-row" data-name={app.name}>
      <td className={CELL}>
        <Link to={`/apps/${app.name}`} className="font-medium text-ink hover:underline">
          {app.title}
        </Link>
        <Mono className="block text-muted">{app.name}</Mono>
      </td>
      <td className={CELL}>
        <Pills items={app.input} />
      </td>
      <td className={CELL}>
        <Pill>{app.lands_as}</Pill>
      </td>
      <td className={CELL}>
        <Pills items={app.roles} />
      </td>
      <td className={CELL}>
        {code.length > 0 ? (
          <span className="flex flex-col gap-1">
            {code.map((file) => (
              <Mono key={file}>{file}</Mono>
            ))}
          </span>
        ) : (
          '—'
        )}
      </td>
    </tr>
  )
}

export function Apps() {
  const apps = useQuery({ queryKey: ['apps'], queryFn: getApps })
  const state = apps.isPending ? 'loading' : apps.error ? 'error' : 'ready'

  return (
    <div className="flex flex-col gap-5" data-testid="apps-view" data-state={state}>
      <div className="flex items-center gap-3">
        <h1 className="text-xl text-ink">Apps</h1>
        <NewAppLink />
      </div>
      <ErrorBanner error={apps.error && asApiError(apps.error)} />
      {!apps.data ? (
        !apps.error && <Loading />
      ) : apps.data.length === 0 ? (
        <Empty testId="apps-empty">No apps yet. Describe the first one with New app.</Empty>
      ) : (
        <Card className="overflow-hidden p-0 sm:p-0">
          <table className="w-full text-sm">
            <thead className="text-left text-xs text-muted">
              <tr>
                {[`App (${apps.data.length})`, 'Input', 'Saves as', 'Roles', 'Extra code'].map((label) => (
                  <th key={label} className="px-4 py-2 font-medium">
                    {label}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {apps.data.map((app) => (
                <AppRow key={app.name} app={app} />
              ))}
            </tbody>
          </table>
        </Card>
      )}
    </div>
  )
}
