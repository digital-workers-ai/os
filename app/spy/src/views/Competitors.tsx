import { useQuery } from '@tanstack/react-query'
import { getDefinition, getSources, type Source, type SpyDefinition } from '@/api'
import { StateSection } from '@/components/StateSection'
import { Card } from '@/components/ui/card'
import { Empty } from '@/components/ui/empty'
import { Mono } from '@/components/ui/mono'
import { Pill } from '@/components/ui/pill'
import { num } from '@/lib/format'
import { cn } from '@/lib/utils'

const HEAD = 'whitespace-nowrap pb-2 pr-4 text-left font-medium text-muted'
const CELL = 'py-2 pr-4 align-middle text-muted'

const isSpy = (source: Source) => source.category === 'Spy'

function Aliases({ aliases }: { aliases: string[] }) {
  if (aliases.length === 0) return <>—</>
  return (
    <span className="flex flex-wrap gap-1">
      {aliases.map((alias) => (
        <Pill key={alias}>{alias}</Pill>
      ))}
    </span>
  )
}

function Definition({ data }: { data: SpyDefinition }) {
  return (
    <>
      <Card>
        <div className="mb-4 flex flex-wrap items-center gap-2 text-sm" data-testid="competitors-brand">
          <Mono className="text-sm font-medium text-ink">{data.brand.name}</Mono>
          <span className="text-muted">{data.brand.domain}</span>
          {data.brand.aliases.length > 0 && <Aliases aliases={data.brand.aliases} />}
          <Pill tone="unknown">
            {data.country} · {data.language}
          </Pill>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-sm" data-testid="competitors-table">
            <thead className="text-left text-muted">
              <tr className="border-b border-line">
                <th className={HEAD}>Competitor</th>
                <th className={HEAD}>Domain</th>
                <th className={HEAD}>Aliases</th>
                <th className={HEAD}>LinkedIn</th>
                <th className={HEAD}>Google advertiser</th>
              </tr>
            </thead>
            <tbody>
              {data.competitors.map((competitor) => (
                <tr key={competitor.name} className="border-b border-line/30 last:border-0" data-company={competitor.name}>
                  <td className={cn(CELL, 'whitespace-nowrap font-medium text-ink')}>{competitor.name}</td>
                  <td className={CELL}>{competitor.domain}</td>
                  <td className={CELL}>
                    <Aliases aliases={competitor.aliases} />
                  </td>
                  <td className={CELL}>{competitor.linkedin ? <Mono>{competitor.linkedin}</Mono> : '—'}</td>
                  <td className={CELL}>{competitor.google_advertiser_id ? <Mono>{competitor.google_advertiser_id}</Mono> : '—'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>
      <h3 className="mb-2 mt-6 text-sm font-medium text-ink">Tracked queries ({num(data.queries.length)})</h3>
      <ol className="list-inside list-decimal text-sm text-ink" data-testid="competitors-queries">
        {data.queries.map((query) => (
          <li key={query} className="py-0.5">
            {query}
          </li>
        ))}
      </ol>
    </>
  )
}

function Sources({ sources }: { sources: Source[] }) {
  if (sources.length === 0) return <Empty>no Spy sources</Empty>
  return (
    <ul className="divide-y divide-line/30 text-sm">
      {sources.map((source) => (
        <li key={source.source} className="flex items-center justify-between gap-3 py-2" data-source={source.source}>
          <span className="flex min-w-0 flex-wrap items-baseline gap-2">
            <span className="font-medium text-ink">{source.label}</span>
            <Mono className="text-muted">{source.source}</Mono>
          </span>
          <Pill tone={source.enabled ? 'ok' : 'unknown'} data-testid="source-state">
            {source.enabled ? 'on' : 'off'}
          </Pill>
        </li>
      ))}
    </ul>
  )
}

export function Competitors() {
  const definition = useQuery({ queryKey: ['definition'], queryFn: getDefinition, staleTime: Infinity })
  const sources = useQuery({ queryKey: ['sources'], queryFn: getSources })
  return (
    <>
      <StateSection id="competitors" label="Competitors" queries={[definition]}>
        {definition.data && <Definition data={definition.data} />}
      </StateSection>
      <StateSection id="competitors-sources" label="Spy sources" queries={[sources]} className="mt-8">
        <Card>{sources.data && <Sources sources={sources.data.sources.filter(isSpy)} />}</Card>
      </StateSection>
    </>
  )
}
