import { useEffect, useRef, useState } from 'react'
import { get } from '@/api'
import { Filter } from '@/components/Filter'
import { SectionCard } from '@/components/SectionCard'
import { Section } from '@/components/SectionHeading'
import { ErrorBanner } from '@/components/ui/banner'
import { Empty } from '@/components/ui/empty'
import { Loading } from '@/components/ui/loading'
import { Mono } from '@/components/ui/mono'
import { Pager } from '@/components/ui/pager'
import { Chip, Pill } from '@/components/ui/pill'
import { STICKY_HEAD, Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { num, relTime } from '@/lib/format'
import { useGet } from '@/lib/useGet'
import { BODY, FILL, FULL, useLoad } from './shared'
import type { Reading, Vocabulary } from './Vocabulary'

interface LastRun {
  at: string
  read: number
  failed: number
  truncated_at_cap: boolean
}

interface Coverage {
  reading: string
  eligible: number
  read_under_current_vocabulary: number
  read_under_a_retired_vocabulary: number
  never_read: number
  last_run: LastRun | null
}

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

interface EntityFact {
  attr: string
  value: string
  quote: string | null
  quote_verified: boolean
  created_at: string
}

interface EntityReadings {
  facts: EntityFact[]
}

interface Selected {
  canonical_id: string
  label: string
}

const PAGE_SIZE = 50
const UNVERIFIED = 'unverified'
const NUM = 'text-right tabular-nums'
const KEY = 'font-medium text-dbb-charcoal'
const SPLIT = 'grid items-start gap-6 lg:grid-cols-[0.65fr_0.35fr] lg:grid-rows-[minmax(0,1fr)] lg:min-h-0 lg:flex-1'

const sum = (ns: number[]) => ns.reduce((a, b) => a + b, 0)

function Quote({ fact }: { fact: { quote: string | null; quote_verified: boolean } }) {
  return (
    <span className="inline-flex flex-wrap items-center gap-1.5">
      <Pill tone={fact.quote_verified ? 'ok' : 'err'}>{fact.quote_verified ? 'verified' : 'unverified'}</Pill>
      {fact.quote && <span>{fact.quote}</span>}
    </span>
  )
}

function CoverageTable({ rows, readings }: { rows: Coverage[]; readings: Record<string, Reading> }) {
  return (
    <Table className="table-fixed">
      <TableHeader>
        <TableRow>
          <TableHead className="w-56">Reading ({num(rows.length)})</TableHead>
          <TableHead className="w-28">Entity</TableHead>
          <TableHead className={`w-24 ${NUM}`}>Eligible</TableHead>
          <TableHead className={`w-24 ${NUM}`}>Read</TableHead>
          <TableHead className={`w-24 ${NUM}`}>Retired</TableHead>
          <TableHead className={`w-24 ${NUM}`}>Never read</TableHead>
          <TableHead>Last run</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {rows.map((r) => {
          const reading = readings[r.reading]
          return (
            <TableRow key={r.reading}>
              <TableCell className="align-top">
                <span className={`block ${KEY}`}>{r.reading}</span>
                <Mono className="block">
                  {reading.entity}.{reading.input}
                </Mono>
              </TableCell>
              <TableCell className="align-top">
                <Pill>{reading.entity}</Pill>
              </TableCell>
              <TableCell className={`align-top ${NUM}`}>{num(r.eligible)}</TableCell>
              <TableCell className={`align-top ${NUM}`}>{num(r.read_under_current_vocabulary)}</TableCell>
              <TableCell className={`align-top ${NUM}`}>{num(r.read_under_a_retired_vocabulary)}</TableCell>
              <TableCell className={`align-top ${NUM}`}>{num(r.never_read)}</TableCell>
              <TableCell className="align-top">
                {r.last_run === null ? (
                  '—'
                ) : (
                  <span className="inline-flex flex-wrap items-center gap-1.5">
                    <span title={r.last_run.at}>{relTime(r.last_run.at)}</span>
                    <span>
                      · {num(r.last_run.read)} read · {num(r.last_run.failed)} failed
                    </span>
                    {r.last_run.truncated_at_cap && <Pill tone="warn">truncated at cap</Pill>}
                  </span>
                )}
              </TableCell>
            </TableRow>
          )
        })}
      </TableBody>
    </Table>
  )
}

function Facts({
  vocabulary,
  selected,
  onSelect,
}: {
  vocabulary: Vocabulary | null
  selected: Selected | null
  onSelect: (s: Selected) => void
}) {
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
      <ErrorBanner error={facts.error} className="mb-3" />
      {!data && !facts.error && <Loading />}
      {data && data.facts.length === 0 && <Empty>no enriched facts</Empty>}
      {data && data.facts.length > 0 && (
        <>
          <Table className="table-fixed" wrapperClassName="overflow-x-visible">
            <TableHeader className={STICKY_HEAD}>
              <TableRow>
                <TableHead className="w-44">Entity ({num(data.total)})</TableHead>
                <TableHead className="w-24">Type</TableHead>
                <TableHead className="w-28">Fact</TableHead>
                <TableHead className="w-36">Value</TableHead>
                <TableHead>Quote</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {data.facts.map((f, i) => (
                <TableRow
                  key={i}
                  className="cursor-pointer"
                  data-state={f.canonical_id === selected?.canonical_id ? 'selected' : undefined}
                  aria-selected={f.canonical_id === selected?.canonical_id}
                  onClick={() => onSelect({ canonical_id: f.canonical_id, label: f.label })}
                >
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
                    <Quote fact={f} />
                  </TableCell>
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

function EntityDetail({ selected }: { selected: Selected }) {
  const entity = useGet<EntityReadings>(`/api/enrichment/${encodeURIComponent(selected.canonical_id)}`)
  const rows = entity.data?.facts ?? []
  return (
    <SectionCard title={selected.label} className={FILL} bodyClassName={BODY}>
      <ErrorBanner error={entity.error} className="mb-3" />
      {!entity.data && !entity.error && <Loading />}
      {entity.data && rows.length === 0 && <Empty>no readings stored for this entity</Empty>}
      {rows.length > 0 && (
        <>
          <Table className="table-fixed">
            <TableHeader>
              <TableRow>
                <TableHead>Fact ({num(rows.length)})</TableHead>
                <TableHead className="w-36">Value</TableHead>
                <TableHead className="w-20">When</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {rows.map((f, i) => (
                <TableRow key={i}>
                  <TableCell className="align-top">
                    <Mono className="block">{f.attr}</Mono>
                    <span className="mt-1 block">
                      <Quote fact={f} />
                    </span>
                  </TableCell>
                  <TableCell className="align-top">
                    <Chip>{f.value}</Chip>
                  </TableCell>
                  <TableCell className="whitespace-nowrap align-top" title={f.created_at}>
                    {relTime(f.created_at)}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
          <Section title="Receipts">
            <p className="mb-3 text-sm text-dbb-muted">
              How each fact was produced: which model and prompt read it, under which vocabulary, and from which input.
            </p>
            <pre className="overflow-auto rounded-lg bg-dbb-surface p-3 font-mono text-xs">{JSON.stringify(entity.data, null, 2)}</pre>
          </Section>
        </>
      )}
    </SectionCard>
  )
}

export function Enrichment({ onEnabled }: { onEnabled: (on: boolean) => void }) {
  const vocab = useLoad(() => get<Vocabulary>('/api/enrichment/vocabulary'), [])
  const coverage = useLoad(() => get<{ readings: Coverage[] }>('/api/enrichment/coverage'), [])
  const [selected, setSelected] = useState<Selected | null>(null)

  useEffect(() => {
    if (vocab.data) onEnabled(vocab.data.enabled)
  }, [vocab.data, onEnabled])

  return (
    <div className="flex flex-col gap-6 lg:h-full">
      <SectionCard title="Readings" className="shrink-0">
        <ErrorBanner error={vocab.error} className="mb-3" />
        <ErrorBanner error={coverage.error} className="mb-3" />
        {vocab.data && coverage.data && <CoverageTable rows={coverage.data.readings} readings={vocab.data.readings} />}
        {(vocab.loading || coverage.loading) && <Loading />}
      </SectionCard>
      <div className={SPLIT}>
        <Facts vocabulary={vocab.data} selected={selected} onSelect={setSelected} />
        {selected ? (
          <EntityDetail selected={selected} />
        ) : (
          <SectionCard className={FILL} bodyClassName={BODY}>
            <Empty>select an entity</Empty>
          </SectionCard>
        )}
      </div>
    </div>
  )
}
