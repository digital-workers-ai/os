import { useEffect, useState } from 'react'
import { asApiError, get, type ApiError } from '@/api'
import { SectionCard } from '@/components/SectionCard'
import { ErrorBanner } from '@/components/ui/banner'
import { Empty } from '@/components/ui/empty'
import { Loading } from '@/components/ui/loading'
import { Mono } from '@/components/ui/mono'
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

const FILL = 'lg:flex lg:flex-col lg:max-h-[calc(100vh-11.25rem-1px)]'
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

export function Activity() {
  const [data, setData] = useState<ActivityResponse | null>(null)
  const [error, setError] = useState<ApiError | null>(null)

  useEffect(() => {
    get<ActivityResponse>('/api/activity?limit=500')
      .then((r) => {
        setData(r)
        setError(null)
      })
      .catch((e) => setError(asApiError(e)))
  }, [])

  const rows = group(data?.events ?? [])

  return (
    <SectionCard className={FILL} bodyClassName={BODY}>
      <ErrorBanner error={error} className="mb-3" />
      {!data && !error && <Loading />}
      {data && rows.length === 0 && <Empty>no activity yet</Empty>}
      {rows.length > 0 && (
        <Table className="table-fixed" wrapperClassName="overflow-x-visible">
          <TableHeader className={STICKY_HEAD}>
            <TableRow>
              <TableHead className="w-64">Entity ({num(rows.length)})</TableHead>
              <TableHead>Changes</TableHead>
              <TableHead className="w-32">Source</TableHead>
              <TableHead className="w-32">When</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {rows.map((r, i) => (
              <TableRow key={`${r.canonical_id}|${r.source}|${r.observed_at}|${i}`}>
                <TableCell>
                  <span className="block font-medium text-dbb-charcoal">{r.label}</span>
                  <Pill>{r.entity_type}</Pill>
                </TableCell>
                <TableCell>
                  <span className="flex flex-col items-start gap-1">
                    {r.changes.map(([k, v]) => (
                      <Chip key={k}>
                        {k}=<strong>{show(v)}</strong>
                      </Chip>
                    ))}
                  </span>
                </TableCell>
                <TableCell>
                  <Mono>{r.source}</Mono>
                </TableCell>
                <TableCell className="whitespace-nowrap" title={r.observed_at}>
                  {relTime(r.observed_at)}
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      )}
    </SectionCard>
  )
}
