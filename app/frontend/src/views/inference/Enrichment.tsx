import { useState } from 'react'
import { asApiError, get, post, type ApiError } from '../../api'
import { SectionCard } from '@/components/SectionCard'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { ALL, Chip, Empty, Enabled, Fail, LayerOff, Mono, Pill, num, relTime, short, useLoad } from './shared'

interface Gloss {
  label: string
  means: string
}

interface Field {
  name: string
  type: string
  description: string
  labels: Gloss[]
}

interface Reading {
  entity: string
  input: string
  description: string
  sha: string
  fields: Field[]
}

interface Vocabulary {
  enabled: boolean
  model: string
  readings: Record<string, Reading>
}

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

const PAGE = 50

const numCol = 'text-right tabular-nums'

const keyCol = 'font-medium text-dbb-charcoal'

const keep = 'data-[state=inactive]:hidden'

function Verified({ ok }: { ok: boolean }) {
  return <Pill tone={ok ? 'up' : 'err'}>{ok ? 'verified' : 'unverified'}</Pill>
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
    <div className="space-y-3 rounded-lg border border-dbb-warm p-3">
      <div className="flex flex-wrap items-center gap-2 text-sm text-dbb-muted">
        <span>
          {num(report.calls)} calls · {num(report.rows)} rows · {num(report.failed)} failed · {num(report.unverified_quotes)} unverified
          quotes · {num(report.reconciled)} reconciled · {num(report.duration_ms)} ms
        </span>
        {report.truncated_at_cap && <Pill tone="warn">truncated at cap</Pill>}
      </div>
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
    </div>
  )
}

function VocabularyTab({ vocabulary }: { vocabulary: Vocabulary }) {
  return (
    <div className="space-y-6">
      {Object.entries(vocabulary.readings).map(([name, r]) => (
        <div key={name} className="space-y-2">
          <div className="flex flex-wrap items-center gap-x-2 gap-y-1 text-sm text-dbb-muted">
            <span className="font-medium text-dbb-charcoal">{name}</span>
            <span>
              reads{' '}
              <Mono>
                {r.entity}.{r.input}
              </Mono>
            </span>
            <span>
              sha <Mono title={r.sha}>{short(r.sha)}</Mono>
            </span>
            <span>· {r.fields.length} fields</span>
          </div>
          <p className="text-sm text-dbb-muted">{r.description}</p>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Field</TableHead>
                <TableHead>Type</TableHead>
                <TableHead>Description</TableHead>
                <TableHead>Labels</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {r.fields.map((f) => (
                <TableRow key={f.name}>
                  <TableCell className="align-top font-mono text-xs text-dbb-charcoal">{f.name}</TableCell>
                  <TableCell className="align-top">
                    <Pill>{f.type}</Pill>
                  </TableCell>
                  <TableCell className="max-w-md align-top">{f.description}</TableCell>
                  <TableCell className="align-top">
                    <dl className="space-y-1">
                      {f.labels.map((g) => (
                        <div key={g.label} className="flex gap-3">
                          <dt className="w-44 shrink-0 font-mono text-xs text-dbb-charcoal">{g.label}</dt>
                          <dd>{g.means}</dd>
                        </div>
                      ))}
                    </dl>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      ))}
    </div>
  )
}

function FactsTab({ vocabulary, onPick }: { vocabulary: Vocabulary | null; onPick: (id: string) => void }) {
  const [attr, setAttr] = useState('')
  const [value, setValue] = useState('')
  const [unverified, setUnverified] = useState(false)
  const [offset, setOffset] = useState(0)

  const params = new URLSearchParams({ limit: String(PAGE), offset: String(offset) })
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

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center gap-2">
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
      <Fail error={facts.error} />
      {data && (
        <>
          <div className="flex flex-wrap items-center gap-2 text-sm text-dbb-muted">
            <Pill tone="warn">inferred</Pill>
            <span>{data.counts}</span>
          </div>
          <p className="text-sm text-dbb-muted">
            {num(data.total)} facts · {num(data.unverified_quotes)} unverified quotes · showing {num(data.offset)}–
            {num(Math.min(data.offset + data.facts.length, data.total))}
          </p>
          {byValue.length > 0 && (
            <div className="flex flex-wrap gap-1.5">
              {byValue.map(([k, v]) => (
                <Chip key={k}>
                  {k} <strong>{num(v)}</strong>
                </Chip>
              ))}
            </div>
          )}
        </>
      )}
      {facts.loading && <Empty>loading…</Empty>}
      {data && data.facts.length === 0 && <Empty>no enriched facts match</Empty>}
      {data && data.facts.length > 0 && (
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Entity</TableHead>
              <TableHead>Reading</TableHead>
              <TableHead>Attr</TableHead>
              <TableHead>Value</TableHead>
              <TableHead>Quote</TableHead>
              <TableHead>Model</TableHead>
              <TableHead>Vocabulary</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {data.facts.map((f, i) => (
              <TableRow key={i}>
                <TableCell>
                  <Button variant="link" size="sm" className="h-auto p-0 font-mono text-xs" onClick={() => onPick(f.canonical_id)}>
                    {f.canonical_id.slice(0, 8)}
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
      <div className="flex items-center justify-end gap-2">
        <Button variant="outline" size="sm" disabled={offset === 0} onClick={() => setOffset(Math.max(0, offset - PAGE))}>
          prev
        </Button>
        <Button variant="outline" size="sm" disabled={!data || offset + PAGE >= data.total} onClick={() => setOffset(offset + PAGE)}>
          next
        </Button>
      </div>
    </div>
  )
}

function EntityFacts({ id }: { id: string }) {
  const entity = useLoad(() => get<EntityReadings>(`/api/enrichment/${encodeURIComponent(id)}`), [id])
  const rows = entity.data?.facts ?? []
  return (
    <div className="space-y-3">
      <Fail error={entity.error} />
      {entity.data && (
        <div className="flex flex-wrap items-center gap-2 text-sm text-dbb-muted">
          <Pill tone="warn">inferred</Pill>
          <span>
            readings for <Mono>{entity.data.canonical_id}</Mono>
          </span>
        </div>
      )}
      {entity.loading && <Empty>loading…</Empty>}
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
    </div>
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
  const [tab, setTab] = useState('vocabulary')

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
    setTab('entity')
  }

  const readings = Object.keys(vocab.data?.readings ?? {})

  return (
    <SectionCard
      title="Enrichment"
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
      <div className="space-y-4">
        <Fail error={vocab.error} />
        {vocab.data && (
          <div className="flex flex-wrap items-center gap-2 text-sm text-dbb-muted">
            <Enabled on={vocab.data.enabled} />
            <span>
              model <Mono>{vocab.data.model}</Mono>
            </span>
            {!vocab.data.enabled && <span>· the one layer that calls a model; nothing is read until it is switched on</span>}
          </div>
        )}
        <LayerOff error={runError} />
        {report && <RunResult report={report} />}
        <div className="space-y-1">
          <h4 className="text-sm font-medium text-dbb-charcoal">Coverage</h4>
          <p className="text-sm text-dbb-muted">
            Four separate claims per reading, not one number: eligible entities carry input text; read under the current vocabulary;
            read under a retired vocabulary; never read at all.
          </p>
        </div>
        <Fail error={coverage.error} />
        {coverage.loading && <Empty>loading…</Empty>}
        {coverage.data && <CoverageTable rows={coverage.data.readings} />}
        <Tabs value={tab} onValueChange={setTab}>
          <TabsList>
            <TabsTrigger value="vocabulary">Vocabulary</TabsTrigger>
            <TabsTrigger value="facts">Facts</TabsTrigger>
            <TabsTrigger value="entity">One entity</TabsTrigger>
          </TabsList>
          <TabsContent value="vocabulary" forceMount className={keep}>
            {vocab.data ? <VocabularyTab vocabulary={vocab.data} /> : <Empty>loading…</Empty>}
          </TabsContent>
          <TabsContent value="facts" forceMount className={keep}>
            <FactsTab vocabulary={vocab.data} onPick={pick} />
          </TabsContent>
          <TabsContent value="entity" forceMount className={keep}>
            <div className="space-y-3">
              <form
                className="flex items-center gap-2"
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
              {entityId ? <EntityFacts id={entityId} /> : <Empty>paste a canonical id, or pick one from the facts tab</Empty>}
            </div>
          </TabsContent>
        </Tabs>
      </div>
    </SectionCard>
  )
}
