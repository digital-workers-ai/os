import { useEffect, useRef, useState } from 'react'
import { get, type ApiError } from '@/api'
import { Filter } from '@/components/Filter'
import { SectionCard } from '@/components/SectionCard'
import { ErrorBanner } from '@/components/ui/banner'
import { Empty } from '@/components/ui/empty'
import { Loading } from '@/components/ui/loading'
import { Mono } from '@/components/ui/mono'
import { Pager } from '@/components/ui/pager'
import { Chip, Pill } from '@/components/ui/pill'
import { STICKY_HEAD, Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { num } from '@/lib/format'
import { useGet } from '@/lib/useGet'
import { BODY, FULL, useLoad } from './shared'
import type { Vocabulary } from './Vocabulary'

interface Fact {
  canonical_id: string
  entity_type: string
  label: string
  reading: string
  attr: string
  value: string
  quote: string | null
  quote_verified: boolean
}

interface FactsResponse {
  total: number
  unverified_quotes: number
  by_value: Record<string, number>
  facts: Fact[]
}

const PAGE_SIZE = 50
const UNVERIFIED = 'unverified'
const KEY = 'font-medium text-dbb-charcoal'

const sum = (ns: number[]) => ns.reduce((a, b) => a + b, 0)

function Verified({ ok }: { ok: boolean }) {
  return <Pill tone={ok ? 'ok' : 'err'}>{ok ? 'verified' : 'unverified'}</Pill>
}

function Facts({ vocabulary, vocabularyError }: { vocabulary: Vocabulary | null; vocabularyError: ApiError | null }) {
  const [attr, setAttr] = useState('')
  const [value, setValue] = useState('')
  const [unverified, setUnverified] = useState(false)
  const [offset, setOffset] = useState(0)
  const [size, setSize] = useState(PAGE_SIZE)
  const bodyRef = useRef<HTMLDivElement>(null)

  const params = new URLSearchParams({ limit: String(size), offset: String(offset) })
  if (attr) params.set('attr', attr)
  if (value) params.set('value', value)
  if (unverified) params.set('unverified_only', 'true')
  const facts = useGet<FactsResponse>(`/api/enrichment?${params}`)
  const data = facts.data

  const goTo = (n: number) => {
    setOffset(n)
    bodyRef.current?.scrollTo({ top: 0 })
  }
  const changeSize = (n: number) => {
    setSize(n)
    goTo(0)
  }
  const pickAttr = (a: string) => {
    setAttr(a)
    setValue('')
    goTo(0)
  }
  const pickValue = (v: string) => {
    setValue(v)
    goTo(0)
  }
  const pickQuotes = (q: string) => {
    setUnverified(q === UNVERIFIED)
    goTo(0)
  }

  const byValue = data?.by_value ?? {}
  const attrCounts = new Map<string, number>()
  const labelCounts = new Map<string, number>()
  Object.entries(vocabulary?.readings ?? {}).forEach(([name, r]) =>
    r.fields.forEach((f) =>
      f.labels.forEach((g) => {
        const n = byValue[`${name}.${f.name}.${g.label}`] ?? 0
        attrCounts.set(f.name, (attrCounts.get(f.name) ?? 0) + n)
        if (!attr || f.name === attr) labelCounts.set(g.label, (labelCounts.get(g.label) ?? 0) + n)
      }),
    ),
  )
  const total = sum(Object.values(byValue))
  const valuesTotal = attr ? (attrCounts.get(attr) ?? 0) : total

  return (
    <SectionCard
      title={
        <div className="flex items-center gap-2">
          <Filter value={attr} onChange={pickAttr} all={`all facts (${num(total)})`} options={[...attrCounts]} />
          <Filter value={value} onChange={pickValue} all={`all values (${num(valuesTotal)})`} options={[...labelCounts]} />
          <Filter
            value={unverified ? UNVERIFIED : ''}
            onChange={pickQuotes}
            all={`all quotes (${num(total)})`}
            options={[[UNVERIFIED, data?.unverified_quotes ?? 0]]}
          />
        </div>
      }
      className={FULL}
      bodyClassName={BODY}
      bodyRef={bodyRef}
    >
      <ErrorBanner error={vocabularyError} className="mb-3" />
      <ErrorBanner error={facts.error} className="mb-3" />
      {!data && !facts.error && <Loading />}
      {data && data.facts.length === 0 && <Empty>no enriched facts</Empty>}
      {data && data.facts.length > 0 && (
        <>
          <Table className="table-fixed" wrapperClassName="overflow-x-visible">
            <TableHeader className={STICKY_HEAD}>
              <TableRow>
                <TableHead className="w-64">Entity ({num(data.total)})</TableHead>
                <TableHead className="w-28">Type</TableHead>
                <TableHead className="w-32">Fact</TableHead>
                <TableHead className="w-40">Value</TableHead>
                <TableHead className="w-28">Verified</TableHead>
                <TableHead>Quote</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {data.facts.map((f, i) => (
                <TableRow key={i}>
                  <TableCell className={`align-top ${KEY}`}>{f.label}</TableCell>
                  <TableCell className="align-top">
                    <Pill>{f.entity_type}</Pill>
                  </TableCell>
                  <TableCell className="align-top">
                    <Mono>{f.attr}</Mono>
                  </TableCell>
                  <TableCell className="align-top">
                    <Chip>{f.value}</Chip>
                  </TableCell>
                  <TableCell className="align-top">
                    <Verified ok={f.quote_verified} />
                  </TableCell>
                  <TableCell className="align-top">{f.quote}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
          <Pager
            offset={offset}
            count={data.facts.length}
            total={data.total}
            onPage={goTo}
            size={size}
            allSize={Math.min(data.total, 500)}
            onSize={changeSize}
            pageSize={PAGE_SIZE}
          />
        </>
      )}
    </SectionCard>
  )
}

export function Enrichment({ onEnabled }: { onEnabled: (on: boolean) => void }) {
  const vocab = useLoad(() => get<Vocabulary>('/api/enrichment/vocabulary'), [])

  useEffect(() => {
    if (vocab.data) onEnabled(vocab.data.enabled)
  }, [vocab.data, onEnabled])

  return <Facts vocabulary={vocab.data} vocabularyError={vocab.error} />
}
