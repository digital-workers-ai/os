import { useRef, useState } from 'react'
import { asApiError, get, post, type ApiError } from '@/api'
import { SectionCard } from '@/components/SectionCard'
import { Section } from '@/components/SectionHeading'
import { ErrorBanner } from '@/components/ui/banner'
import { Button } from '@/components/ui/button'
import { Empty } from '@/components/ui/empty'
import { Loading } from '@/components/ui/loading'
import { Input } from '@/components/ui/input'
import { Mono } from '@/components/ui/mono'
import { PAGE, Pager } from '@/components/ui/pager'
import { Chip, Pill } from '@/components/ui/pill'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { num, plural, relTime, short } from '@/lib/format'
import { ALL, Enabled, LayerOff, useLoad } from './shared'
import { Readings, type Vocabulary } from './Vocabulary'

interface LastRun {
  at: string
  read: number
  failed: number
  truncated_at_cap: boolean
  model: string
  prompt_version: string
}

interface Coverage {
  reading: string
  vocabulary_sha: string
  eligible: number
  read_under_current_vocabulary: number
  read_under_a_retired_vocabulary: number
  never_read: number
  last_run: LastRun | null
}

interface RunReading {
  eligible: number
  pending: number
  reconciled: number
  read: number
  rows: number
  failed: number
  unverified_quotes: number
  truncated_at_cap: boolean
  errors: string[]
}

interface RunReport {
  readings: Record<string, RunReading>
  calls: number
  rows: number
  failed: number
  unverified_quotes: number
  reconciled: number
  duration_ms: number
  truncated_at_cap?: boolean
}

interface Fact {
  canonical_id: string
  entity_type: string
  reading: string
  attr: string
  value: string
  quote: string | null
  quote_verified: boolean
  model: string
  prompt_version: string
  vocabulary_sha: string
}

interface FactsResponse {
  total: number
  limit: number
  offset: number
  unverified_quotes: number
  by_value: Record<string, number>
  inferred: boolean
  counts: string
  facts: Fact[]
}

interface EntityFact {
  reading: string
  attr: string
  value: string
  quote: string | null
  quote_verified: boolean
  model: string
  prompt_version: string
  vocabulary_sha: string
  input_sha: string
  created_at: string
}

interface EntityReadings {
  canonical_id: string
  inferred: boolean
  facts: EntityFact[]
}

const numCol = 'text-right tabular-nums'

const keyCol = 'font-medium text-dbb-charcoal'

function Verified({ ok }: { ok: boolean }) {
  return <Pill tone={ok ? 'ok' : 'err'}>{ok ? 'verified' : 'unverified'}</Pill>
}

function Quote({ fact }: { fact: { quote: string | null; quote_verified: boolean } }) {
  return (
    <span className="inline-flex flex-wrap items-center gap-1.5">
      <Verified ok={fact.quote_verified} />
      {fact.quote && <span>{fact.quote}</span>}
    </span>
  )
}

function CoverageTable({ rows }: { rows: Coverage[] }) {
  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead>Reading</TableHead>
          <TableHead>Vocabulary</TableHead>
          <TableHead className={numCol}>Eligible</TableHead>
          <TableHead className={numCol}>Read under current vocabulary</TableHead>
          <TableHead className={numCol}>Read under a retired vocabulary</TableHead>
          <TableHead className={numCol}>Never read</TableHead>
          <TableHead>Last run</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {rows.map((r) => (
          <TableRow key={r.reading}>
            <TableCell className={keyCol}>{r.reading}</TableCell>
            <TableCell>
              <Mono>{r.vocabulary_sha}</Mono>
            </TableCell>
            <TableCell className={numCol}>{num(r.eligible)}</TableCell>
            <TableCell className={numCol}>{num(r.read_under_current_vocabulary)}</TableCell>
            <TableCell className={numCol}>{num(r.read_under_a_retired_vocabulary)}</TableCell>
            <TableCell className={numCol}>{num(r.never_read)}</TableCell>
            <TableCell>
              {r.last_run === null ? (
                '—'
              ) : (
                <span className="inline-flex flex-wrap items-center gap-1.5">
                  <span title={r.last_run.at}>{relTime(r.last_run.at)}</span>
                  <span>
                    · {num(r.last_run.read)} read · {num(r.last_run.failed)} failed
                  </span>
                  {r.last_run.truncated_at_cap && <Pill tone="warn">truncated at cap</Pill>}
                  <Mono>
                    {r.last_run.model} {r.last_run.prompt_version}
                  </Mono>
                </span>
              )}
            </TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  )
}

function RunResult({ report }: { report: RunReport }) {
  return (
    <>
      <p className="mb-3 flex flex-wrap items-center gap-2 text-sm text-dbb-muted">
        <span>
          {num(report.calls)} calls · {num(report.rows)} rows · {num(report.failed)} failed · {num(report.unverified_quotes)} unverified
          quotes · {num(report.reconciled)} reconciled · {num(report.duration_ms)} ms
        </span>
        {report.truncated_at_cap && <Pill tone="warn">truncated at cap</Pill>}
      </p>
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Reading</TableHead>
            <TableHead className={numCol}>Eligible</TableHead>
            <TableHead className={numCol}>Pending</TableHead>
            <TableHead className={numCol}>Read</TableHead>
            <TableHead className={numCol}>Rows</TableHead>
            <TableHead className={numCol}>Failed</TableHead>
            <TableHead className={numCol}>Unverified</TableHead>
            <TableHead className={numCol}>Reconciled</TableHead>
            <TableHead>Errors</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {Object.entries(report.readings).map(([name, r]) => (
            <TableRow key={name}>
              <TableCell className={keyCol}>
                <span className="inline-flex items-center gap-1.5">
                  {name}
                  {r.truncated_at_cap && <Pill tone="warn">truncated at cap</Pill>}
                </span>
              </TableCell>
              <TableCell className={numCol}>{num(r.eligible)}</TableCell>
              <TableCell className={numCol}>{num(r.pending)}</TableCell>
              <TableCell className={numCol}>{num(r.read)}</TableCell>
              <TableCell className={numCol}>{num(r.rows)}</TableCell>
              <TableCell className={numCol}>{num(r.failed)}</TableCell>
              <TableCell className={numCol}>{num(r.unverified_quotes)}</TableCell>
              <TableCell className={numCol}>{num(r.reconciled)}</TableCell>
              <TableCell>{r.errors.length ? r.errors.join('; ') : '—'}</TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </>
  )
}

function Facts({ vocabulary, onPick }: { vocabulary: Vocabulary | null; onPick: (id: string) => void }) {
  const [attr, setAttr] = useState('')
  const [value, setValue] = useState('')
  const [unverified, setUnverified] = useState(false)
  const [offset, setOffset] = useState(0)
  const [size, setSize] = useState(PAGE)

  const params = new URLSearchParams({ limit: String(size), offset: String(offset) })
  if (attr) params.set('attr', attr)
  if (value) params.set('value', value)
  if (unverified) params.set('unverified_only', 'true')
  const query = params.toString()
  const facts = useLoad(() => get<FactsResponse>(`/api/enrichment?${query}`), [query])

  const fields = Object.values(vocabulary?.readings ?? {}).flatMap((r) => r.fields)
  const attrs = [...new Set(fields.map((f) => f.name))]
  const labels = [...new Set(fields.filter((f) => !attr || f.name === attr).flatMap((f) => f.labels.map((g) => g.label)))]
  const data = facts.data
  const byValue = Object.entries(data?.by_value ?? {})
  const changeSize = (n: number) => {
    setSize(n)
    setOffset(0)
  }

  return (
    <SectionCard
      title={`Enriched facts${data ? ` (${num(data.total)})` : ''}`}
      description={
        data && (
          <span className="inline-flex flex-wrap items-center gap-2">
            <Pill tone="warn">inferred</Pill>
            <span>{data.counts}</span>
          </span>
        )
      }
    >
      <div className="mb-3 flex flex-wrap items-center gap-2">
        <Select
          value={attr || ALL}
          onValueChange={(v) => {
            setAttr(v === ALL ? '' : v)
            setValue('')
            setOffset(0)
          }}
        >
          <SelectTrigger className="h-8 w-44">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value={ALL}>any attr</SelectItem>
            {attrs.map((a) => (
              <SelectItem key={a} value={a}>
                {a}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
        <Select
          value={value || ALL}
          onValueChange={(v) => {
            setValue(v === ALL ? '' : v)
            setOffset(0)
          }}
        >
          <SelectTrigger className="h-8 w-44">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value={ALL}>any value</SelectItem>
            {labels.map((l) => (
              <SelectItem key={l} value={l}>
                {l}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
        <label className="inline-flex items-center gap-1.5 text-sm text-dbb-muted">
          <input
            type="checkbox"
            className="accent-dbb-charcoal"
            checked={unverified}
            onChange={(e) => {
              setUnverified(e.target.checked)
              setOffset(0)
            }}
          />
          unverified quotes only
        </label>
      </div>
      <ErrorBanner error={facts.error} className="mb-3" />
      {data && (
        <p className="mb-3 flex flex-wrap items-center gap-1.5 text-sm text-dbb-muted">
          <span>
            {num(data.total)} facts · {num(data.unverified_quotes)} unverified quotes
          </span>
          {byValue.map(([k, v]) => (
            <Chip key={k}>
              {k} <strong>{num(v)}</strong>
            </Chip>
          ))}
        </p>
      )}
      {facts.loading && <Loading />}
      {data && data.facts.length === 0 && <Empty>no enriched facts match</Empty>}
      {data && data.facts.length > 0 && (
        <Table className="table-fixed">
          <TableHeader>
            <TableRow>
              <TableHead className="w-32">Entity</TableHead>
              <TableHead className="w-32">Reading</TableHead>
              <TableHead className="w-32">Attr</TableHead>
              <TableHead className="w-32">Value</TableHead>
              <TableHead className="w-64">Quote</TableHead>
              <TableHead className="w-40">Model</TableHead>
              <TableHead className="w-40">Vocabulary</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {data.facts.map((f, i) => (
              <TableRow key={i}>
                <TableCell>
                  <Button variant="link" size="sm" className="h-auto p-0 font-mono text-xs" onClick={() => onPick(f.canonical_id)}>
                    {short(f.canonical_id)}
                  </Button>{' '}
                  {f.entity_type}
                </TableCell>
                <TableCell className={keyCol}>{f.reading}</TableCell>
                <TableCell>
                  <Mono>{f.attr}</Mono>
                </TableCell>
                <TableCell>
                  <Mono>{f.value}</Mono>
                </TableCell>
                <TableCell>
                  <Quote fact={f} />
                </TableCell>
                <TableCell>
                  {f.model} {f.prompt_version}
                </TableCell>
                <TableCell>
                  <Mono>{f.vocabulary_sha}</Mono>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      )}
      {data && (
        <Pager
          offset={offset}
          count={data.facts.length}
          total={data.total}
          onPage={setOffset}
          size={size}
          allSize={Math.min(data.total, 500)}
          onSize={changeSize}
        />
      )}
    </SectionCard>
  )
}

function EntityFacts({ id }: { id: string }) {
  const entity = useLoad(() => get<EntityReadings>(`/api/enrichment/${encodeURIComponent(id)}`), [id])
  const rows = entity.data?.facts ?? []
  return (
    <>
      <ErrorBanner error={entity.error} className="mb-3" />
      {entity.data && (
        <p className="mb-3 flex flex-wrap items-center gap-2 text-sm text-dbb-muted">
          <Pill tone="warn">inferred</Pill>
          <span>
            readings for <Mono>{entity.data.canonical_id}</Mono>
          </span>
        </p>
      )}
      {entity.loading && <Loading />}
      {entity.data && rows.length === 0 && <Empty>no readings stored for this entity</Empty>}
      {rows.length > 0 && (
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Reading</TableHead>
              <TableHead>Attr</TableHead>
              <TableHead>Value</TableHead>
              <TableHead>Quote</TableHead>
              <TableHead>Model</TableHead>
              <TableHead>Vocabulary</TableHead>
              <TableHead>Input</TableHead>
              <TableHead>Read</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {rows.map((f, i) => (
              <TableRow key={i}>
                <TableCell className={keyCol}>{f.reading}</TableCell>
                <TableCell>
                  <Mono>{f.attr}</Mono>
                </TableCell>
                <TableCell>
                  <Mono>{f.value}</Mono>
                </TableCell>
                <TableCell>
                  <Quote fact={f} />
                </TableCell>
                <TableCell>
                  {f.model} {f.prompt_version}
                </TableCell>
                <TableCell>
                  <Mono>{f.vocabulary_sha}</Mono>
                </TableCell>
                <TableCell>
                  <Mono>{f.input_sha}</Mono>
                </TableCell>
                <TableCell title={f.created_at}>{relTime(f.created_at)}</TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      )}
    </>
  )
}

export function Enrichment() {
  const vocab = useLoad(() => get<Vocabulary>('/api/enrichment/vocabulary'), [])
  const coverage = useLoad(() => get<{ readings: Coverage[] }>('/api/enrichment/coverage'), [])
  const [reading, setReading] = useState('')
  const [force, setForce] = useState(false)
  const [limit, setLimit] = useState('')
  const [running, setRunning] = useState(false)
  const [report, setReport] = useState<RunReport | null>(null)
  const [runError, setRunError] = useState<ApiError | null>(null)
  const [entityInput, setEntityInput] = useState('')
  const [entityId, setEntityId] = useState('')
  const entityCard = useRef<HTMLDivElement>(null)

  const run = async () => {
    setRunning(true)
    setRunError(null)
    setReport(null)
    const params = new URLSearchParams()
    if (reading) params.set('reading', reading)
    if (force) params.set('force', 'true')
    if (limit) params.set('limit', limit)
    try {
      setReport(await post<RunReport>(`/api/enrichment/run?${params}`))
    } catch (e) {
      setRunError(asApiError(e))
    } finally {
      setRunning(false)
      coverage.reload()
    }
  }

  const pick = (id: string) => {
    setEntityInput(id)
    setEntityId(id)
    entityCard.current?.scrollIntoView({ behavior: 'smooth', block: 'start' })
  }

  const readings = Object.keys(vocab.data?.readings ?? {})

  return (
    <div className="space-y-6">
      <SectionCard
        title="Enrichment"
        description={
          vocab.data && (
            <span className="inline-flex flex-wrap items-center gap-x-2 gap-y-1">
              <Enabled on={vocab.data.enabled} />
              <span>
                model <Mono>{vocab.data.model}</Mono>
              </span>
              {!vocab.data.enabled && <span>· the one layer that calls a model; nothing is read until it is switched on</span>}
            </span>
          )
        }
        headerRight={
          <form
            className="flex flex-wrap items-center gap-2"
            onSubmit={(e) => {
              e.preventDefault()
              run()
            }}
          >
            <Select value={reading || ALL} onValueChange={(v) => setReading(v === ALL ? '' : v)}>
              <SelectTrigger className="h-8 w-40">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value={ALL}>all readings</SelectItem>
                {readings.map((r) => (
                  <SelectItem key={r} value={r}>
                    {r}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            <label className="inline-flex items-center gap-1.5 text-sm text-dbb-muted">
              <input type="checkbox" className="accent-dbb-charcoal" checked={force} onChange={(e) => setForce(e.target.checked)} />
              force
            </label>
            <Input
              type="number"
              min={1}
              max={1000}
              placeholder="limit"
              className="h-8 w-20"
              value={limit}
              onChange={(e) => setLimit(e.target.value)}
            />
            <Button size="sm" type="submit" disabled={running}>
              {running ? 'running…' : 'Run'}
            </Button>
          </form>
        }
      >
        <ErrorBanner error={vocab.error} className="mb-3" />
        <LayerOff error={runError} />
        {report && (
          <Section title="Last run">
            <RunResult report={report} />
          </Section>
        )}
        <Section title="Coverage">
          <p className="mb-3 text-sm text-dbb-muted">
            Four separate claims per reading, not one number: eligible entities carry input text; read under the current vocabulary;
            read under a retired vocabulary; never read at all.
          </p>
          <ErrorBanner error={coverage.error} className="mb-3" />
          {coverage.loading && <Loading />}
          {coverage.data && <CoverageTable rows={coverage.data.readings} />}
        </Section>
      </SectionCard>

      <SectionCard title="Vocabulary" description={vocab.data && plural(readings.length, 'reading')}>
        {vocab.data ? <Readings vocabulary={vocab.data} /> : <Loading />}
      </SectionCard>

      <Facts vocabulary={vocab.data} onPick={pick} />

      <div ref={entityCard} className="scroll-mt-6">
        <SectionCard title="One entity" description="every reading stored for a single canonical id">
          <form
            className="mb-3 flex items-center gap-2"
            onSubmit={(e) => {
              e.preventDefault()
              setEntityId(entityInput.trim())
            }}
          >
            <Input
              placeholder="canonical id"
              className="h-8 max-w-md font-mono text-xs"
              value={entityInput}
              onChange={(e) => setEntityInput(e.target.value)}
            />
            <Button size="sm" type="submit" disabled={!entityInput.trim()}>
              Load
            </Button>
          </form>
          {entityId ? <EntityFacts id={entityId} /> : <Empty>paste a canonical id, or pick one from the facts table</Empty>}
        </SectionCard>
      </div>
    </div>
  )
}
