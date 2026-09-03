import { useEffect, useState, type ReactNode } from 'react'
import { api, asApiError, type ApiError, type SourceRow, type SyncRunsResponse } from '@/api'
import { SectionCard } from '@/components/SectionCard'
import { Button } from '@/components/ui/button'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { cn } from '@/lib/utils'

const PAGE = 50
const ALL = '*'

export const num = (n: number) => n.toLocaleString()

export function relTime(iso: string | null): string {
  if (!iso) return 'never'
  const then = new Date(iso).getTime()
  if (Number.isNaN(then)) return 'never'
  const secs = Math.max(0, Math.round((Date.now() - then) / 1000))
  if (secs < 60) return `${secs}s ago`
  if (secs < 3600) return `${Math.round(secs / 60)}m ago`
  if (secs < 86400) return `${Math.round(secs / 3600)}h ago`
  return `${Math.round(secs / 86400)}d ago`
}

export const MONO = 'font-mono text-xs'
export const NUM = 'text-right tabular-nums'
export const KEY = 'font-medium text-dbb-charcoal'
export const LINK = 'underline decoration-dotted decoration-dbb-muted underline-offset-2 hover:decoration-solid'
export const PRE = 'max-h-[480px] overflow-auto rounded-lg bg-dbb-surface p-3 font-mono text-xs'

const TONES = {
  ok: 'bg-dbb-up/10 text-dbb-up',
  warn: 'bg-amber-50 text-amber-800',
  failed: 'bg-dbb-clay/10 text-dbb-clay',
  neutral: 'bg-dbb-sand text-dbb-charcoal',
}

export type Tone = keyof typeof TONES

export function Pill({ tone = 'neutral', className, children }: { tone?: Tone; className?: string; children: ReactNode }) {
  return (
    <span className={cn('inline-flex items-center whitespace-nowrap rounded-full px-2 py-0.5 text-[11px] font-medium', TONES[tone], className)}>
      {children}
    </span>
  )
}

export function Empty({ children }: { children: ReactNode }) {
  return <p className="py-8 text-center text-sm text-dbb-muted">{children}</p>
}

export function ErrorBanner({ error }: { error: ApiError | null }) {
  if (!error) return null
  return (
    <div role="alert" className="mb-3 rounded-lg border border-dbb-clay/30 bg-dbb-clay/5 px-3 py-2 text-sm text-dbb-clay">
      <span className={MONO}>{error.status || 'network'}</span> {error.detail}
    </div>
  )
}

export function Pager({
  offset,
  count,
  total,
  onPage,
  className,
}: {
  offset: number
  count: number
  total: number
  onPage: (offset: number) => void
  className?: string
}) {
  return (
    <div className={cn('mt-3 flex items-center gap-1 border-t border-dbb-warm/50 pt-2 text-sm text-dbb-muted', className)}>
      <Button variant="ghost" size="sm" className="h-7 px-2" disabled={offset === 0} onClick={() => onPage(Math.max(0, offset - PAGE))}>
        ← Prev
      </Button>
      <span className="px-1 tabular-nums">
        {total === 0 ? '0' : `${num(offset + 1)}–${num(offset + count)}`} / {num(total)}
      </span>
      <Button variant="ghost" size="sm" className="h-7 px-2" disabled={offset + count >= total} onClick={() => onPage(offset + PAGE)}>
        Next →
      </Button>
    </div>
  )
}

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
      <ErrorBanner error={error} />
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
                  <span className={KEY}>{labels.get(r.source) ?? r.source}</span> <span className={MONO}>{r.source}</span>
                </TableCell>
                <TableCell>
                  <Pill tone={r.ok ? 'ok' : 'failed'}>{r.ok ? 'ok' : 'failed'}</Pill>
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
