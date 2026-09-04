import { useEffect, useRef, useState } from 'react'
import { asApiError, get, type ApiError } from '@/api'
import { Filter } from '@/components/Filter'
import { SectionCard } from '@/components/SectionCard'
import { ErrorBanner } from '@/components/ui/banner'
import { Empty } from '@/components/ui/empty'
import { Loading } from '@/components/ui/loading'
import { Mono } from '@/components/ui/mono'
import { Pager } from '@/components/ui/pager'
import { Chip, Pill } from '@/components/ui/pill'
import { STICKY_HEAD, Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { num, relTime } from '@/lib/format'

interface Event {
  observed_at: string
  canonical_id: string
  entity_type: string
  label: string
  source: string
  attr: string
  value: unknown
}

interface ActivityResponse {
  events: Event[]
}

interface Row {
  observed_at: string
  canonical_id: string
  entity_type: string
  label: string
  source: string
  changes: [string, unknown][]
}

const PAGE_SIZE = 50
const FILL = 'lg:flex lg:flex-col lg:h-[calc(100vh-11.25rem-1px)]'
const BODY = 'lg:min-h-0 lg:overflow-y-auto lg:-mx-6 lg:px-6 lg:-mb-6 lg:pb-6 lg:rounded-b-xl'

const show = (v: unknown) =>
  v === null || v === undefined ? '—' : typeof v === 'object' ? JSON.stringify(v) : String(v)

const group = (events: Event[]) =>
  events.reduce<Row[]>((rows, e) => {
    const last = rows[rows.length - 1]
    if (last && last.canonical_id === e.canonical_id && last.source === e.source && last.observed_at === e.observed_at) {
      last.changes.push([e.attr, e.value])
    } else {
      const { attr, value, ...rest } = e
      rows.push({ ...rest, changes: [[attr, value]] })
    }
    return rows
  }, [])

const countBy = (rows: Row[], key: 'entity_type' | 'source') =>
  [...rows.reduce((m, r) => m.set(r[key], (m.get(r[key]) ?? 0) + 1), new Map<string, number>())].sort(([a], [b]) => a.localeCompare(b))

export function Activity() {
  const [data, setData] = useState<ActivityResponse | null>(null)
  const [error, setError] = useState<ApiError | null>(null)
  const [type, setType] = useState('')
  const [source, setSource] = useState('')
  const [offset, setOffset] = useState(0)
  const [size, setSize] = useState(PAGE_SIZE)
  const bodyRef = useRef<HTMLDivElement>(null)
  const goTo = (n: number) => {
    setOffset(n)
    bodyRef.current?.scrollTo({ top: 0 })
  }
  const changeSize = (n: number) => {
    setSize(n)
    goTo(0)
  }
  const filter = (set: (v: string) => void) => (v: string) => {
    set(v)
    goTo(0)
  }

  useEffect(() => {
    get<ActivityResponse>('/api/activity?limit=500')
      .then((r) => {
        setData(r)
        setError(null)
      })
      .catch((e) => setError(asApiError(e)))
  }, [])

  const all = group(data?.events ?? [])
  const rows = all.filter((r) => (!type || r.entity_type === type) && (!source || r.source === source))
  const page = rows.slice(offset, offset + size)

  return (
    <SectionCard
      title={
        <div className="flex items-center gap-2">
          <Filter
            value={type}
            onChange={filter(setType)}
            all={`all types (${num(all.length)})`}
            options={countBy(all, 'entity_type')}
            testId="activity-type-filter"
          />
          <Filter
            value={source}
            onChange={filter(setSource)}
            all={`all sources (${num(all.length)})`}
            options={countBy(all, 'source')}
            testId="activity-source-filter"
          />
        </div>
      }
      className={FILL}
      bodyClassName={BODY}
      bodyRef={bodyRef}
      testId="activity"
    >
      <ErrorBanner error={error} className="mb-3" />
      {!data && !error && <Loading />}
      {data && rows.length === 0 && <Empty>no activity yet</Empty>}
      {rows.length > 0 && (
        <Table className="table-fixed" wrapperClassName="overflow-x-visible" data-testid="activity-table">
          <TableHeader className={STICKY_HEAD}>
            <TableRow>
              <TableHead className="w-64">Entity ({num(rows.length)})</TableHead>
              <TableHead className="w-36">Type</TableHead>
              <TableHead>Changes</TableHead>
              <TableHead className="w-32">Source</TableHead>
              <TableHead className="w-32">When</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {page.map((r, i) => (
              <TableRow key={`${r.canonical_id}|${r.source}|${r.observed_at}|${i}`}>
                <TableCell className="align-top font-medium text-dbb-charcoal">{r.label}</TableCell>
                <TableCell className="align-top">
                  <Pill>{r.entity_type}</Pill>
                </TableCell>
                <TableCell className="align-top">
                  <span className="flex flex-col items-start gap-1">
                    {r.changes.map(([k, v]) => (
                      <Chip key={k}>
                        {k}=<strong>{show(v)}</strong>
                      </Chip>
                    ))}
                  </span>
                </TableCell>
                <TableCell className="align-top">
                  <Mono>{r.source}</Mono>
                </TableCell>
                <TableCell className="whitespace-nowrap align-top" title={r.observed_at}>
                  {relTime(r.observed_at)}
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      )}
      {rows.length > 0 && (
        <Pager
          offset={offset}
          count={page.length}
          total={rows.length}
          onPage={goTo}
          size={size}
          allSize={rows.length}
          onSize={changeSize}
          pageSize={PAGE_SIZE}
        />
      )}
    </SectionCard>
  )
}
