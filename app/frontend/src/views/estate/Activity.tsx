import { useEffect, useState } from 'react'
import { api, asApiError, type ApiError, type SourceRow, type SyncRunsResponse } from '@/api'
import { SectionCard } from '@/components/SectionCard'
import { ErrorBanner } from '@/components/ui/banner'
import { Empty } from '@/components/ui/empty'
import { Mono } from '@/components/ui/mono'
import { PAGE, Pager } from '@/components/ui/pager'
import { Pill } from '@/components/ui/pill'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { num, relTime } from '@/lib/format'

const ALL = '*'

export const MONO = 'font-mono text-xs'
export const NUM = 'text-right tabular-nums'
export const KEY = 'font-medium text-dbb-charcoal'
export const LINK = 'underline decoration-dotted decoration-dbb-muted underline-offset-2 hover:decoration-solid'
export const PRE = 'max-h-[480px] overflow-auto rounded-lg bg-dbb-surface p-3 font-mono text-xs'

export function Activity({
  sources,
  source,
  onSource,
  tick,
}: {
  sources: SourceRow[]
  source: string
  onSource: (source: string) => void
  tick: number
}) {
  const [offset, setOffset] = useState(0)
  const [page, setPage] = useState<SyncRunsResponse | null>(null)
  const [error, setError] = useState<ApiError | null>(null)

  useEffect(() => {
    setOffset(0)
  }, [source, tick])

  useEffect(() => {
    let live = true
    api
      .syncRuns(source, PAGE, offset)
      .then((r) => {
        if (!live) return
        setPage(r)
        setError(null)
      })
      .catch((e) => live && setError(asApiError(e)))
    return () => {
      live = false
    }
  }, [source, offset, tick])

  const labels = new Map(sources.map((s) => [s.source, s.label]))
  const runs = page?.runs ?? []
  const total = page?.total ?? 0

  return (
    <SectionCard
      title="Activity"
      headerRight={
        <div className="flex flex-wrap items-center gap-2">
          <Select value={source || ALL} onValueChange={(v) => onSource(v === ALL ? '' : v)}>
            <SelectTrigger className="h-8 w-44">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value={ALL}>all sources</SelectItem>
              {sources.map((s) => (
                <SelectItem key={s.source} value={s.source}>
                  {s.label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
          {page && <Pager className="mt-0 border-0 pt-0" offset={offset} count={runs.length} total={total} onPage={setOffset} />}
        </div>
      }
    >
      <ErrorBanner error={error} className="mb-3" />
      {!page && !error ? (
        <Empty>loading…</Empty>
      ) : runs.length === 0 ? (
        <Empty>no sync runs yet</Empty>
      ) : (
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>When</TableHead>
              <TableHead>Source</TableHead>
              <TableHead>Outcome</TableHead>
              <TableHead className={NUM}>Rows</TableHead>
              <TableHead>Detail</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {runs.map((r) => (
              <TableRow key={r.id} className={r.ok ? undefined : 'bg-dbb-clay/5'}>
                <TableCell className="whitespace-nowrap" title={r.started_at}>
                  {relTime(r.started_at)}
                </TableCell>
                <TableCell className="whitespace-nowrap">
                  <span className={KEY}>{labels.get(r.source) ?? r.source}</span> <Mono>{r.source}</Mono>
                </TableCell>
                <TableCell>
                  <Pill tone={r.ok ? 'ok' : 'err'}>{r.ok ? 'ok' : 'failed'}</Pill>
                </TableCell>
                <TableCell className={NUM}>{num(r.rows_written)}</TableCell>
                <TableCell>
                  {r.detail && (
                    <span className="inline-block max-w-[48ch] truncate align-bottom" title={r.detail}>
                      {r.detail}
                    </span>
                  )}
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      )}
    </SectionCard>
  )
}
