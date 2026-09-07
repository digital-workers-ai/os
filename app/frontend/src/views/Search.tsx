import { useEffect, useRef, useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import type { SearchResponse } from '@/api'
import { Filter } from '@/components/Filter'
import { SectionCard } from '@/components/SectionCard'
import { Empty } from '@/components/ui/empty'
import { Loading } from '@/components/ui/loading'
import { Pager } from '@/components/ui/pager'
import { Chip, FilterChip, Pill } from '@/components/ui/pill'
import { STICKY_HEAD, Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { anchorText, num } from '@/lib/format'
import { hrefFor } from '@/lib/hrefFor'
import { useGet } from '@/lib/useGet'
import { BODY, FULL, LayerOff, PAGE_FILL } from './inference/shared'

const PAGE_SIZE = 50
const DEBOUNCE_MS = 250
const MODES = ['words', 'meaning', 'both'] as const

const name = (label: string) => (label.includes('|') ? anchorText(label) : label)

function Evidence({ text }: { text: string }) {
  if (text.includes('«')) {
    return (
      <span className="text-dbb-muted">
        {text.split(/«([^»]*)»/).map((part, i) =>
          i % 2 ? (
            <mark key={i} className="bg-transparent font-medium text-dbb-charcoal">
              {part}
            </mark>
          ) : (
            part
          ),
        )}
      </span>
    )
  }
  const at = text.indexOf('=')
  const attr = text.slice(0, at)
  const value = text.slice(at + 1)
  return (
    <Chip>
      {at < 0 ? text : `${attr}=`}
      {at >= 0 && <strong>{attr === 'anchor' ? anchorText(value) : value}</strong>}
    </Chip>
  )
}

export function Search() {
  const [params, setParams] = useSearchParams()
  const navigate = useNavigate()
  const q = params.get('q') ?? ''
  const kind = params.get('kind') ?? ''
  const mode = params.get('mode') ?? 'words'
  const offset = Number(params.get('offset')) || 0
  const [text, setText] = useState(q)
  const [size, setSize] = useState(PAGE_SIZE)
  const bodyRef = useRef<HTMLDivElement>(null)

  const write = (patch: Record<string, string>, replace: boolean) =>
    setParams(
      (prev) => {
        const next = new URLSearchParams(prev)
        Object.entries(patch).forEach(([k, v]) => (v ? next.set(k, v) : next.delete(k)))
        return next
      },
      { replace },
    )

  useEffect(() => setText(q), [q])
  useEffect(() => {
    if (text === q) return
    const timer = setTimeout(() => write({ q: text, offset: '' }, true), DEBOUNCE_MS)
    return () => clearTimeout(timer)
  }, [text, q, setParams])

  const search = useGet<SearchResponse>(
    q ? `/api/search?${new URLSearchParams({ q, ...(kind && { kind }), mode, limit: String(size), offset: String(offset) })}` : null,
  )
  const data = search.data
  const results = data?.results ?? []
  const byKind = Object.entries(data?.by_kind ?? {}).sort(([, a], [, b]) => b - a)
  const across = byKind.reduce((n, [, c]) => n + c, 0)

  const goTo = (n: number) => {
    write({ offset: n ? String(n) : '' }, false)
    bodyRef.current?.scrollTo({ top: 0 })
  }
  const changeSize = (n: number) => {
    setSize(n)
    goTo(0)
  }

  return (
    <div className={PAGE_FILL}>
      <SectionCard
        title={`Results (${num(data?.total ?? 0)})`}
        headerRight={
          <div className="flex items-center gap-2">
            <input
              className="h-6 w-72 rounded-md border border-dbb-warm bg-white px-2 text-sm"
              placeholder="Search everything…"
              autoFocus
              value={text}
              onChange={(e) => setText(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && write({ q: text, offset: '' }, false)}
              data-testid="search-box"
            />
            <Filter
              value={kind}
              onChange={(k) => write({ kind: k, offset: '' }, false)}
              all={`all kinds (${num(across)})`}
              options={byKind}
              testId="search-kind-filter"
            />
            {data?.meaning_enabled &&
              MODES.map((m) => (
                <FilterChip
                  key={m}
                  on={mode === m}
                  onClick={() => write({ mode: m === 'words' ? '' : m, offset: '' }, false)}
                  data-testid={`search-mode-${m}`}
                >
                  {m}
                </FilterChip>
              ))}
          </div>
        }
        className={FULL}
        bodyClassName={BODY}
        bodyRef={bodyRef}
        testId="search"
      >
        <LayerOff error={search.error} />
        {!q ? (
          <Empty>type to search everything stored · ⌘K opens search from any page</Empty>
        ) : search.error ? null : !data ? (
          <Loading />
        ) : results.length === 0 ? (
          <Empty>no matches</Empty>
        ) : (
          <>
            <Table className="table-fixed" wrapperClassName="overflow-x-visible" data-testid="search-table">
              <TableHeader className={STICKY_HEAD}>
                <TableRow>
                  <TableHead hint="What sort of thing this is" className="w-32">Kind</TableHead>
                  <TableHead hint="How the thing is labelled" className="w-72">Name</TableHead>
                  <TableHead hint="The words that matched, in context">Evidence</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {results.map((hit) => (
                  <TableRow
                    key={`${hit.kind}|${hit.id}`}
                    className="cursor-pointer"
                    data-testid="search-row"
                    data-kind={hit.kind}
                    data-id={hit.id}
                    onClick={() => navigate(hrefFor(hit.kind, hit.id))}
                  >
                    <TableCell className="align-top">
                      <Pill>{hit.kind}</Pill>
                    </TableCell>
                    <TableCell className="align-top font-medium text-dbb-charcoal">{name(hit.label)}</TableCell>
                    <TableCell className="align-top">
                      <Evidence text={hit.evidence} />
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
            <div data-testid="search-pager">
              <Pager
                offset={offset}
                count={results.length}
                total={data.total}
                onPage={goTo}
                size={size}
                allSize={Math.min(data.total, 500)}
                onSize={changeSize}
                pageSize={PAGE_SIZE}
              />
            </div>
          </>
        )}
      </SectionCard>
    </div>
  )
}
