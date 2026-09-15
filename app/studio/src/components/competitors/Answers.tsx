import { useState } from 'react'
import { useQuery, type UseQueryResult } from '@tanstack/react-query'
import { asApiError, getAnswers, type AnswersResponse } from '@/api'
import { ErrorBanner } from '@/components/ui/banner'
import { Card } from '@/components/ui/card'
import { Empty } from '@/components/ui/empty'
import { Input } from '@/components/ui/input'
import { Loading } from '@/components/ui/loading'
import { Mono } from '@/components/ui/mono'
import { Pill } from '@/components/ui/pill'
import { num, pct } from '@/lib/format'
import { cn } from '@/lib/utils'

const HEAD = 'whitespace-nowrap pb-2 pr-4 text-left font-medium text-muted last:pr-0'
const CELL = 'py-2 pr-4 align-middle last:pr-0'
const LABEL = 'text-xs font-medium uppercase tracking-wide text-muted'

const asShare = (rate: number) => (rate > 1 ? rate / 100 : rate)

function AnswersBody({ query }: { query: UseQueryResult<AnswersResponse> }) {
  if (query.error) return <ErrorBanner error={asApiError(query.error)} />
  if (!query.data) return <Loading />
  const data = query.data
  if (data.prompts.length === 0) return <Empty>no prompts tracked</Empty>
  const rates = Object.entries(data.mention_rate).sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0]))
  return (
    <div className="space-y-3">
      <div className="overflow-x-auto">
        <table className="w-full text-sm" data-testid="answers-table">
          <thead className="text-left text-muted">
            <tr className="border-b border-line">
              <th className={HEAD}>prompt</th>
              {data.engines.map((engine) => (
                <th key={engine} className={HEAD} data-engine={engine}>
                  {engine}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {data.prompts.map((row) => (
              <tr key={row.prompt} className="border-b border-line/30 last:border-0" data-testid="answers-row">
                <td className={cn(CELL, 'font-medium text-ink')}>“{row.prompt}”</td>
                {data.engines.map((engine) => {
                  const named = Object.entries(row.named[engine] ?? {})
                  return (
                    <td key={engine} className={CELL} data-engine={engine}>
                      {named.length === 0 ? (
                        <span className="text-muted">—</span>
                      ) : (
                        <span className="flex flex-wrap gap-1">
                          {named.map(([brand, wasNamed]) => (
                            <Pill key={brand} tone={wasNamed ? 'ok' : 'down'}>
                              {brand} {wasNamed ? '✓' : '✗'}
                            </Pill>
                          ))}
                        </span>
                      )}
                    </td>
                  )
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
        <div data-testid="answers-mention-rate">
          <p className={LABEL}>mentioned</p>
          <p className="mt-1 text-sm text-ink">
            {rates.length === 0 ? '—' : rates.map(([brand, rate]) => `${brand} ${pct(asShare(rate))}`).join(' · ')}
          </p>
        </div>
        <div data-testid="answers-cited">
          <p className={LABEL}>cited: {num(data.cited.length)} of our URLs</p>
          {data.cited.length === 0 ? (
            <p className="mt-1 text-sm text-muted">—</p>
          ) : (
            <ul className="mt-1 space-y-0.5">
              {data.cited.map((entry) => (
                <li key={entry.url} className="flex items-baseline justify-between gap-2">
                  <Mono className="min-w-0 text-muted" title={entry.url}>
                    {entry.url}
                  </Mono>
                  <span className="shrink-0 text-sm tabular-nums text-ink">{num(entry.count)}</span>
                </li>
              ))}
            </ul>
          )}
        </div>
      </div>
    </div>
  )
}

export function AnswersPanel() {
  const [prompt, setPrompt] = useState('')
  const query = useQuery({
    queryKey: ['answers', prompt],
    queryFn: () => getAnswers(prompt || undefined),
  })
  const data = query.data
  return (
    <Card
      className="space-y-3 p-4 sm:p-5"
      data-testid="answers-panel"
      data-state={query.isPending ? 'loading' : query.error ? 'error' : 'ready'}
    >
      <div className="flex flex-wrap items-center justify-between gap-2 border-b border-line pb-2">
        <div className="flex flex-wrap items-baseline gap-2">
          <h2 className={LABEL}>AI answers</h2>
          {data && (
            <span className="text-xs text-muted">
              {num(data.prompts.length)} prompts · {data.engines.join(' ')}
            </span>
          )}
        </div>
        <Input
          aria-label="prompt"
          placeholder="prompt…"
          className="h-8 w-full text-xs sm:w-56"
          value={prompt}
          onChange={(event) => setPrompt(event.target.value)}
          data-testid="answers-filter-prompt"
        />
      </div>
      <AnswersBody query={query} />
      <p className="border-t border-line/50 pt-2 text-xs text-muted" data-testid="answers-footer">
        answers are plain queries over dated entities
      </p>
    </Card>
  )
}
